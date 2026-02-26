#!/usr/bin/env python3
"""
Build the FMAPI Unified Dashboard JSON programmatically.

Run this to regenerate dashboard/fmapi_unified_dashboard.json.
Uses the LakeviewDashboard builder class.

Usage:
    python scripts/build_dashboard.py
"""

import json
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from lakeview_builder import LakeviewDashboard


def build_dashboard() -> dict:
    dashboard = LakeviewDashboard("FMAPI Unified Dashboard")

    # =========================================================================
    # DATASETS
    # =========================================================================

    # Dataset 1: All-model usage (extends claude-endpoint-dashboard to all providers)
    dashboard.add_dataset(
        "all_model_usage",
        "All Model Usage",
        (
            "SELECT\n"
            "    u.request_time,\n"
            "    DATE(u.request_time) as request_date,\n"
            "    u.input_token_count,\n"
            "    u.output_token_count,\n"
            "    u.input_token_count + u.output_token_count as total_tokens,\n"
            "    u.status_code,\n"
            "    CASE WHEN u.status_code = 200 THEN 'Success' ELSE 'Error' END as status,\n"
            "    u.requester,\n"
            "    e.endpoint_name,\n"
            "    COALESCE(e.served_entity_name, e.entity_name) as model_name,\n"
            "    e.entity_name as model_version,\n"
            "    CASE\n"
            "        WHEN LOWER(e.entity_name) LIKE '%claude%' OR LOWER(e.endpoint_name) LIKE '%claude%' THEN 'Anthropic'\n"
            "        WHEN LOWER(e.entity_name) LIKE '%gpt%' OR LOWER(e.endpoint_name) LIKE '%gpt%' OR LOWER(e.entity_name) LIKE '%openai%' THEN 'OpenAI'\n"
            "        WHEN LOWER(e.entity_name) LIKE '%gemini%' OR LOWER(e.endpoint_name) LIKE '%gemini%' THEN 'Google'\n"
            "        WHEN LOWER(e.entity_name) LIKE '%llama%' OR LOWER(e.entity_name) LIKE '%meta%' THEN 'Meta'\n"
            "        ELSE 'Other'\n"
            "    END as provider\n"
            "FROM system.serving.endpoint_usage u\n"
            "JOIN system.serving.served_entities e\n"
            "    ON u.served_entity_id = e.served_entity_id\n"
            "WHERE e.entity_type = 'FOUNDATION_MODEL'\n"
            "   OR e.external_model_config IS NOT NULL"
        ),
    )

    # Dataset 2: Billing across all MODEL_SERVING SKUs
    dashboard.add_dataset(
        "all_model_billing",
        "All Model Billing",
        (
            "SELECT\n"
            "    usage_date as request_date,\n"
            "    usage_metadata.endpoint_name as endpoint_name,\n"
            "    CASE\n"
            "        WHEN u.sku_name LIKE '%ANTHROPIC%' THEN 'Anthropic'\n"
            "        WHEN u.sku_name LIKE '%OPENAI%' THEN 'OpenAI'\n"
            "        WHEN u.sku_name LIKE '%GOOGLE%' THEN 'Google'\n"
            "        WHEN u.sku_name LIKE '%META%' OR u.sku_name LIKE '%LLAMA%' THEN 'Meta'\n"
            "        ELSE 'Other'\n"
            "    END as provider,\n"
            "    u.sku_name,\n"
            "    SUM(usage_quantity) as total_dbus,\n"
            "    SUM(usage_quantity * COALESCE(lp.pricing.effective_list.default, 0.07)) as estimated_cost\n"
            "FROM system.billing.usage u\n"
            "LEFT JOIN system.billing.list_prices lp\n"
            "    ON u.sku_name = lp.sku_name\n"
            "    AND u.cloud = lp.cloud\n"
            "    AND u.usage_start_time >= lp.price_start_time\n"
            "    AND (lp.price_end_time IS NULL OR u.usage_start_time < lp.price_end_time)\n"
            "WHERE u.sku_name LIKE '%MODEL_SERVING%'\n"
            "   OR u.sku_name LIKE '%FOUNDATION_MODEL%'\n"
            "GROUP BY usage_date, usage_metadata.endpoint_name, u.sku_name"
        ),
    )

    # Dataset 3: AI Gateway usage (for Page 2)
    dashboard.add_dataset(
        "ai_gateway_usage",
        "AI Gateway Usage",
        (
            "SELECT\n"
            "    event_time,\n"
            "    DATE(event_time) as request_date,\n"
            "    endpoint_name,\n"
            "    destination_model as model_name,\n"
            "    CASE\n"
            "        WHEN LOWER(destination_model) LIKE '%claude%' THEN 'Anthropic'\n"
            "        WHEN LOWER(destination_model) LIKE '%gpt%' THEN 'OpenAI'\n"
            "        WHEN LOWER(destination_model) LIKE '%gemini%' THEN 'Google'\n"
            "        WHEN LOWER(destination_model) LIKE '%llama%' THEN 'Meta'\n"
            "        ELSE 'Other'\n"
            "    END as provider,\n"
            "    input_tokens as input_token_count,\n"
            "    output_tokens as output_token_count,\n"
            "    total_tokens as total_token_count,\n"
            "    latency_ms as request_latency_ms,\n"
            "    time_to_first_byte_ms as time_to_first_token_ms,\n"
            "    status_code,\n"
            "    CASE WHEN status_code = 200 THEN 'Success' ELSE 'Error' END as status,\n"
            "    requester,\n"
            "    routing_information\n"
            "FROM system.ai_gateway.usage"
        ),
    )

    # Dataset 4: Routing data (for Page 3)
    dashboard.add_dataset(
        "routing_data",
        "Routing & A/B Tests",
        (
            "SELECT\n"
            "    event_time,\n"
            "    DATE(event_time) as request_date,\n"
            "    endpoint_name,\n"
            "    destination_model as model_name,\n"
            "    routing_information,\n"
            "    routing_information.attempts[0].destination as routed_to,\n"
            "    input_tokens as input_token_count,\n"
            "    output_tokens as output_token_count,\n"
            "    latency_ms as request_latency_ms,\n"
            "    status_code,\n"
            "    requester\n"
            "FROM system.ai_gateway.usage\n"
            "WHERE routing_information IS NOT NULL"
        ),
    )

    # =========================================================================
    # PAGE 1: Gateway Overview
    # =========================================================================
    # (Default page already created as "Overview" — rename it)
    dashboard.pages[0]["displayName"] = "Gateway Overview"

    # Global date filter — spans all four datasets
    dashboard.add_date_filter(
        [
            ("all_model_usage", "request_date"),
            ("all_model_billing", "request_date"),
            ("ai_gateway_usage", "request_date"),
            ("routing_data", "request_date"),
        ],
        "request_date", "Date Range",
        position={"x": 0, "y": 0, "width": 2, "height": 1},
    )
    dashboard.add_filter_dropdown(
        "all_model_usage", "provider", "Provider",
        position={"x": 2, "y": 0, "width": 1, "height": 1},
        multi_select=True,
    )
    dashboard.add_filter_dropdown(
        "all_model_usage", "endpoint_name", "Endpoint",
        position={"x": 3, "y": 0, "width": 2, "height": 1},
        multi_select=True,
    )

    # KPI counters row
    dashboard.add_counter(
        "all_model_usage", "*", "COUNT", "Total Requests",
        position={"x": 0, "y": 1, "width": 1, "height": 2},
    )
    dashboard.add_counter(
        "all_model_usage", "input_token_count", "SUM", "Input Tokens",
        position={"x": 1, "y": 1, "width": 1, "height": 2},
    )
    dashboard.add_counter(
        "all_model_usage", "output_token_count", "SUM", "Output Tokens",
        position={"x": 2, "y": 1, "width": 1, "height": 2},
    )
    dashboard.add_counter(
        "all_model_usage", "requester", "COUNT_DISTINCT", "Unique Users",
        position={"x": 3, "y": 1, "width": 1, "height": 2},
    )
    dashboard.add_counter(
        "all_model_usage", "endpoint_name", "COUNT_DISTINCT", "Active Endpoints",
        position={"x": 4, "y": 1, "width": 1, "height": 2},
    )
    dashboard.add_counter(
        "all_model_billing", "estimated_cost", "SUM", "Est. Cost ($)",
        position={"x": 5, "y": 1, "width": 1, "height": 2},
    )

    # Daily requests by provider (line chart)
    dashboard.add_line_chart(
        "all_model_usage", "request_date", "*", "COUNT",
        title="Daily Requests by Provider",
        position={"x": 0, "y": 3, "width": 6, "height": 4},
        color_field="provider",
    )

    # Cost by provider (bar chart)
    dashboard.add_bar_chart(
        "all_model_billing", "provider", "estimated_cost", "SUM",
        title="Cost by Provider",
        position={"x": 0, "y": 7, "width": 3, "height": 5},
        sort_descending=True,
        colors=["#FF6B35", "#00A972", "#4285F4", "#8BCAE7", "#919191"],
    )

    # Requests by endpoint (bar chart)
    dashboard.add_bar_chart(
        "all_model_usage", "endpoint_name", "*", "COUNT",
        title="Requests by Endpoint",
        position={"x": 3, "y": 7, "width": 3, "height": 5},
        sort_descending=True,
    )

    # Requests by model (pie)
    dashboard.add_pie_chart(
        "all_model_usage", "*", "provider", "COUNT",
        title="Requests by Provider",
        position={"x": 0, "y": 12, "width": 3, "height": 5},
    )

    # Token usage by model (bar)
    dashboard.add_bar_chart(
        "all_model_usage", "model_name", "total_tokens", "SUM",
        title="Token Usage by Model",
        position={"x": 3, "y": 12, "width": 3, "height": 5},
        sort_descending=True,
        colors=["#8BCAE7"],
    )

    # Daily cost trend
    dashboard.add_line_chart(
        "all_model_billing", "request_date", "estimated_cost", "SUM",
        title="Daily Estimated Cost ($)",
        position={"x": 0, "y": 17, "width": 6, "height": 4},
        color_field="provider",
    )

    # Top users
    dashboard.add_bar_chart(
        "all_model_usage", "requester", "*", "COUNT",
        title="Requests by User",
        position={"x": 0, "y": 21, "width": 6, "height": 5},
        sort_descending=True,
        colors=["#00A972"],
    )

    # =========================================================================
    # PAGE 2: AI Gateway & Performance
    # =========================================================================
    dashboard.add_page("AI Gateway & Performance")

    # Filters (date range is global from Page 1)
    dashboard.add_filter_dropdown(
        "ai_gateway_usage", "provider", "Provider",
        position={"x": 0, "y": 0, "width": 2, "height": 1},
        multi_select=True,
    )
    dashboard.add_filter_dropdown(
        "ai_gateway_usage", "endpoint_name", "Endpoint",
        position={"x": 2, "y": 0, "width": 2, "height": 1},
        multi_select=True,
    )

    # Latency comparison by model (bar chart)
    dashboard.add_bar_chart(
        "ai_gateway_usage", "model_name", "request_latency_ms", "AVG",
        title="Avg Latency by Model (ms)",
        position={"x": 0, "y": 1, "width": 3, "height": 5},
        sort_descending=True,
        colors=["#FF6B35"],
    )

    # TTFB by model
    dashboard.add_bar_chart(
        "ai_gateway_usage", "model_name", "time_to_first_token_ms", "AVG",
        title="Avg Time to First Token by Model (ms)",
        position={"x": 3, "y": 1, "width": 3, "height": 5},
        sort_descending=True,
        colors=["#AB4057"],
    )

    # Throughput trend (daily requests)
    dashboard.add_line_chart(
        "ai_gateway_usage", "request_date", "*", "COUNT",
        title="Daily Request Throughput",
        position={"x": 0, "y": 6, "width": 6, "height": 4},
        color_field="provider",
    )

    # Error rate by provider (pie)
    dashboard.add_pie_chart(
        "ai_gateway_usage", "*", "status", "COUNT",
        title="Success vs Error",
        position={"x": 0, "y": 10, "width": 3, "height": 5},
    )

    # Latency trend over time
    dashboard.add_line_chart(
        "ai_gateway_usage", "request_date", "request_latency_ms", "AVG",
        title="Avg Latency Trend (ms)",
        position={"x": 3, "y": 10, "width": 3, "height": 5},
        color_field="provider",
    )

    # Token throughput
    dashboard.add_line_chart(
        "ai_gateway_usage", "request_date", "total_token_count", "SUM",
        title="Daily Token Throughput",
        position={"x": 0, "y": 15, "width": 6, "height": 4},
        color_field="provider",
    )

    # =========================================================================
    # PAGE 3: Routing & A/B Tests
    # =========================================================================
    dashboard.add_page("Routing & A/B Tests")

    # Filters (date range is global from Page 1)
    dashboard.add_filter_dropdown(
        "routing_data", "endpoint_name", "Endpoint",
        position={"x": 0, "y": 0, "width": 2, "height": 1},
        multi_select=True,
    )

    # Traffic split visualization
    dashboard.add_pie_chart(
        "routing_data", "*", "routed_to", "COUNT",
        title="Traffic Split by Served Model",
        position={"x": 0, "y": 1, "width": 3, "height": 5},
    )

    # Latency by routed model
    dashboard.add_bar_chart(
        "routing_data", "routed_to", "request_latency_ms", "AVG",
        title="Avg Latency by Routed Model (ms)",
        position={"x": 3, "y": 1, "width": 3, "height": 5},
        colors=["#4285F4", "#FF6B35"],
    )

    # Routing decisions over time
    dashboard.add_line_chart(
        "routing_data", "request_date", "*", "COUNT",
        title="Routing Decisions Over Time",
        position={"x": 0, "y": 6, "width": 6, "height": 4},
        color_field="routed_to",
    )

    # Routing decisions table
    dashboard.add_table(
        "routing_data",
        columns=[
            {"field": "event_time", "title": "Time", "type": "datetime"},
            {"field": "endpoint_name", "title": "Endpoint"},
            {"field": "routed_to", "title": "Routed To"},
            {"field": "model_name", "title": "Model"},
            {"field": "request_latency_ms", "title": "Latency (ms)", "type": "integer"},
            {"field": "input_token_count", "title": "In Tokens", "type": "integer"},
            {"field": "output_token_count", "title": "Out Tokens", "type": "integer"},
            {"field": "status_code", "title": "Status", "type": "integer"},
        ],
        title="Routing Decisions Log",
        position={"x": 0, "y": 10, "width": 6, "height": 6},
    )

    return dashboard.to_dict()


def main():
    dashboard_dict = build_dashboard()

    output_path = Path(__file__).parent.parent / "dashboard" / "fmapi_unified_dashboard.json"
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(dashboard_dict, f, indent=2)

    print(f"Dashboard JSON written to {output_path}")
    print(f"  Pages: {len(dashboard_dict['pages'])}")
    for page in dashboard_dict["pages"]:
        print(f"    - {page['displayName']}: {len(page['layout'])} widgets")
    print(f"  Datasets: {len(dashboard_dict['datasets'])}")


if __name__ == "__main__":
    main()
