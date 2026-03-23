#!/usr/bin/env python3
"""
Scene 2 Setup: Create serving endpoints for all three major model families.

This is the headline differentiator: Claude (Anthropic), GPT (OpenAI), and Gemini (Google)
all served natively through a single gateway — something neither Bedrock (no OpenAI, no Gemini) nor Vertex (no OpenAI) can match.

Also creates a Claude Opus 4.5 endpoint for the A/B test demo (Scene 4),
and a ground truth table for the evaluation demo (Scene 4b).

Usage:
    python scripts/01_endpoint_setup.py
    python scripts/01_endpoint_setup.py --config config.yaml
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
import yaml
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointStateReady


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_fresh_token(profile: str) -> str:
    """Get a fresh OAuth token from the Databricks CLI."""
    result = subprocess.run(
        ["databricks", "auth", "token", "--profile", profile],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Error getting token: {result.stderr}")
        sys.exit(1)
    return json.loads(result.stdout)["access_token"]


def run_databricks_api(method: str, path: str, profile: str, payload: dict | None = None) -> dict:
    """Call the Databricks REST API via the CLI."""
    cmd = f"databricks api {method} {path} --profile={profile}"
    if payload:
        payload_file = "/tmp/fmapi_endpoint_payload.json"
        with open(payload_file, "w") as f:
            json.dump(payload, f)
        cmd += f" --json @{payload_file}"

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        return {"error": result.stderr}

    stdout = result.stdout
    json_start = stdout.find("{")
    if json_start > 0:
        stdout = stdout[json_start:]
    return json.loads(stdout) if stdout.strip() else {}


def create_endpoint(
    client: WorkspaceClient,
    endpoint_name: str,
    foundation_model_name: str,
    catalog: str,
    schema: str,
    profile: str,
    timeout_minutes: int = 20,
):
    """Create a pay-per-token serving endpoint with AI Gateway and inference tables enabled."""

    # Check if endpoint already exists
    try:
        existing = client.serving_endpoints.get(endpoint_name)
        print(f"  Endpoint '{endpoint_name}' already exists (state: {existing.state.ready})")
        if existing.state.ready == EndpointStateReady.READY:
            return existing
        print(f"  Waiting for existing endpoint to become READY...")
    except Exception:
        print(f"  Creating endpoint '{endpoint_name}' (pay-per-token)...")
        payload = {
            "name": endpoint_name,
            "config": {
                "served_entities": [
                    {
                        "name": endpoint_name,
                        "external_model": {
                            "name": foundation_model_name,
                            "provider": "databricks-model-serving",
                            "task": "llm/v1/chat",
                            "databricks_model_serving_config": {
                                "databricks_workspace_url": client.config.host,
                                "databricks_api_token_plaintext": get_fresh_token(profile),
                            },
                        },
                    }
                ],
            },
            "ai_gateway": {
                "inference_table_config": {
                    "catalog_name": catalog,
                    "schema_name": schema,
                    "enabled": True,
                },
            },
        }
        result = run_databricks_api("post", "/api/2.0/serving-endpoints", profile, payload)
        if "error" in result:
            print(f"  Error: {result['error']}")
            return None

    # Wait for READY state
    start = time.time()
    while time.time() - start < timeout_minutes * 60:
        ep = client.serving_endpoints.get(endpoint_name)
        ready = ep.state.ready
        if ready == EndpointStateReady.READY:
            print(f"  Endpoint '{endpoint_name}' is READY")
            return ep
        if ready == EndpointStateReady.NOT_READY:
            config_state = str(ep.state.config_update) if ep.state.config_update else "PENDING"
            elapsed = int(time.time() - start)
            print(f"  Waiting... ({elapsed}s, config: {config_state})")
            time.sleep(30)
            continue
        print(f"  Unexpected state: {ready!r}")
        time.sleep(15)

    print(f"  TIMEOUT: Endpoint '{endpoint_name}' did not reach READY in {timeout_minutes} min")
    sys.exit(1)


def create_ground_truth_table(client: WorkspaceClient, catalog: str, schema: str):
    """Create a sample ground truth table for the evaluation demo (Scene 4b)."""
    print("\n--- Creating evaluation ground truth table ---")

    full_table = f"{catalog}.{schema}.evaluation_ground_truth"

    # Use SQL via the statement execution API
    sql_statements = [
        f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}",
        f"""CREATE TABLE IF NOT EXISTS {full_table} (
            prompt STRING,
            expected_response STRING,
            quality_score DOUBLE,
            category STRING
        ) USING DELTA""",
        f"TRUNCATE TABLE {full_table}",
        f"""INSERT INTO {full_table} VALUES
            ('Summarize the key benefits of a unified data platform.',
             'A unified data platform consolidates data engineering, analytics, and AI on one platform, reducing complexity, improving governance, and lowering costs.',
             0.95, 'summarization'),
            ('What is the difference between batch and streaming data processing?',
             'Batch processing handles data in large groups at scheduled intervals, while streaming processes data in real-time as it arrives. Modern platforms like Databricks support both paradigms.',
             0.90, 'explanation'),
            ('Write a SQL query to find the top 5 customers by revenue.',
             'SELECT customer_name, SUM(revenue) as total_revenue FROM sales GROUP BY customer_name ORDER BY total_revenue DESC LIMIT 5',
             0.85, 'code_generation'),
            ('Explain model governance in the context of enterprise AI.',
             'Model governance encompasses tracking model lineage, monitoring performance, ensuring compliance, controlling access, and maintaining audit trails across the ML lifecycle.',
             0.92, 'explanation'),
            ('What are the advantages of using a lakehouse architecture?',
             'Lakehouse combines the flexibility and cost-efficiency of data lakes with the reliability and performance of data warehouses, supporting ACID transactions, schema enforcement, and unified batch/streaming.',
             0.88, 'summarization')""",
    ]

    for sql in sql_statements:
        try:
            client.statement_execution.execute_statement(
                warehouse_id=config.get("sql_warehouse_id", ""),
                statement=sql,
                wait_timeout="50s",
            )
        except Exception as e:
            print(f"  Warning: {e}")

    print(f"  Ground truth table created: {full_table}")


def main():
    parser = argparse.ArgumentParser(description="Create FMAPI demo serving endpoints")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument(
        "--skip-wait",
        action="store_true",
        help="Create endpoints without waiting for READY state",
    )
    args = parser.parse_args()

    global config
    config = load_config(args.config)

    profile = config["databricks_cli_profile"]

    # Initialize client
    client = WorkspaceClient(
        host=config["workspace_host"],
        profile=config.get("databricks_cli_profile"),
        token=config.get("databricks_token") or None,
    )

    endpoints_cfg = config["endpoints"]
    catalog = config["inference_table_catalog"]
    schema = config["inference_table_schema"]

    # --- Headline demo: All three major model families ---
    print("=" * 60)
    print("SCENE 2: One Gateway, Every Model")
    print("Creating endpoints for all three major model families")
    print("=" * 60)

    # Foundation model endpoints (pay-per-token, served via external model gateway)
    headline_endpoints = [
        (endpoints_cfg["claude_opus_4_6"], "databricks-claude-opus-4-6"),
        (endpoints_cfg["gpt_5_2"], "databricks-gpt-5-2"),
        (endpoints_cfg["gemini_3_1_pro"], "databricks-gemini-3-1-pro"),
    ]

    for ep_name, model_name in headline_endpoints:
        print(f"\n[{model_name}]")
        create_endpoint(client, ep_name, model_name, catalog, schema, profile)

    # --- Version optionality: Opus 4.5 for A/B test ---
    print("\n" + "=" * 60)
    print("SCENE 4: Version Optionality (A/B Test)")
    print("Creating Claude Opus 4.5 for side-by-side comparison")
    print("=" * 60)

    print(f"\n[databricks-claude-opus-4-5]")
    create_endpoint(
        client,
        endpoints_cfg["claude_opus_4_5"],
        "databricks-claude-opus-4-5",
        catalog,
        schema,
        profile,
    )

    # --- Ground truth table for evaluation demo ---
    create_ground_truth_table(client, catalog, schema)

    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    print(f"\nEndpoints created:")
    for ep_name, model_name in headline_endpoints:
        print(f"  - {ep_name} ({model_name})")
    print(f"  - {endpoints_cfg['claude_opus_4_5']} (databricks-claude-opus-4-5)")
    print(f"\nGround truth table: {catalog}.{schema}.evaluation_ground_truth")
    print(f"\nNext step: python scripts/02_test_requests.py")


if __name__ == "__main__":
    main()
