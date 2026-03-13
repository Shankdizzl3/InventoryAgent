# InventoryAgent

Inventory reconciliation toolset for field service operations.
Finds maintenance ticket parts that failed to consume into GP, classifies root causes,
and outputs findings to Excel for human review.

## Components

| File | Purpose |
|------|---------|
| `audit.py` | **Phase 1-2.** Deterministic audit — finds unconsumed parts, classifies errors, writes Excel with Summary/Detail/Staged Fixes tabs. |
| `investigate.py` | **Phase 4.** Reads audit Excel, gathers evidence per row, runs fast-path or LLM investigation, writes `investigation_YYYYMMDD.xlsx`. |
| `evidence.py` | Per-category evidence queries, parallel MCP gathering, fast-path rules, evidence text formatting. |
| `llm_utils.py` | Shared Ollama client setup, single-turn LLM call, verdict parser. |
| `playbooks/` | 10 decision-tree files (one per error category, ~400 tokens each) that guide the LLM's verdict. |
| `agent.py` | Interactive LLM agent for ad-hoc SQL investigation across all 3 databases. |
| `mcp_client.py` | Async MCP client — proxies DB queries through mssql-mcp-server. Includes `parse_rows()` for shared result parsing. |

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
- **Summary** tab: error category counts + triage fix-type breakdown
- **Detail** tab: one row per unconsumed ticket part with GP qty, deficit, DaysOpen, and recommended action
- **Staged Fixes** tab: auto-fixable rows (RESET_TO_PENDING, CYCLE_COUNT_TBD) sorted oldest-first

## Running the investigation (Phase 4)

```
python investigate.py
python investigate.py path/to/audit_YYYYMMDD_HHMMSS.xlsx
```

Reads the most recent audit Excel (or a specific file), gathers evidence per row via parallel SQL queries, applies fast-path deterministic rules where possible, and falls back to LLM (phi4-mini) for ambiguous cases. Produces `investigation_YYYYMMDD_HHMMSS.xlsx`:
- **Investigation Summary** tab: verdict counts (CONFIRM/ESCALATE/RECLASSIFY/UNKNOWN), method counts (fast-path/llm), reclassification breakdown
- **Investigation Detail** tab: original row data + LLMVerdict, LLMReason, LLMNewCategory, InvestigationMethod

## Running the interactive agent

```
python agent.py
```

Type SQL questions in plain English. The agent translates to SQL, queries the DB via MCP,
and summarizes results. Type `exit` to quit.

## Error categories (audit.py)

| Category | Meaning | Fix Type |
|----------|---------|----------|
| `QTYFULFI_STALE` | Stale failure; GP has stock, no allocation | RESET_TO_PENDING |
| `STUCK_PROCESSING` | StatusID=5, stuck in processing | RESET_TO_PENDING |
| `QTY_SHORTAGE` | GP qty genuinely insufficient | CYCLE_COUNT_TBD |
| `QTY_SHORTAGE_RINV` | RINV removal caused shortage | CYCLE_COUNT_TBD |
| `TICKET_OPEN` | Ticket still open in Trakker | HUMAN_ACTION |
| `NOT_SAFE` | Integration flagged inconsistent state | HUMAN_ACTION |
| `QTYFULFI` | Stock exists but allocated (ATYALLOC lock) | HUMAN_ACTION |
| `CONTRACT_LOCATION` | Part must move to contract location | HUMAN_ACTION |
| `NOT_INTEGRATED` | No integration record exists | HUMAN_ACTION |
| `OTHER` | Unrecognized error | HUMAN_ACTION |
