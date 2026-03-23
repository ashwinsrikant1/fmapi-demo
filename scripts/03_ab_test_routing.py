#!/usr/bin/env python3
"""
Scene 4 Demo: A/B test routing between Claude Opus 4.5 and Opus 4.6.

Real-world scenario: "Opus 4.6 just dropped — run it side-by-side with Opus 4.5,
compare quality, then pick the winner." Traffic split 70/30.

Uses an external model gateway endpoint that routes to existing pay-per-token
foundation model endpoints — no GPU provisioning required, instant deployment.

Usage:
    python scripts/03_ab_test_routing.py
    python scripts/03_ab_test_routing.py --config config.yaml
"""

import argparse
import json
import subprocess
import sys
import time
import yaml
from collections import Counter
from openai import OpenAI
from tabulate import tabulate


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
        payload_file = "/tmp/fmapi_ab_payload.json"
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


def create_ab_test_endpoint(config: dict):
    """Create a gateway endpoint that routes to existing foundation model endpoints."""
    endpoint_name = config["endpoints"]["ab_test"]
    catalog = config["inference_table_catalog"]
    schema = config["inference_table_schema"]
    profile = config["databricks_cli_profile"]
    workspace_host = config["workspace_host"]

    opus_46_endpoint = config["endpoints"]["claude_opus_4_6"]
    opus_45_endpoint = config["endpoints"]["claude_opus_4_5"]

    print("=" * 60)
    print("SCENE 4: A/B Test Routing")
    print(f"Endpoint: {endpoint_name}")
    print(f"  Route A (70%): {opus_46_endpoint}")
    print(f"  Route B (30%): {opus_45_endpoint}")
    print("=" * 60)

    # Store a fresh token as a Databricks secret for the gateway to authenticate
    # to backend endpoints. Secret references are more reliable than plaintext tokens.
    secret_scope = "fmapi"
    secret_key = "api_token"
    token = get_fresh_token(profile)

    print(f"\nStoring fresh token in secret scope '{secret_scope}'...")
    store_cmd = f'databricks secrets put-secret {secret_scope} {secret_key} --string-value "{token}" --profile={profile}'
    result = subprocess.run(store_cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        # Create scope if it doesn't exist, then retry
        subprocess.run(
            f"databricks secrets create-scope {secret_scope} --profile={profile}",
            shell=True, capture_output=True, text=True,
        )
        subprocess.run(store_cmd, shell=True, capture_output=True, text=True)

    secret_ref = f"{{{{secrets/{secret_scope}/{secret_key}}}}}"

    def build_served_entities():
        return [
            {
                "name": "claude-opus-4-6",
                "external_model": {
                    "name": opus_46_endpoint,
                    "provider": "databricks-model-serving",
                    "task": "llm/v1/chat",
                    "databricks_model_serving_config": {
                        "databricks_workspace_url": workspace_host,
                        "databricks_api_token": secret_ref,
                    },
                },
            },
            {
                "name": "claude-opus-4-5",
                "external_model": {
                    "name": opus_45_endpoint,
                    "provider": "databricks-model-serving",
                    "task": "llm/v1/chat",
                    "databricks_model_serving_config": {
                        "databricks_workspace_url": workspace_host,
                        "databricks_api_token": secret_ref,
                    },
                },
            },
        ]

    traffic_config = {
        "routes": [
            {"served_model_name": "claude-opus-4-6", "traffic_percentage": 70},
            {"served_model_name": "claude-opus-4-5", "traffic_percentage": 30},
        ]
    }

    # Check if endpoint already exists
    existing = run_databricks_api("get", f"/api/2.0/serving-endpoints/{endpoint_name}", profile)

    if "error" not in existing:
        print(f"\nEndpoint '{endpoint_name}' exists — updating config...")
        payload = {
            "served_entities": build_served_entities(),
            "traffic_config": traffic_config,
        }
        result = run_databricks_api(
            "put", f"/api/2.0/serving-endpoints/{endpoint_name}/config", profile, payload
        )
    else:
        print(f"\nCreating new A/B test endpoint...")
        payload = {
            "name": endpoint_name,
            "config": {
                "served_entities": build_served_entities(),
                "traffic_config": traffic_config,
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
        print(f"Error: {result['error']}")
        sys.exit(1)

    state = result.get("state", {})
    print(f"Endpoint state: {state.get('ready', 'unknown')}")
    if state.get("ready") == "READY":
        print("Endpoint is READY!")


def send_ab_test_requests(config: dict, count: int = 20):
    """Send requests through the A/B endpoint and show routing distribution."""
    endpoint_name = config["endpoints"]["ab_test"]
    profile = config["databricks_cli_profile"]

    # Use a fresh token for requests
    token = get_fresh_token(profile)
    client = OpenAI(
        base_url=f"{config['workspace_host']}/serving-endpoints",
        api_key=token,
    )

    print(f"\n--- Sending {count} requests through A/B endpoint ---")

    prompts = [
        "Explain data governance in one sentence.",
        "What is a feature store?",
        "Define model drift.",
        "What is prompt engineering?",
        "Explain vector search briefly.",
    ]

    results = []
    for i in range(count):
        prompt = prompts[i % len(prompts)]
        start = time.time()
        try:
            response = client.chat.completions.create(
                model=endpoint_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
            )
            elapsed = time.time() - start
            model_used = response.model or "unknown"
            # Simplify model name for display
            if "opus-4-6" in model_used:
                display_name = "Opus 4.6"
            elif "opus-4-5" in model_used:
                display_name = "Opus 4.5"
            else:
                display_name = model_used

            results.append({
                "request": i + 1,
                "model": display_name,
                "latency": round(elapsed, 2),
                "tokens": response.usage.completion_tokens,
            })
        except Exception as e:
            results.append({
                "request": i + 1,
                "model": "ERROR",
                "latency": round(time.time() - start, 2),
                "tokens": 0,
            })

        if (i + 1) % 5 == 0:
            print(f"  Sent {i + 1}/{count}")

    # Show distribution
    model_counts = Counter(r["model"] for r in results)
    print(f"\n--- Routing Distribution ---")
    for model, cnt in model_counts.most_common():
        pct = (cnt / len(results)) * 100
        print(f"  {model}: {cnt} requests ({pct:.0f}%)")

    # Show latency comparison
    print(f"\n--- Latency by Model ---")
    for model in model_counts:
        if model == "ERROR":
            continue
        latencies = [r["latency"] for r in results if r["model"] == model]
        if latencies:
            avg = sum(latencies) / len(latencies)
            print(f"  {model}: avg={avg:.2f}s, min={min(latencies):.2f}s, max={max(latencies):.2f}s")

    print(f"\nRouting information will appear in system.ai_gateway.usage within 5-30 minutes.")
    print(f"Query: SELECT routing_information FROM system.ai_gateway.usage")
    print(f"       WHERE endpoint_name = '{endpoint_name}'")


def main():
    parser = argparse.ArgumentParser(description="A/B test routing demo")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--count", type=int, default=20, help="Number of test requests")
    parser.add_argument("--skip-create", action="store_true", help="Skip endpoint creation, just send requests")
    args = parser.parse_args()

    config = load_config(args.config)

    if not args.skip_create:
        create_ab_test_endpoint(config)

    send_ab_test_requests(config, args.count)


if __name__ == "__main__":
    main()
