"""
evidence.py — Pre-defined evidence queries and gathering logic for the investigation layer.

The LLM never writes SQL. Each error category has a fixed set of queries that are
executed in parallel via MCP. Results are compressed into a compact text packet
that fits within phi4-mini's context window.
"""

import asyncio
from typing import Any

import mcp_client


# ---------------------------------------------------------------------------
# Shared query specs — reused across multiple categories.
# ---------------------------------------------------------------------------

_GP_QTY = {
    "label": "gp_qty",
    "database": "IntegrationDB",
    "sql": (
        "SELECT QTYONHND, ATYALLOC, QTYCOMTD "
        "FROM dbo.IV00102 "
        "WHERE RTRIM(ITEMNMBR)='{part}' AND RTRIM(LOCNCODE)='{location}'"
    ),
}

_TRAKKER_QTY = {
    "label": "trakker_qty",
    "database": "T2Online",
    "sql": (
        "SELECT IqtQtyOnHand, IqtQtyConsume "
        "FROM dbo.InventQuantities "
        "WHERE IqtPartNumber='{part}' AND IqtLocationCode='{location}'"
    ),
}

# ---------------------------------------------------------------------------
# Evidence query definitions — one list per error category.
# Each entry: label, database, sql (with {part}, {location}, {company_db} placeholders),
# and a format hint for compression.
# ---------------------------------------------------------------------------

