# InventoryAgent — Project Roadmap & Goals

**Last updated**: 2026-03-12
**Current phase**: Phase 4 — LLM Investigation Layer (COMPLETE)

---

## Problem Statement

Maintenance ticket parts processed through Trakker (T2Online) must be "consumed" — deducted
from GP inventory via an integration pipeline that writes records to
`Inventory.dbo.IntegrationTransactions`. This pipeline fails silently. Parts get marked as
used on a ticket, the TMIN transaction is created, but the consumption never completes in GP.

The result: **GP inventory is overstated.** Parts show as available when they've already been
used. This cascades into incorrect stock replenishment decisions, inaccurate financials, and
manual reconciliation work that currently has no systematic tooling.

At any given time there are ~200 unconsumed ticket parts in various failure states across all
entities (SEI, SRVIQ, TOPG, and others), all flowing through the same
`IntegrationTransactions` table.

---

## Vision

A continuously-running agentic system that:

1. **Detects** all unconsumed ticket part failures automatically
2. **Diagnoses** the root cause of each failure using deterministic rules against live DB data
3. **Proposes** the exact SQL fix query for each record — staged for DBA review
4. **Executes** approved fixes via Admin Panel API endpoints (once panels are built)
5. **Monitors** the fix queue until the backlog reaches zero and stays there

The system runs locally on-machine. Business data never leaves the network. The LLM handles
reasoning and investigation; humans retain final approval over all write operations until the
Admin Panel integration is trusted and fully tested.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        InventoryAgent                        │
│                                                              │
│  audit.py          ──► deterministic detection engine        │
│  agent.py          ──► LLM investigation & fix proposal      │
│  mcp_client.py     ──► DB access via mssql-mcp-server (MCP)  │
│                                                              │
│  Runtime: Ollama (phi4-mini, local CPU)                      │
│  DB: SQL Server — T2Online, Inventory, IntegrationDB         │
│  Output: Excel (audit + staged fix queries)                  │
│  Future: Admin Panel API (write-back execution)              │
└─────────────────────────────────────────────────────────────┘
```

### Data flow (current)
```
SQL Server ──► mcp_client.py ──► audit.py ──► audit_YYYYMMDD.xlsx
                                               ├── Summary tab
                                               ├── Detail tab (213 rows, color-coded)
                                               └── [Staged Fixes tab — Phase 2]
```

### Data flow (target)
```
SQL Server ──► audit.py (continuous) ──► classify ──► propose fix SQL
                    │                                       │
                    └──► agent.py (LLM investigation) ◄────┘
                                   │
                                   ▼
                         Staged Fixes Excel (DBA review)
                                   │
                                   ▼ (approved)
                         Admin Panel API endpoints
                                   │
                                   ▼
                         SQL Server (write-back executed)
