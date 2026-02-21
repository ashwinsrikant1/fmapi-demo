# Scene 6: Managed MCPs with Claude Code

> **Key message:** The model is interchangeable; the data connections are the durable value. Databricks provides managed MCP servers that give any AI tool secure access to your data.

## Setup: Add Managed MCP Servers

Replace `<workspace>` with your workspace URL (e.g., `fevm-demo-classic.cloud.databricks.com`).

### Genie MCP (Natural Language to SQL)

```bash
claude mcp add --transport http databricks-genie \
  "https://<workspace>/api/2.0/mcp/genie/<genie-space-id>"
```

### Unity Catalog Functions MCP

```bash
claude mcp add --transport http databricks-uc-functions \
  "https://<workspace>/api/2.0/mcp/functions/<catalog>/<schema>"
```

### Vector Search MCP

```bash
claude mcp add --transport http databricks-vector-search \
  "https://<workspace>/api/2.0/mcp/vector-search/<index-name>"
```

**Authentication:** Each MCP server uses your Databricks PAT. Set `DATABRICKS_TOKEN` in your environment or configure it in Claude Code's MCP settings.

## Example Interactions

### Genie: Query Data with Natural Language

```
You: "What are the top 5 endpoints by request count this week?"
```

Genie translates this to SQL, runs it against the warehouse, and returns results — all through the MCP protocol.

### UC Functions: Execute Registered Functions

```
You: "Calculate the risk score for customer ID 12345 using the risk_score function."
```

Claude Code discovers the function signature from Unity Catalog and calls it with the right parameters.

### Vector Search: Semantic Document Retrieval

```
You: "Find internal documents about AI governance policies."
```

Claude Code searches the vector index and returns relevant documents with similarity scores.

## Demo Flow

1. **Show the MCP config** — `claude mcp list` to show all three servers connected
2. **Genie query** — Ask a data question, show the SQL + results
3. **Key point:** "This works with ANY model — Claude, GPT, Gemini. The MCP connections are model-agnostic. Switch models, keep your data connections."

## Talking Points

- **Managed infrastructure** — Databricks hosts the MCP servers; no self-hosting required
- **Unified auth** — Same Databricks PAT for model access and data access
- **Governance preserved** — UC permissions apply; the model can only access data the user is authorized for
- **Model-agnostic** — MCP works with any AI tool that supports the protocol
- **Data proximity** — The MCP servers run next to the data; no data movement needed