EVIDENCE_QUERIES: dict[str, list[dict]] = {
    "QTYFULFI_STALE": [
        _GP_QTY,
        {
            "label": "open_orders",
            "database": "IntegrationDB",
            "sql": (
                "SELECT TOP 5 SOPNUMBE, QUANTITY, ATYALLOC "
                "FROM dbo.SOP10200 "
                "WHERE RTRIM(ITEMNMBR)='{part}' AND RTRIM(LOCNCODE)='{location}' "
                "AND QUANTITY > 0"
            ),
        },
        _TRAKKER_QTY,
    ],

    "STUCK_PROCESSING": [
        _GP_QTY,
        {
            "label": "intercompany",
            "database": "Inventory",
            "sql": (
                "SELECT TOP 5 ItPKey, ItGPDocID, ItIntegrationStatusID, ItQty, ItProcessDate "
                "FROM dbo.IntegrationTransactions "
                "WHERE ItPartNumber='{part}' AND ItOrigin='{location}' "
                "AND ItGPDocID LIKE 'TINV%' "
                "ORDER BY ItProcessDate DESC"
            ),
        },
        {
            "label": "other_statuses",
            "database": "Inventory",
            "sql": (
                "SELECT ItIntegrationStatusID, COUNT(*) AS cnt "
                "FROM dbo.IntegrationTransactions "
                "WHERE ItPartNumber='{part}' AND ItOrigin='{location}' "
                "AND ItGPDocID LIKE 'TMIN%' "
                "GROUP BY ItIntegrationStatusID"
            ),
        },
    ],

    "QTY_SHORTAGE": [
        _GP_QTY,
        _TRAKKER_QTY,
        {
            "label": "tinv_pinv_history",
            "database": "Inventory",
            "sql": (
                "SELECT TOP 5 ItGPDocID, ItQty, ItIntegrationStatusID, ItProcessDate "
                "FROM dbo.IntegrationTransactions "
                "WHERE ItPartNumber='{part}' AND ItOrigin='{location}' "
                "AND ItGPDocID IN (SELECT ItGPDocID FROM dbo.IntegrationTransactions "
                "    WHERE ItGPDocID LIKE 'TINV%' OR ItGPDocID LIKE 'PINV%') "
                "ORDER BY ItProcessDate DESC"
            ),
        },
        {
            "label": "rinv_history",
            "database": "Inventory",
            "sql": (
                "SELECT TOP 3 ItPKey, ItQty, ItIntegrationStatusID, ItProcessDate "
                "FROM dbo.IntegrationTransactions "
                "WHERE ItGPDocID LIKE 'RINV%' "
                "AND ItPartNumber='{part}' AND ItOrigin='{location}' "
                "ORDER BY ItProcessDate DESC"
            ),
        },
    ],

    "QTY_SHORTAGE_RINV": [
        _GP_QTY,
        _TRAKKER_QTY,
        {
            "label": "rinv_detail",
            "database": "Inventory",
            "sql": (
                "SELECT TOP 5 ItPKey, ItGPDocID, ItQty, ItIntegrationStatusID, ItProcessDate "
                "FROM dbo.IntegrationTransactions "
                "WHERE ItGPDocID LIKE 'RINV%' "
                "AND ItPartNumber='{part}' AND ItOrigin='{location}' "
                "ORDER BY ItProcessDate DESC"
            ),
        },
    ],

    "TICKET_OPEN": [
        {
            "label": "ticket_state",
            "database": "T2Online",
            "sql": (
                "SELECT tcm.TcaPKey, tcm.TcaCallDate, tcp.TcpConsumed "
                "FROM dbo.TicketCallMain tcm "
                "JOIN dbo.TicketPartsMain tcp ON tcp.TcaPKey = tcm.TcaPKey "
                "WHERE tcp.TcpPKey = {part_line_id}"
            ),
        },
    ],

    "NOT_SAFE": [
        _GP_QTY,
        _TRAKKER_QTY,
        {
            "label": "all_it_records",
            "database": "Inventory",
            "sql": (
                "SELECT TOP 5 ItGPDocID, ItQty, ItIntegrationStatusID, ItProcessDate "
                "FROM dbo.IntegrationTransactions "
                "WHERE ItPartNumber='{part}' AND ItOrigin='{location}' "
                "ORDER BY ItProcessDate DESC"
            ),
        },
    ],

    "CONTRACT_LOCATION": [
        _GP_QTY,
        {
            "label": "acq_info",
            "database": "T2Online",
            "sql": (
                "SELECT AcqName, DbName, AcqHWSStockLocation "
                "FROM dbo.AcqAcquisitionLookup "
                "WHERE DbName='{company_db}'"
            ),
        },
    ],

    "OTHER": [
        _GP_QTY,
        {
            "label": "all_it_records",
            "database": "Inventory",
            "sql": (
                "SELECT TOP 5 ItGPDocID, ItQty, ItIntegrationStatusID, ItLongError, ItProcessDate "
                "FROM dbo.IntegrationTransactions "
                "WHERE ItPartNumber='{part}' AND ItOrigin='{location}' "
                "ORDER BY ItProcessDate DESC"
            ),
        },
    ],

    "NOT_INTEGRATED": [
        _GP_QTY,
        _TRAKKER_QTY,
        {
            "label": "any_it_record",
            "database": "Inventory",
            "sql": (
                "SELECT TOP 3 ItGPDocID, ItQty, ItIntegrationStatusID, ItProcessDate "
                "FROM dbo.IntegrationTransactions "
                "WHERE TicketLineItemID = {part_line_id} "
                "ORDER BY ItProcessDate DESC"
            ),
        },
    ],

    "QTYFULFI": [
        _GP_QTY,
        {
            "label": "open_orders",
            "database": "IntegrationDB",
            "sql": (
                "SELECT TOP 5 SOPNUMBE, QUANTITY, ATYALLOC "
                "FROM dbo.SOP10200 "
                "WHERE RTRIM(ITEMNMBR)='{part}' AND RTRIM(LOCNCODE)='{location}' "
                "AND QUANTITY > 0"
            ),
        },
        {
            "label": "status3_rinv",
            "database": "Inventory",
            "sql": (
                "SELECT TOP 5 ItPKey, ItGPDocID, ItQty, ItProcessDate "
                "FROM dbo.IntegrationTransactions "
                "WHERE ItGPDocID LIKE 'RINV%' "
                "AND ItPartNumber='{part}' AND ItOrigin='{location}' "
                "AND ItIntegrationStatusID = 3 "
                "ORDER BY ItProcessDate DESC"
            ),
        },
    ],
}


# ---------------------------------------------------------------------------
# Fast-path deterministic checks — skip LLM when evidence is unambiguous.
# Returns a verdict dict or None if LLM investigation is needed.
# ---------------------------------------------------------------------------

