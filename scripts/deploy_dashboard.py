#!/usr/bin/env python3
"""
Deploy the FMAPI Unified Dashboard to a Databricks workspace.

Usage:
    python scripts/deploy_dashboard.py --config config.yaml
    python scripts/deploy_dashboard.py --profile fevm-demo-classic --warehouse-id abc123 --parent-path /Users/user@company.com
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def deploy_dashboard(profile: str, warehouse_id: str, parent_path: str, dashboard_name: str):
    """Deploy the dashboard JSON via Databricks API."""

    dashboard_file = Path(__file__).parent.parent / "dashboard" / "fmapi_unified_dashboard.json"

    if not dashboard_file.exists():
        print(f"Error: Dashboard file not found: {dashboard_file}")
        sys.exit(1)

    with open(dashboard_file) as f:
        dashboard = json.load(f)

    payload = {
        "display_name": dashboard_name,
        "warehouse_id": warehouse_id,
        "parent_path": parent_path,
        "serialized_dashboard": json.dumps(dashboard),
    }

    payload_file = "/tmp/fmapi_dashboard_payload.json"
    with open(payload_file, "w") as f:
        json.dump(payload, f)

    # Create dashboard
    cmd = f"databricks api post /api/2.0/lakeview/dashboards --profile={profile} --json @{payload_file}"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error creating dashboard: {result.stderr}")
        sys.exit(1)

    # Parse response (strip any ANSI warnings before JSON)
    stdout = result.stdout
    json_start = stdout.find("{")
    if json_start > 0:
        stdout = stdout[json_start:]

    response = json.loads(stdout)
    dashboard_id = response.get("dashboard_id")

    if not dashboard_id:
        print(f"Unexpected response: {response}")
        sys.exit(1)

    # Get workspace URL
    host = ""
    profile_cmd = f"databricks auth env --profile={profile}"
    profile_result = subprocess.run(profile_cmd, shell=True, capture_output=True, text=True)
    for line in profile_result.stdout.split("\n"):
        if "DATABRICKS_HOST" in line:
            host = line.split("=")[1].strip().strip('"')
            break

    print(f"Dashboard created!")
    print(f"  ID: {dashboard_id}")
    if host:
        print(f"  URL: {host}/dashboardsv3/{dashboard_id}")

    # Publish
    publish_cmd = f"databricks api post /api/2.0/lakeview/dashboards/{dashboard_id}/published --profile={profile} --json '{{}}'"
    subprocess.run(publish_cmd, shell=True, capture_output=True)
    print("  Published!")

    return dashboard_id


def main():
    parser = argparse.ArgumentParser(description="Deploy FMAPI Unified Dashboard")
    parser.add_argument("--config", help="Config file path (alternative to --profile/--warehouse-id/--parent-path)")
    parser.add_argument("--profile", help="Databricks CLI profile")
    parser.add_argument("--warehouse-id", help="SQL Warehouse ID")
    parser.add_argument("--parent-path", help="Dashboard parent path")
    parser.add_argument("--name", default="FMAPI Unified Dashboard", help="Dashboard display name")
    args = parser.parse_args()

    if args.config:
        import yaml

        with open(args.config) as f:
            config = yaml.safe_load(f)
        profile = config["databricks_cli_profile"]
        warehouse_id = config["sql_warehouse_id"]
        parent_path = config["dashboard_parent_path"]
    elif args.profile and args.warehouse_id and args.parent_path:
        profile = args.profile
        warehouse_id = args.warehouse_id
        parent_path = args.parent_path
    else:
        parser.error("Provide either --config or all of --profile, --warehouse-id, --parent-path")

    deploy_dashboard(profile, warehouse_id, parent_path, args.name)


if __name__ == "__main__":
    main()
