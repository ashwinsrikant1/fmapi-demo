#!/usr/bin/env python3
"""
Scene 2 Demo: Send identical prompts to all three model families via OpenAI SDK.

The key demo moment: ONE client, ONE SDK, ONE auth — hitting Claude, GPT, and Gemini.
This is what neither Bedrock (no OpenAI, no Gemini) nor Vertex (no OpenAI) can match.

Usage:
    python scripts/02_test_requests.py                    # Single prompt, side-by-side
    python scripts/02_test_requests.py --batch             # 20+ requests per endpoint (populate system tables)
    python scripts/02_test_requests.py --batch --count 50  # Custom batch size
"""

import argparse
import time
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from tabulate import tabulate


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


DEMO_PROMPT = (
    "In exactly 2-3 sentences, explain why a unified data platform "
    "is better than managing separate tools for data engineering, "
    "analytics, and AI."
)

BATCH_PROMPTS = [
    "What is a lakehouse architecture?",
    "Explain ACID transactions in one sentence.",
    "What are the benefits of Unity Catalog?",
    "Compare batch vs streaming processing.",
    "What is Delta Lake?",
    "Explain the medallion architecture.",
    "What is model serving?",
    "How does feature engineering work?",
    "What is MLflow?",
    "Explain data governance in 2 sentences.",
    "What is a SQL warehouse?",
    "How do vector databases work?",
    "What is RAG (retrieval-augmented generation)?",
    "Explain fine-tuning vs prompt engineering.",
    "What are embeddings?",
    "How does A/B testing work for ML models?",
    "What is inference table logging?",
    "Explain the concept of model evaluation.",
    "What is a serving endpoint?",
    "How does auto-scaling work for model serving?",
]


def send_request(client: OpenAI, endpoint_name: str, prompt: str) -> dict:
    """Send a single chat completion request and return timing + response."""
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=endpoint_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.7,
        )
        elapsed = time.time() - start
        return {
            "endpoint": endpoint_name,
            "response": response.choices[0].message.content.strip(),
            "tokens_in": response.usage.prompt_tokens,
            "tokens_out": response.usage.completion_tokens,
            "latency_s": round(elapsed, 2),
            "status": "OK",
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "endpoint": endpoint_name,
            "response": str(e)[:100],
            "tokens_in": 0,
            "tokens_out": 0,
            "latency_s": round(elapsed, 2),
            "status": "ERROR",
        }


def demo_side_by_side(client: OpenAI, endpoints: list[str]):
    """Scene 2: Send the same prompt to all three families, show side-by-side."""
    print("=" * 70)
    print("SCENE 2: One Gateway, Every Model")
    print(f"Prompt: \"{DEMO_PROMPT[:80]}...\"")
    print("=" * 70)

    results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(send_request, client, ep, DEMO_PROMPT): ep
            for ep in endpoints
        }
        for future in as_completed(futures):
            results.append(future.result())

    # Sort by endpoint name for consistent display
    results.sort(key=lambda r: r["endpoint"])

    for r in results:
        provider = "unknown"
        if "claude" in r["endpoint"].lower():
            provider = "Anthropic"
        elif "gpt" in r["endpoint"].lower():
            provider = "OpenAI"
        elif "gemini" in r["endpoint"].lower():
            provider = "Google"

        print(f"\n--- {provider}: {r['endpoint']} ({r['latency_s']}s) ---")
        print(r["response"][:300])

    # Summary table
    print("\n" + "-" * 70)
    table = [
        [r["endpoint"], r["status"], r["tokens_in"], r["tokens_out"], r["latency_s"]]
        for r in results
    ]
    print(tabulate(table, headers=["Endpoint", "Status", "In Tokens", "Out Tokens", "Latency (s)"]))


def batch_requests(client: OpenAI, endpoints: list[str], count: int):
    """Send many requests to populate system tables for the dashboard demo."""
    print("=" * 70)
    print(f"BATCH MODE: Sending {count} requests per endpoint to populate system tables")
    print("=" * 70)

    prompts = (BATCH_PROMPTS * ((count // len(BATCH_PROMPTS)) + 1))[:count]
    total = len(endpoints) * count
    completed = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for ep in endpoints:
            for prompt in prompts:
                futures.append(executor.submit(send_request, client, ep, prompt))

        for future in as_completed(futures):
            result = future.result()
            completed += 1
            if result["status"] != "OK":
                errors += 1
            if completed % 10 == 0 or completed == total:
                print(f"  Progress: {completed}/{total} (errors: {errors})")

    print(f"\nBatch complete: {completed} requests sent, {errors} errors")
    print("System tables will populate in 5-30 minutes.")
    print("Inference tables may take up to 1 hour.")


def main():
    parser = argparse.ArgumentParser(description="Test FMAPI endpoints with OpenAI SDK")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--batch", action="store_true", help="Send many requests for system table population")
    parser.add_argument("--count", type=int, default=20, help="Requests per endpoint in batch mode")
    args = parser.parse_args()

    config = load_config(args.config)

    # ONE client for ALL models — this is the demo moment
    client = OpenAI(
        base_url=f"{config['workspace_host']}/serving-endpoints",
        api_key=config.get("databricks_token") or None,
    )

    endpoints_cfg = config["endpoints"]
    primary_endpoints = [
        endpoints_cfg["claude_opus_4_6"],
        endpoints_cfg["gpt_5_2"],
        endpoints_cfg["gemini_3_1_pro"],
    ]

    if args.batch:
        # Batch mode: hit all endpoints including Opus 4.5
        all_endpoints = primary_endpoints + [endpoints_cfg["claude_opus_4_5"]]
        batch_requests(client, all_endpoints, args.count)
    else:
        # Demo mode: side-by-side comparison
        demo_side_by_side(client, primary_endpoints)

        # Also send a couple requests to Opus 4.5 for A/B test data
        print(f"\n\nSending a few requests to {endpoints_cfg['claude_opus_4_5']} for A/B test data...")
        for prompt in BATCH_PROMPTS[:3]:
            r = send_request(client, endpoints_cfg["claude_opus_4_5"], prompt)
            print(f"  {r['status']} ({r['latency_s']}s)")

    print(f"\nNext step: python scripts/03_ab_test_routing.py")


if __name__ == "__main__":
    main()