def check_fast_path(category: str, evidence: dict[str, Any], row: dict) -> dict | None:
    """
    Deterministic confirmation rules. Returns a verdict dict if the evidence
    is unambiguous, or None if the LLM should investigate.
    """
    needed = row.get("QuantityNeeded") or 0

    if category == "QTYFULFI_STALE":
        gp = evidence.get("gp_qty", [])
        sop = evidence.get("open_orders", [])
        if gp:
            gp_row = gp[0]
            on_hand = _num(gp_row.get("QTYONHND", 0))
            alloc = _num(gp_row.get("ATYALLOC", 0))
            available = on_hand - alloc
            if available >= needed and alloc == 0 and len(sop) == 0:
                return {
                    "verdict": "CONFIRM",
                    "reason": f"GP has {on_hand} on hand, 0 allocated, no open SOP orders. Safe to reset.",
                    "new_category": "",
                }
            if available < needed:
                deficit = max(0, needed - on_hand)
                return {
                    "verdict": "RECLASSIFY",
                    "reason": f"GP qty dropped since audit. QTYONHND={on_hand}, need {needed}, deficit={deficit}.",
                    "new_category": "QTY_SHORTAGE",
                }
            if alloc > 0:
                return {
                    "verdict": "RECLASSIFY",
                    "reason": f"ATYALLOC={alloc} now > 0. Genuine allocation lock.",
                    "new_category": "QTYFULFI",
                }
        # If GP returned no rows, can't confirm — need LLM
        return None

    if category == "STUCK_PROCESSING":
        gp = evidence.get("gp_qty", [])
        if gp:
            gp_row = gp[0]
            on_hand = _num(gp_row.get("QTYONHND", 0))
            alloc = _num(gp_row.get("ATYALLOC", 0))
            intercompany = evidence.get("intercompany", [])
            if on_hand >= needed and alloc == 0 and len(intercompany) == 0:
                return {
                    "verdict": "CONFIRM",
                    "reason": f"GP has {on_hand} on hand, 0 allocated, no intercompany transfers. Safe to reset.",
                    "new_category": "",
                }
        return None

    # No fast-path for other categories
    return None


