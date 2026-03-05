# InventoryAgent

Inventory reconciliation toolset for field service operations.
Finds maintenance ticket parts that failed to consume into GP, classifies root causes,
and outputs findings to Excel for human review.

## Components

| File | Purpose |
|------|---------|
| `audit.py` | **Primary tool.** Deterministic audit script — no LLM. Runs runbook queries, classifies errors, writes Excel report. |
| `agent.py` | Interactive LLM agent (Ollama/phi4-mini) for ad-hoc SQL investigation. |
| `mcp_client.py` | Async MCP client that proxies DB queries through the mssql-mcp-server. |

## Prerequisites

### 1. Ollama

```
winget install Ollama.Ollama
ollama pull phi4-mini
ollama serve
```

### 2. MCP Server (mssql-mcp-server)

The MCP server is a separate Node.js project. Build it once:

```
cd path\to\mssql-mcp-server
npm install
npm run build
```

Create its `.env` with your SQL Server credentials (see that repo's README).

### 3. Python dependencies

```
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and set:

```
MCP_SERVER_PATH=C:\path\to\mssql-mcp-server\dist\index.js
OLLAMA_MODEL=phi4-mini
OLLAMA_BASE_URL=http://localhost:11434
```

## Running the audit

```
python audit.py
```

Produces `audit_YYYYMMDD_HHMMSS.xlsx` in the project directory.
- **Summary** tab: error category counts
- **Detail** tab: one row per unconsumed ticket part with GP qty, deficit, and recommended action

## Running the interactive agent

```
python agent.py
```

Type SQL questions in plain English. The agent translates to SQL, queries the DB via MCP,
and summarizes results. Type `exit` to quit.

## Error categories (audit.py)

| Category | Meaning |
|----------|---------|
| `NOT_INTEGRATED` | No integration record exists — manually trigger consumption |
| `STUCK_PROCESSING` | StatusID=5, stuck in processing — check IntercompanyTransactions |
| `QTYFULFI` | Stock exists but allocated (ATYALLOC lock) — check SOP10200 + stuck RINV |
| `QTY_SHORTAGE_RINV` | RINV removal caused shortage — Cycle Count + reprocess |
| `QTY_SHORTAGE` | GP qty genuinely insufficient — investigate TINV/PINV history |
| `OTHER` | Unrecognized error — manual review |
