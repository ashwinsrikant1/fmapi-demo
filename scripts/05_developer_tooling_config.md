# Scene 5: Developer Tooling Configuration

> **Key message:** Same governance, same billing, whether the request comes from a production app or a developer's IDE.

## Claude Code

Point Claude Code at your Databricks serving endpoint:

```bash
# In your shell profile (~/.zshrc or ~/.bashrc):
export ANTHROPIC_BASE_URL="https://fevm-demo-classic.cloud.databricks.com/serving-endpoints/demo-claude-opus-4-6/anthropic"
export ANTHROPIC_AUTH_TOKEN="dapi..."  # Your Databricks PAT
```

Then use Claude Code normally — every request routes through Databricks and appears in the same system tables.

## Codex CLI (OpenAI)

```bash
export OPENAI_BASE_URL="https://fevm-demo-classic.cloud.databricks.com/serving-endpoints"
export OPENAI_API_KEY="dapi..."  # Your Databricks PAT
```

## Verify Requests in System Tables

After making a few requests from Claude Code or Codex, run this SQL to confirm they appear:

```sql
-- Requests from developer tools show up in the same system tables
SELECT
    request_time,
    endpoint_name,
    requester,
    status_code,
    input_token_count,
    output_token_count
FROM system.serving.endpoint_usage u
JOIN system.serving.served_entities e
    ON u.served_entity_id = e.served_entity_id
WHERE e.endpoint_name IN ('demo-claude-opus-4-6', 'demo-gpt-5-2')
    AND request_time >= CURRENT_TIMESTAMP - INTERVAL 1 HOUR
ORDER BY request_time DESC
LIMIT 20;
```

## Demo Talking Points

1. **No code changes** — just set environment variables
2. **Same billing** — developer usage rolls up to the same workspace billing
3. **Same governance** — every request logged in system tables with user identity
4. **Same rate limits** — AI Gateway policies apply to developer tools too
5. **Seamless upgrades** — when a new model version drops, update the endpoint once; every developer gets it automatically

## Workspace-Specific URLs

| Workspace | Claude Code `ANTHROPIC_BASE_URL` |
|-----------|----------------------------------|
| fevm-demo-classic | `https://fevm-demo-classic.cloud.databricks.com/serving-endpoints/demo-claude-opus-4-6/anthropic` |
| e2-demo-field-eng | `https://e2-demo-field-eng.cloud.databricks.com/serving-endpoints/demo-claude-opus-4-6/anthropic` |