def _num(val) -> float:
    """Safely convert a value to float."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Evidence gathering — runs queries in parallel via MCP, returns results dict.
# ---------------------------------------------------------------------------

async def _run_query(label: str, sql: str, database: str) -> tuple[str, list[dict]]:
    """Execute a single query via MCP and return (label, rows)."""
    try:
        raw = await mcp_client.call_tool("execute_query", {"query": sql, "database": database})
        return label, mcp_client.parse_rows(raw)
    except Exception:
        return label, []


async def gather_evidence(row: dict, category: str) -> dict[str, list[dict]]:
    """
    Run all evidence queries for the given category in parallel.
    Returns {label: [row_dicts]} for each query.
    """
    specs = EVIDENCE_QUERIES.get(category, [])
    if not specs:
        return {}

    part = (row.get("PartNumber") or "").replace("'", "''")
    location = (row.get("Location") or "").replace("'", "''")
    company_db = (row.get("Company") or "").replace("'", "''")
    part_line_id = row.get("PartLineID") or 0

    tasks = []
    for spec in specs:
        sql = spec["sql"].format(
            part=part,
            location=location,
            company_db=company_db,
            part_line_id=part_line_id,
        )
        tasks.append(_run_query(spec["label"], sql, spec["database"]))

    results = await asyncio.gather(*tasks)
    return dict(results)


# ---------------------------------------------------------------------------
# Evidence formatting — compress query results into a compact text packet.
# ---------------------------------------------------------------------------

def format_evidence(row: dict, evidence: dict[str, list[dict]]) -> str:
    """
    Compress evidence results into a compact text packet for the LLM.
    Target: ~150 tokens.
    """
    lines = []

    # Row context
    error = (row.get("IntegrationError") or "")[:200]
    lines.append(
        f"ROW: Part={row.get('PartNumber', '?')} "
        f"Location={row.get('Location', '?')} "
        f"Needed={row.get('QuantityNeeded', '?')} "
        f"DaysOpen={row.get('DaysOpen', '?')}"
    )
    lines.append(f"     Error=\"{error}\"")
    lines.append(
        f"     Audit: {row.get('ErrorCategory', '?')} -> {row.get('FixType', '?')}"
    )
    lines.append("")
    lines.append("EVIDENCE:")

    for label, rows in evidence.items():
        if not rows:
            lines.append(f"  {label}: (no data)")
            continue

        if label == "gp_qty":
            r = rows[0]
            lines.append(
                f"  GP: QTYONHND={r.get('QTYONHND', 0)}, "
                f"ATYALLOC={r.get('ATYALLOC', 0)}, "
                f"QTYCOMTD={r.get('QTYCOMTD', 0)}"
            )
        elif label == "open_orders":
            lines.append(f"  SOP: {len(rows)} open order(s)")
            for r in rows[:3]:
                lines.append(
                    f"    SOPNUMBE={r.get('SOPNUMBE', '?')}, "
                    f"QTY={r.get('QUANTITY', 0)}, "
                    f"ALLOC={r.get('ATYALLOC', 0)}"
                )
        elif label == "trakker_qty" and rows:
            r = rows[0]
            lines.append(
                f"  Trakker: OnHand={r.get('IqtQtyOnHand', 0)}, "
                f"Consume={r.get('IqtQtyConsume', 0)}"
            )
        elif label == "intercompany":
            lines.append(f"  Intercompany TINVs: {len(rows)} record(s)")
            for r in rows[:2]:
                lines.append(
                    f"    DocID={r.get('ItGPDocID', '?')}, "
                    f"Status={r.get('ItIntegrationStatusID', '?')}, "
                    f"Qty={r.get('ItQty', 0)}"
                )
        elif label == "other_statuses":
            parts = [f"Status{r.get('ItIntegrationStatusID', '?')}={r.get('cnt', 0)}" for r in rows]
            lines.append(f"  TMIN status breakdown: {', '.join(parts)}")
        elif label in ("tinv_pinv_history", "rinv_history", "rinv_detail", "all_it_records"):
            lines.append(f"  {label}: {len(rows)} record(s)")
            for r in rows[:3]:
                doc = r.get("ItGPDocID", "?")
                qty = r.get("ItQty", 0)
                status = r.get("ItIntegrationStatusID", "?")
                date = str(r.get("ItProcessDate", "?"))[:10]
                lines.append(f"    DocID={doc}, Qty={qty}, Status={status}, Date={date}")
        elif label == "status3_rinv":
            lines.append(f"  Status-3 RINVs: {len(rows)} record(s)")
            for r in rows[:3]:
                lines.append(
                    f"    ItPKey={r.get('ItPKey', '?')}, "
                    f"Qty={r.get('ItQty', 0)}, "
                    f"Date={str(r.get('ItProcessDate', '?'))[:10]}"
                )
        elif label == "ticket_state" and rows:
            r = rows[0]
            lines.append(
                f"  Ticket: TcaPKey={r.get('TcaPKey', '?')}, "
                f"Date={str(r.get('TcaCallDate', '?'))[:10]}, "
                f"Consumed={r.get('TcpConsumed', '?')}"
            )
        elif label == "acq_info" and rows:
            r = rows[0]
            lines.append(
                f"  Entity: {r.get('AcqName', '?')}, "
                f"DB={r.get('DbName', '?')}, "
                f"StockLoc={r.get('AcqHWSStockLocation', '?')}"
            )
        elif label == "any_it_record":
            lines.append(f"  IT records for part line: {len(rows)} record(s)")
            for r in rows[:3]:
                doc = r.get("ItGPDocID", "?")
                status = r.get("ItIntegrationStatusID", "?")
                date = str(r.get("ItProcessDate", "?"))[:10]
                lines.append(f"    DocID={doc}, Status={status}, Date={date}")
        else:
            # Generic fallback
            lines.append(f"  {label}: {len(rows)} row(s)")
            if rows:
                lines.append(f"    {rows[0]}")

    return "\n".join(lines)
