# Foundation Model API Demo

**One Gateway, Every Model** — Databricks as the unified platform for foundation model serving.

This demo shows how Databricks Foundation Model API serves all three major model families (Anthropic, OpenAI, Google) natively through a single gateway, with unified billing, observability, governance, and routing.

## Competitive Differentiator

| Provider | Databricks | AWS Bedrock | GCP Vertex |
|----------|:----------:|:-----------:|:----------:|
| Anthropic (Claude) | Yes | Yes | No |
| OpenAI (GPT) | Yes | No | No |
| Google (Gemini) | Yes | No | Yes |

Only Databricks gives you all three.

## Prerequisites

- UC-enabled Databricks workspace (tested on `fevm-demo-classic` and `e2-demo-field-eng`)
- SQL warehouse (Serverless recommended)
- Databricks CLI configured with a profile
- Python 3.10+
- Databricks PAT (personal access token)

## Quick Setup

```bash
# 1. Clone the repo
git clone https://github.com/ashwinsrikant1/fmapi-demo.git
cd fmapi-demo

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp config.yaml.template config.yaml
# Edit config.yaml with your workspace, warehouse, and token

# 4. Create endpoints (takes 10-15 min for provisioning)
python3 scripts/01_endpoint_setup.py

# 5. Test — see all three models respond to the same prompt
python3 scripts/02_test_requests.py

# 6. Populate system tables (run 30+ min before demo)
python3 scripts/02_test_requests.py --batch

# 7. Set up A/B routing
python3 scripts/03_ab_test_routing.py

# 8. Deploy dashboard
python3 scripts/deploy_dashboard.py --config config.yaml
```

## Demo Flow (~25 min)

### Act 1: One Gateway, Every Model (~15 min)

#### Scene 1: The Problem (Slides)
- Show slide 2: "The Multi-Model Reality" — N providers, N bills, N logs

#### Scene 2: All Three Families (Live)
```bash
python3 scripts/02_test_requests.py
```
- ONE OpenAI SDK client hits Claude, GPT, and Gemini
- Same auth, same API, same code — different providers
- Show version optionality: Opus 4.5 vs 4.6

#### Scene 3: Unified Dashboard (Live)
- Open the deployed Lakeview dashboard
- Page 1 "Gateway Overview": requests by provider, cost by provider, usage trends
- Show system tables: `system.serving.endpoint_usage`, `system.billing.usage`

#### Scene 4: A/B Testing & Routing (Live)
```bash
python3 scripts/03_ab_test_routing.py
```
- Traffic split: 70% Opus 4.6 / 30% Opus 4.5
- Show routing distribution in output
- Dashboard Page 3: routing decisions, traffic split visualization
- Query `routing_information` in system tables

#### Scene 4b: Inference Table Evaluation (Live)
- Run SQL from `scripts/04_inference_table_evaluation.sql`
- JOIN inference outputs with ground truth table
- "Your inference data lives next to your eval data — model eval is a SQL query"

### Act 2: Your Data, Your Models, Your Tools (~10 min)

#### Scene 5: Developer Tooling (Brief)
- Show Claude Code env vars (see `scripts/05_developer_tooling_config.md`)
- Make a request, show it in system tables
- "Same governance whether request comes from production or developer IDE"

#### Scene 6: Managed MCPs (Live)
- See `scripts/06_mcp_demo.md` for setup
- Show Genie MCP: ask a data question, get SQL + results
- "The model is interchangeable; the data connections are the durable value"

### Closing
- Show slide 8: "Without vs. With Databricks" comparison table

## Timing Notes

| Data Source | Latency After Requests |
|------------|----------------------|
| `system.serving.endpoint_usage` | 5-30 minutes |
| `system.billing.usage` | Up to 24 hours |
| `system.ai_gateway.usage` | 5-30 minutes |
| Inference tables | Up to 1 hour |

**Run `02_test_requests.py --batch` at least 30 minutes before the demo.**
Enable inference tables and send test requests the day before if possible.

## Switching Workspaces

Edit `config.yaml` to point to a different workspace:

```yaml
# fevm-demo-classic (personal)
workspace_host: "https://fevm-demo-classic.cloud.databricks.com"
databricks_cli_profile: "fevm-demo-classic"

# e2-demo-field-eng (shared)
# workspace_host: "https://e2-demo-field-eng.cloud.databricks.com"
# databricks_cli_profile: "e2-demo-field-eng"
```

## Repo Structure

```
fmapi-demo/
├── README.md                              # This file
├── requirements.txt                       # Python dependencies
├── config.yaml.template                   # Config template
├── scripts/
│   ├── 01_endpoint_setup.py               # Create serving endpoints
│   ├── 02_test_requests.py                # Send test requests (side-by-side + batch)
│   ├── 03_ab_test_routing.py              # A/B traffic split demo
│   ├── 04_inference_table_evaluation.sql  # Eval queries for inference tables
│   ├── 05_developer_tooling_config.md     # Claude Code / Codex CLI setup
│   ├── 06_mcp_demo.md                     # Managed MCP setup + examples
│   ├── build_dashboard.py                 # Regenerate dashboard JSON
│   └── deploy_dashboard.py               # Deploy dashboard to workspace
├── dashboard/
│   └── fmapi_unified_dashboard.json       # 3-page Lakeview dashboard
├── slides/
│   └── slide_content.md                   # Slide-by-slide content
└── lib/
    └── lakeview_builder.py                # Dashboard builder class
```

## Cleanup

```bash
# Delete endpoints (optional — they don't cost when idle with serverless)
databricks serving-endpoints delete demo-claude-opus-4-6 --profile fevm-demo-classic
databricks serving-endpoints delete demo-gpt-5-2 --profile fevm-demo-classic
databricks serving-endpoints delete demo-gemini-3-1-pro --profile fevm-demo-classic
databricks serving-endpoints delete demo-claude-opus-4-5 --profile fevm-demo-classic
databricks serving-endpoints delete demo-claude-ab-test --profile fevm-demo-classic

# Delete ground truth table
# DROP TABLE IF EXISTS main.fmapi_demo.evaluation_ground_truth;
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Endpoint stuck in NOT_READY | Check workspace quota; try a different model size |
| System tables empty | Wait 30 min; check `system.serving.endpoint_usage` directly |
| Inference tables empty | Wait 1 hour; verify `ai_gateway.inference_table_config.enabled = true` |
| `system.ai_gateway.usage` not found | AI Gateway system tables may be in Preview; check workspace feature flags |
| OpenAI SDK auth error | Verify `databricks_token` in config.yaml; ensure PAT has serving permissions |
| Dashboard shows no data | Filters may be too narrow; try removing date filter or expanding range |
