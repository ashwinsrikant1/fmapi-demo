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
import sys
import time
import yaml
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    EndpointCoreConfigInput,
    ServedEntityInput,
    AiGatewayConfig,
    AiGatewayInferenceTableConfig,
)


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def create_endpoint(
    client: WorkspaceClient,
    endpoint_name: str,
    entity_name: str,
    catalog: str,
    schema: str,
    timeout_minutes: int = 20,
):
    """Create a serving endpoint with AI Gateway and inference tables enabled."""

    # Check if endpoint already exists
    try:
        existing = client.serving_endpoints.get(endpoint_name)
        print(f"  Endpoint '{endpoint_name}' already exists (state: {existing.state.ready})")
        if str(existing.state.ready) == "READY":
            return existing
        print(f"  Waiting for existing endpoint to become READY...")
    except Exception:
        print(f"  Creating endpoint '{endpoint_name}' with entity '{entity_name}'...")
        client.serving_endpoints.create(
            name=endpoint_name,
            config=EndpointCoreConfigInput(
                served_entities=[
                    ServedEntityInput(
                        entity_name=entity_name,
                        entity_version="1",
                    )
                ],
            ),
            ai_gateway=AiGatewayConfig(
                inference_table_config=AiGatewayInferenceTableConfig(
                    catalog_name=catalog,
                    schema_name=schema,
                    enabled=True,
                ),
            ),
        )

    # Wait for READY state
    start = time.time()
    while time.time() - start < timeout_minutes * 60:
        ep = client.serving_endpoints.get(endpoint_name)
        state = str(ep.state.ready)
        if state == "READY":
            print(f"  Endpoint '{endpoint_name}' is READY")
            return ep
        elif state == "NOT_READY":
            config_state = str(ep.state.config_update) if ep.state.config_update else "PENDING"
            print(f"  Waiting... (config: {config_state})")
            time.sleep(30)
        else:
            print(f"  Unexpected state: {state}")
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
            # Execute via databricks SDK statement execution
            client.statement_execution.execute_statement(
                warehouse_id=config.get("sql_warehouse_id", ""),
                statement=sql,
                wait_timeout="120s",
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

    headline_endpoints = [
        (endpoints_cfg["claude_opus_4_6"], "databricks-claude-opus-4-6"),
        (endpoints_cfg["gpt_5_2"], "databricks-gpt-5-2"),
        (endpoints_cfg["gemini_3_1_pro"], "databricks-gemini-3-1-pro"),
    ]

    for ep_name, entity_name in headline_endpoints:
        print(f"\n[{entity_name}]")
        create_endpoint(client, ep_name, entity_name, catalog, schema)

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
    )

    # --- Ground truth table for evaluation demo ---
    create_ground_truth_table(client, catalog, schema)

    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    print(f"\nEndpoints created:")
    for ep_name, entity_name in headline_endpoints:
        print(f"  - {ep_name} ({entity_name})")
    print(f"  - {endpoints_cfg['claude_opus_4_5']} (databricks-claude-opus-4-5)")
    print(f"\nGround truth table: {catalog}.{schema}.evaluation_ground_truth")
    print(f"\nNext step: python scripts/02_test_requests.py")


if __name__ == "__main__":
    main()
