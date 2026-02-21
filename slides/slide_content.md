# Foundation Model API: One Gateway, Every Model

## Slide 1: Title

**Foundation Model API**
One Gateway, Every Model

_Databricks as the unified platform for foundation model serving_

**Speaker notes:** This demo shows how Databricks Foundation Model API eliminates the multi-provider fragmentation problem. We'll show all three major model families — Claude, GPT, and Gemini — served natively through a single gateway, with unified billing, observability, and governance.

---

## Slide 2: The Multi-Model Reality

**Title:** The Multi-Model Reality

Every enterprise uses multiple models. Today that means:

- **N providers** — separate accounts for Anthropic, OpenAI, Google
- **N bills** — reconciling usage across provider dashboards
- **N access controls** — different IAM, different keys, different policies
- **N logging systems** — no unified view of who used what, when
- **N upgrade paths** — swapping models requires code changes

_Visual: Diagram showing 3 cloud provider logos each with separate billing, auth, and logging icons — a tangled mess._

**Speaker notes:** Start with the pain. Every customer we talk to uses at least 2-3 model providers. That creates operational overhead: separate billing, separate governance, separate upgrade paths. The question isn't "which model is best" — it's "how do I manage all of them?"

---

## Slide 3: One Gateway, Every Model

**Title:** One Gateway, Every Model

Databricks Foundation Model API serves all major model families natively:

| Provider | Models | Competitive Differentiator |
|----------|--------|---------------------------|
| **Anthropic** | Claude Opus 4.6, Opus 4.5, Sonnet, Haiku | Not on Vertex |
| **OpenAI** | GPT-5.2, GPT-4.1, o3 | Not on Bedrock, not on Vertex |
| **Google** | Gemini 3.1 Pro, Gemini 2.5 | Not on Bedrock |
| **Meta** | Llama 3.3, Llama 4 | Open-source, optimized serving |
| **BYOK** | Any model via external endpoints | Bring your own API key |

One API (OpenAI-compatible). One SDK. One auth token. One bill.

**Speaker notes:** This is the sharpest differentiator. Bedrock doesn't have OpenAI or Gemini. Vertex doesn't have OpenAI. Only Databricks gives you all three major families through a single gateway. And it's OpenAI-spec compatible, so existing code works with zero changes.

---

## Slide 4: Every Request, One View

**Title:** Every Request, One View

Unified observability across all models:

- **system.serving.endpoint_usage** — request counts, tokens, latency, users
- **system.billing.usage** — cost by provider, by endpoint, by user
- **system.ai_gateway.usage** — latency, TTFB, routing decisions, errors
- **Inference tables** — full request/response payloads for eval and audit

_Visual: Screenshot of the FMAPI Unified Dashboard — 3-page Lakeview dashboard showing all providers in one view._

**Speaker notes:** Every request — whether from a production app, Claude Code, or Codex CLI — flows through the same gateway and into the same system tables. One dashboard shows cost, latency, and usage across all providers. No stitching together multiple dashboards.

---

## Slide 5: Traffic Routing, A/B Testing, Fallback

**Title:** Traffic Routing, A/B Testing, Fallback

AI Gateway policies give you production-grade model management:

- **A/B testing** — Split traffic (e.g., 70% Opus 4.6 / 30% Opus 4.5) and compare quality
- **Fallback** — If primary model errors, automatically route to backup
- **Rate limiting** — Control request rates per user or per endpoint
- **Routing visibility** — `routing_information` in system tables shows which model handled each request

_Visual: Flow diagram showing request entering gateway, splitting to two model versions, with routing_information logged._

**Speaker notes:** Demo this live. A new model drops — you don't have to choose immediately. Run both versions side-by-side, compare quality metrics in the inference tables, then shift traffic when you're confident. The routing_information field gives you full visibility into every routing decision.

---

## Slide 6: Inference Follows the Platform

**Title:** Inference Follows the Platform

Data proximity enables evaluation without data movement:

- Inference table outputs live in the same lakehouse as your ground truth data
- JOIN model outputs with evaluation datasets in a single SQL query
- No ETL, no data export, no separate eval pipeline
- Unity Catalog governance applies to inference data too

```sql
SELECT gt.prompt, gt.expected_response, inf.actual_response
FROM evaluation_ground_truth gt
JOIN inference_table inf ON gt.prompt = inf.prompt
```

**Speaker notes:** This is the "data proximity" argument. When inference outputs land in Delta tables next to your evaluation data, model eval becomes a SQL query — not a pipeline. This is something you simply can't do when model inference is outside the platform.

---

## Slide 7: Developer Tools & Managed MCPs

**Title:** Developer Tools & Managed MCPs

Same governance for production and development:

- **Claude Code** — Set `ANTHROPIC_BASE_URL` to your Databricks endpoint
- **Codex CLI** — Set `OPENAI_BASE_URL` to your Databricks endpoint
- **Managed MCPs** — Genie, UC Functions, Vector Search as MCP servers
- Every developer request appears in the same system tables

_Visual: Developer laptop icon connected to Databricks gateway, which connects to system tables and MCP servers._

**Speaker notes:** Brief aside — show the env vars, make one request, show it in the system tables. Then show managed MCPs: Genie for natural language queries, UC Functions for registered functions, Vector Search for RAG. The model is interchangeable; the data connections are the durable value.

---

## Slide 8: Without vs. With Databricks

**Title:** The Platform Difference

| Capability | Without Databricks | With Databricks |
|-----------|-------------------|-----------------|
| **Model access** | Separate account per provider | One gateway, all providers |
| **Billing** | Reconcile N provider bills | One unified bill |
| **Governance** | Different IAM per provider | Unity Catalog + system tables |
| **Observability** | Stitch together dashboards | One Lakeview dashboard |
| **A/B testing** | Build custom routing layer | Built-in traffic config |
| **Evaluation** | Export data, run external pipeline | SQL JOIN in lakehouse |
| **Developer tools** | Each tool has own billing | Same gateway, same governance |
| **Model upgrades** | Code changes per consumer | Update endpoint, done |

**Speaker notes:** Close with the summary table. This isn't about any one model being better — it's about the platform making every model better. Inference follows the platform because the platform has the data, the governance, and the operational tooling.
