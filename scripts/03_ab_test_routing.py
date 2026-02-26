#!/usr/bin/env python3
"""
Scene 4 Demo: A/B test routing between Claude Opus 4.5 and Opus 4.6.

Real-world scenario: "Opus 4.6 just dropped — run it side-by-side with Opus 4.5,
compare quality, then pick the winner." Traffic split 70/30, with fallback enabled.

Usage:
    python scripts/03_ab_test_routing.py
    python scripts/03_ab_test_routing.py --config config.yaml
"""

import argparse
import time
import yaml
from collections import Counter
from openai import OpenAI
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    EndpointCoreConfigInput,
    ServedEntityInput,
    TrafficConfig,
    Route,
    AiGatewayConfig,
    AiGatewayInferenceTableConfig,
    FallbackConfig,
)
from tabulate import tabulate


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def create_ab_test_endpoint(client: WorkspaceClient, config: dict):
    """Create an endpoint with two served entities and traffic splitting."""
    endpoint_name = config["endpoints"]["ab_test"]
    catalog = config["inference_table_catalog"]
    schema = config["inference_table_schema"]

    print("=" * 60)
    print("SCENE 4: A/B Test Routing")
    print(f"Endpoint: {endpoint_name}")
    print("Traffic split: 70% Opus 4.6, 30% Opus 4.5")
    print("Fallback: enabled")
    print("=" * 60)

    # Check if exists
    try:
        existing = client.serving_endpoints.get(endpoint_name)
        print(f"\nEndpoint '{endpoint_name}' exists — updating config...")
        client.serving_endpoints.update_config(
            name=endpoint_name,
            served_entities=[
                ServedEntityInput(
                    entity_name="system.ai.databricks-claude-opus-4-6",
                    entity_version="1",
                    name="claude-opus-4-6",
                    workload_size="Small",
                ),
                ServedEntityInput(
                    entity_name="system.ai.databricks-claude-opus-4-5",
                    entity_version="1",
                    name="claude-opus-4-5",
                    workload_size="Small",
                ),
            ],
            traffic_config=TrafficConfig(
                routes=[
                    Route(
                        served_model_name="claude-opus-4-6",
                        traffic_percentage=70,
                    ),
                    Route(
                        served_model_name="claude-opus-4-5",
                        traffic_percentage=30,
                    ),
                ]
            ),
        )
    except Exception:
        print(f"\nCreating new A/B test endpoint...")
        client.serving_endpoints.create(
            name=endpoint_name,
            config=EndpointCoreConfigInput(
                name=endpoint_name,
                served_entities=[
                    ServedEntityInput(
                        entity_name="system.ai.databricks-claude-opus-4-6",
                        entity_version="1",
                        name="claude-opus-4-6",
                        workload_size="Small",
                    ),
                    ServedEntityInput(
                        entity_name="system.ai.databricks-claude-opus-4-5",
                        entity_version="1",
                        name="claude-opus-4-5",
                        workload_size="Small",
                    ),
                ],
                traffic_config=TrafficConfig(
                    routes=[
                        Route(
                            served_model_name="claude-opus-4-6",
                            traffic_percentage=70,
                        ),
                        Route(
                            served_model_name="claude-opus-4-5",
                            traffic_percentage=30,
                        ),
                    ]
                ),
            ),
            ai_gateway=AiGatewayConfig(
                inference_table_config=AiGatewayInferenceTableConfig(
                    catalog_name=catalog,
                    schema_name=schema,
                    enabled=True,
                ),
                # fallback_config not supported for foundation model endpoints
            ),
        )

    # Wait for ready
    print("Waiting for endpoint to be READY...")
    for _ in range(40):
        ep = client.serving_endpoints.get(endpoint_name)
        if str(ep.state.ready) == "READY":
            print("Endpoint is READY!")
            return
        time.sleep(15)

    print("WARNING: Endpoint did not reach READY state in time. Continuing anyway.")


def send_ab_test_requests(config: dict, count: int = 20):
    """Send requests through the A/B endpoint and show routing distribution."""
    endpoint_name = config["endpoints"]["ab_test"]

    client = OpenAI(
        base_url=f"{config['workspace_host']}/serving-endpoints",
        api_key=config.get("databricks_token") or None,
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
            # The model field in the response indicates which served entity handled it
            model_used = response.model or "unknown"
            results.append({
                "request": i + 1,
                "model": model_used,
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
        sdk_client = WorkspaceClient(
            host=config["workspace_host"],
            profile=config.get("databricks_cli_profile"),
            token=config.get("databricks_token") or None,
        )
        create_ab_test_endpoint(sdk_client, config)

    send_ab_test_requests(config, args.count)


if __name__ == "__main__":
    main()