```

---

## Source of Truth Hierarchy

| System | Role |
|--------|------|
| `IntegrationDB.dbo.IV00102` | GP — authoritative current qty (QTYONHND, ATYALLOC) |
| `T2Online.dbo.TicketPartsMain` | Trakker — what was used on each ticket |
| `Inventory.dbo.IntegrationTransactions` | Movement audit log — all TMIN/TINV/RINV/PINV |

---

## Confirmed Schema (verified against live DB, March 2026)

### T2Online.dbo.TicketCallMain
- PK: `TcaPKey` | `TcaCallDate` | `TcaCustomerName`

### T2Online.dbo.TicketPartsMain
- PK: `TcpPKey` | FK to ticket: `TcaPKey`
- `TcpPartNumber`, `TcpQuantityOrdered`, `TcpInventoryLocation`, `TcpConsumed`

### Inventory.dbo.IntegrationTransactions
- PK: `ItPKey`
- `ItGPDocID` — TMIN=consume, TINV=transfer, RINV=removal, PINV=PO receipt
- `ItPartNumber`, `ItOrigin`, `ItQty`, `ItLongError`, `it_retry_count`, `ItProcessDate`
- `ItIntegrationStatusID` → FK to IntegrationStatusLookup.IsPKey
- `TicketLineItemID` → FK to TicketPartsMain.TcpPKey  ← primary join key
- `CompanyDatabaseName` — entity identifier (SEI, SRVIQ, TOPG, etc.)

### Inventory.dbo.IntegrationStatusLookup
- PK: `IsPKey` | `IsDescription`
- 1=Success, 2=Failure, 3=Failed Batch, 4=Pending, 5=Processing, 6=Processed But Failed Qty Update, 9=Cancelled

### IntegrationDB.dbo.IV00102
- `ITEMNMBR`, `LOCNCODE`, `QTYONHND`, `ATYALLOC`, `QTYCOMTD`

---

## Error Categories & Fix Strategy

| Category | Root Cause | Count (Mar 12) | Proposed Fix |
|----------|-----------|:--------------:|--------------|
| `QTYFULFI_STALE` | Stale failure; GP has stock, ATYALLOC=0 | **192** | UPDATE ItIntegrationStatusID=4 → reprocess via Admin Panel |
| `QTY_SHORTAGE` | GP qty genuinely zero/insufficient | 7 | Cycle Count INSERT for deficit qty, then reset to Pending |
| `STUCK_PROCESSING` | Frozen at StatusID=5 | 6 | Reset ItIntegrationStatusID=4 via Admin Panel |
| `TICKET_OPEN` | Ticket still open in Trakker | 3 | Human: close/finalize ticket, then reprocess |
| `QTY_SHORTAGE_RINV` | RINV removal caused shortage | 3 | Cycle Count INSERT, then reset to Pending |
| `CONTRACT_LOCATION` | Part must move to contract location | 1 | Human: move location in Trakker, then reprocess |
| `NOT_SAFE` | Integration flagged inconsistent state | 1 | Human: manual Trakker + GP state review |
| `QTYFULFI` | Genuine allocation lock (ATYALLOC > 0) | 0 | Investigate SOP10200 + stuck Status 3 RINV |
| `NOT_INTEGRATED` | No IT record exists | 0 | INSERT new TMIN record → reprocess |
| `OTHER` | Unrecognized error | 0 | Manual review |

**Key query notes:**
- `QUERY_FAILED_TMIN` drives from IntegrationTransactions (fast — small filtered set). Covers all failure categories.
- `QUERY_NOT_INTEGRATED` drives from T2Online with 90-day date filter + NOT EXISTS. Scoped to avoid 30s timeout on 1.1M-row TicketCallMain.
- Never drive the main query from T2Online without a date filter — causes timeout.

---

## Phased Roadmap

### Phase 1 — Detection Engine ✅ COMPLETE
> *Build a deterministic audit that reliably finds and classifies every failure.*

- [x] `audit.py` — deterministic reconciliation engine, fully async via MCP
- [x] Two-query strategy (IT-driven + T2Online 90-day scoped) — avoids 30s timeout
- [x] 9 error categories confirmed against live data (235 → 213 records across 3 runs)
- [x] QTYFULFI vs QTYFULFI_STALE split on ATYALLOC check — QTYFULFI=0 confirmed
- [x] `QTYFULFI` in error string branch also applies ATYALLOC + shortage logic
- [x] High-retry warning on RetryCount ≥ 10 appended to action text
- [x] Excel output — Summary + Detail tabs, color-coded by category, frozen header
- [x] Clean MCP session lifecycle via `close_session()` — no shutdown errors
- [x] TicketID populated from `tcp.TcaPKey`; fallback to `PartLineID` for 11 orphaned IT records
- [x] `MEMORY.md` and `ROADMAP.md` written with confirmed schema and decisions
- [x] Dead files removed (`Proof of Concept/`, `server.bat`, `docs/`, `Project Plan.md`, `inventory_tools.py`)
- [x] `agent.py` SYSTEM_PROMPT updated with real column names across all three databases
- [x] `README.md` rewritten with current setup instructions

---

### Phase 2 — Fix Query Generation ✅ COMPLETE
> *For each classified failure, generate the exact SQL fix query. Stage it in Excel for DBA review.*

- [x] `ItProcessDate` added to QUERY_FAILED_TMIN SELECT — pulled into Detail tab
- [x] `DaysOpen` calculated column (today − ItProcessDate) — age-based prioritization
- [x] `Staged Fixes` tab in Excel: Company, TicketID, PartLineID, PartNumber, Location, ErrorCategory, DaysOpen, FixType
- [x] Auto-fixable rows only, sorted by DaysOpen descending (oldest first)
- [x] Summary tab updated with FixType triage counts

---

### Phase 3 — Continuous Operation
> *Move from on-demand runs to a continuously-running background process.*

**Deliverables**:
- [ ] Configurable run interval (default: 15 minutes)
- [ ] Delta detection — only process newly failed records since last run
- [ ] Run log (`audit_log.txt`) — timestamped entry per run with category counts
- [ ] Backlog trend (`history.csv`) — append summary counts per run for charting
- [ ] `loop.py` wrapper or Windows Task Scheduler config
- [ ] Graceful connectivity loss handling — retry with backoff, log error, continue

---

### Phase 4 — LLM Investigation Layer ✅ COMPLETE
> *"Guided Investigation" pattern: deterministic evidence gathering + LLM verdict interpretation.*

- [x] `llm_utils.py` — shared Ollama client, single-turn call, verdict parser
- [x] `evidence.py` — per-category SQL queries, parallel gathering via MCP, fast-path rules, evidence formatting
- [x] `playbooks/` — 10 category-specific decision trees (~400 tokens each)
- [x] `investigate.py` — orchestrator: reads audit Excel → gathers evidence → fast-path/LLM → writes investigation Excel
- [x] Fast-path for QTYFULFI_STALE + STUCK_PROCESSING (skips LLM when evidence is unambiguous)
- [x] `agent.py` tool definitions fixed to support all 3 databases (was hardcoded to Inventory)
- [x] `agent.py` refactored to import from `llm_utils.py`

---

### Phase 5 — Admin Panel Integration
> *Replace the staged Excel approval step with direct Admin Panel API calls.*

**Deliverables**:
- [ ] Document Admin Panel API (endpoints, auth, request format)
- [ ] Build Admin Panel panels for each auto-fixable fix type (Reset to Pending, Cycle Count)
- [ ] `admin_panel_client.py` — async wrapper over Admin Panel HTTP API
- [ ] Dry-run mode: log what would be called before executing
- [ ] Full execution log: timestamp, endpoint, payload, response for every call
- [ ] All fix operations reversible or logged for manual rollback

**Gate**: Does not start until Staged Fixes Excel has been in use long enough for DBA to sign
off on automating each category.

---

### Phase 6 — Full Autonomous Loop
> *Close the loop: detect → diagnose → fix → verify → repeat.*

**Deliverables**:
- [ ] Auto-fix pipeline for QTYFULFI_STALE and STUCK_PROCESSING (highest confidence categories)
- [ ] Post-fix verification: re-query ItIntegrationStatusID after fix, confirm =1
- [ ] Escalation: if fix fails or verify fails, flag for human review
- [ ] Weekly summary: records fixed, escalated, backlog trend
- [ ] `NOT_SAFE` and `OTHER` always stay in human queue — never auto-fixed

---

## Technical Constraints

| Constraint | Detail |
|-----------|--------|
| **Local only** | Business data must never leave the machine or network. No cloud LLM API in production. |
| **Read-only DB** | All SQL Server access via mssql-mcp-server (MCP, stdio). Write-back through Admin Panel only. |
| **Hardware** | AMD Ryzen 7 5700U, 16GB RAM, CPU-only. phi4-mini (3.8B) is practical ceiling for interactive use. |
| **LLM model** | phi4-mini via Ollama. Upgrade path: Qwen2.5-7B for better reasoning when performance allows. |
| **Human approval** | Until Phase 5 is trusted, all destructive SQL reviewed and executed by DBA via Admin Panel. |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Backlog size | Zero unconsumed parts in auto-fixable categories |
| Time-to-detect | < 15 minutes from failure to audit appearance |
| Fix turnaround | QTYFULFI_STALE resolved within 1 business day of detection |
| Age visibility | Every failure shows `ItProcessDate` + `DaysOpen` |
| Classification accuracy | 0 records in `OTHER` that belong in a known category |
| False positives | 0 fix queries staged for records that are actually fine |

---

## Out of Scope

- Full Trakker vs GP history reconciliation (IV30300 vs InventHistory)
- Root cause analysis of *why* TMIN records fail upstream
- Inventory forecasting or demand planning
- Modifications to the Admin Panel codebase itself
