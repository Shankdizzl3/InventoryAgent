"""
audit.py — Inventory Reconciliation Walking Skeleton

Pure Python, no LLM. Connects via MCP client (mcp_client.py → mssql-mcp-server).
Runs the runbook Step 1 query to find unconsumed maintenance ticket parts, then
diagnoses each via GP qty (IV00102) and RINV history checks, classifies the error,
and writes findings to Excel with Summary + Detail tabs.

Usage:
    python audit.py
"""

import asyncio
import json
import os
from datetime import datetime

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from dotenv import load_dotenv

import mcp_client

load_dotenv()

# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

# Step 1: Pull all unconsumed maintenance ticket parts.
# Joins T2Online to get ticket/part context; OUTER APPLYs IntegrationTransactions
# + IntegrationStatusLookup to capture the latest integration attempt.
QUERY_UNCONSUMED = """
SELECT
    tcm.CallCompany                             AS Company,
    tcm.CallID                                  AS TicketID,
    tpm.PartsPartNumber                         AS PartNumber,
    tpm.PartsQtyNeeded                          AS QuantityNeeded,
    acq.AcqLocationCode                         AS Location,
    ist.IslStatusID                             AS StatusID,
    ist.IslStatusDescription                    AS StatusDescription,
    it.ItGPDocID                                AS GPDocID,
    it.ItLongError                              AS IntegrationError,
    it.it_retry_count                           AS RetryCount,
    it.ItPKey                                   AS IntegrationID
FROM T2Online.dbo.TicketCallMain tcm
JOIN T2Online.dbo.AgreeAgreementMain aam
    ON aam.AgreementID = tcm.CallAgreementID
JOIN T2Online.dbo.AcqAcquisitionLookup acq
    ON acq.AcqAgreementID = aam.AgreementID
JOIN T2Online.dbo.TicketPartsMain tpm
    ON tpm.PartsCallID = tcm.CallID
OUTER APPLY (
    SELECT TOP 1
        it2.ItPKey,
        it2.ItGPDocID,
        it2.ItLongError,
        it2.ItIntegrationStatusID,
        it2.it_retry_count
    FROM Inventory.dbo.IntegrationTransactions it2
    WHERE it2.ItGPDocID LIKE 'TMIN%'
      AND it2.ItOrigin = acq.AcqLocationCode
      AND it2.ItPartNumber = tpm.PartsPartNumber
    ORDER BY it2.ItProcessDate DESC
) it
OUTER APPLY (
    SELECT TOP 1 ist2.IslStatusID, ist2.IslStatusDescription
    FROM Inventory.dbo.IntegrationStatusLookup ist2
    WHERE ist2.IslStatusID = it.ItIntegrationStatusID
) ist
WHERE tpm.PartsConsumed = 0
  AND tpm.PartsQtyNeeded > 0
"""

# Query 3: GP item-location qty for a specific part + location.
QUERY_GP_QTY = """
SELECT
    ITEMNMBR,
    LOCNCODE,
    QTYONHND,
    ATYALLOC,
    QTYCOMTD
FROM IntegrationDB.dbo.IV00102
WHERE ITEMNMBR = '{part}'
  AND LOCNCODE = '{location}'
"""

# Query 7: Check for RINV removal records for a specific part + location.
QUERY_RINV = """
SELECT
    ItPKey,
    ItGPDocID,
    ItQty,
    ItIntegrationStatusID,
    ItProcessDate
FROM Inventory.dbo.IntegrationTransactions
WHERE ItGPDocID LIKE 'RINV%'
  AND ItPartNumber = '{part}'
  AND ItOrigin = '{location}'
ORDER BY ItProcessDate DESC
"""

# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify(row: dict, gp_qty: dict, rinv_records: list) -> dict:
    """Map each ticket row to an error category + recommended action."""
    error = row.get("IntegrationError") or ""
    status = row.get("StatusID")
    needed = row.get("QuantityNeeded") or 0
    on_hand = gp_qty.get("QTYONHND", 0)
    alloc = gp_qty.get("ATYALLOC", 0)
    available = on_hand - alloc
    location = row.get("Location", "")

    if status is None:
        return {
            "category": "NOT_INTEGRATED",
            "action": "No integration record. Manually trigger consumption.",
        }

    if status == 5:
        return {
            "category": "STUCK_PROCESSING",
            "action": "Stuck in Processing. Check IntercompanyTransactions; may need reset.",
        }

    if "Quantity of part in ERP system is not enough" in error:
        deficit = max(0, needed - on_hand)
        if available >= needed:
            return {
                "category": "QTYFULFI",
                "action": (
                    f"Allocation lock. QTYONHND={on_hand}, ATYALLOC={alloc}. "
                    "Check SOP10200 + Status 3 RINV records."
                ),
            }
        if rinv_records:
            return {
                "category": "QTY_SHORTAGE_RINV",
                "action": (
                    f"RINV removal likely caused shortage. Deficit={deficit}. "
                    f"Cycle Count {deficit} unit(s) at {location}, then reprocess."
                ),
            }
        return {
            "category": "QTY_SHORTAGE",
            "action": (
                f"GP has {on_hand}, need {needed}, deficit={deficit}. "
                f"Investigate TINV/PINV history. Likely Cycle Count {deficit} unit(s)."
            ),
        }

    if "QTYFULFI" in error or "QtyShrtOpt" in error:
        return {
            "category": "QTYFULFI",
            "action": (
                f"Allocation lock. QTYONHND={on_hand}, ATYALLOC={alloc}. "
                "Check SOP10200 + stuck Status 3 RINV."
            ),
        }

    return {
        "category": "OTHER",
        "action": f"Manual review. Error: {error}",
    }


# ---------------------------------------------------------------------------
# MCP helpers
# ---------------------------------------------------------------------------

async def run_query(sql: str, database: str = "Inventory") -> list[dict]:
    """Execute a SELECT via MCP and return list of row dicts."""
    raw = await mcp_client.call_tool("execute_query", {"query": sql, "database": database})
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    # MCP server may return {"rows": [...]} or a bare list
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("rows", "result", "data", "results"):
            if key in data and isinstance(data[key], list):
                return data[key]
        # Single-row dict
        if any(k not in ("error",) for k in data):
            return [data]
    return []


# ---------------------------------------------------------------------------
# Excel report
# ---------------------------------------------------------------------------

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(color="FFFFFF", bold=True)

CATEGORY_COLORS = {
    "NOT_INTEGRATED":    "FFF2CC",
    "STUCK_PROCESSING":  "FCE4D6",
    "QTYFULFI":          "DDEBF7",
    "QTY_SHORTAGE_RINV": "FFD7D7",
    "QTY_SHORTAGE":      "FFD7D7",
    "OTHER":             "EEEEEE",
}


def _header_row(ws, columns: list[str]):
    ws.append(columns)
    for cell in ws[ws.max_row]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")


def write_excel(detail_rows: list[dict], filename: str):
    wb = openpyxl.Workbook()

    # --- Summary tab ---
    ws_sum = wb.active
    ws_sum.title = "Summary"
    _header_row(ws_sum, ["ErrorCategory", "Count"])

    from collections import Counter
    counts = Counter(r["ErrorCategory"] for r in detail_rows)
    for category, count in sorted(counts.items(), key=lambda x: -x[1]):
        ws_sum.append([category, count])

    ws_sum.column_dimensions["A"].width = 28
    ws_sum.column_dimensions["B"].width = 10

    # --- Detail tab ---
    ws_det = wb.create_sheet("Detail")
    columns = [
        "Company", "TicketID", "PartNumber", "QuantityNeeded", "Location",
        "StatusID", "StatusDescription", "ErrorCategory",
        "GPQtyOnHand", "GPAllocated", "GPAvailable", "Deficit",
        "HasRINV", "RetryCount", "IntegrationError",
        "RecommendedAction", "IntegrationID",
    ]
    _header_row(ws_det, columns)

    for row in detail_rows:
        ws_det.append([row.get(c, "") for c in columns])
        # Color-code by category
        color = CATEGORY_COLORS.get(row.get("ErrorCategory", "OTHER"), "FFFFFF")
        fill = PatternFill("solid", fgColor=color)
        for cell in ws_det[ws_det.max_row]:
            cell.fill = fill

    # Auto-width (approximate)
    col_widths = {
        "Company": 14, "TicketID": 14, "PartNumber": 18, "QuantityNeeded": 14,
        "Location": 12, "StatusID": 10, "StatusDescription": 22, "ErrorCategory": 22,
        "GPQtyOnHand": 14, "GPAllocated": 14, "GPAvailable": 14, "Deficit": 10,
        "HasRINV": 10, "RetryCount": 12, "IntegrationError": 40,
        "RecommendedAction": 55, "IntegrationID": 16,
    }
    for i, col in enumerate(columns, 1):
        letter = openpyxl.utils.get_column_letter(i)
        ws_det.column_dimensions[letter].width = col_widths.get(col, 14)

    ws_det.freeze_panes = "A2"

    wb.save(filename)
    print(f"Report written → {filename}")


# ---------------------------------------------------------------------------
# Main audit loop
# ---------------------------------------------------------------------------

async def main():
    print("=== Inventory Reconciliation Audit ===\n")

    # Step 1: Pull unconsumed tickets (query runs cross-DB; use T2Online as anchor)
    print("Step 1: Pulling unconsumed maintenance ticket parts...")
    tickets = await run_query(QUERY_UNCONSUMED, database="T2Online")
    print(f"  Found {len(tickets)} unconsumed ticket parts.\n")

    if not tickets:
        print("Nothing to audit. Exiting.")
        return

    detail_rows = []

    for i, row in enumerate(tickets, 1):
        part = row.get("PartNumber", "")
        location = row.get("Location", "")

        if i % 20 == 0 or i == 1:
            print(f"  Processing row {i}/{len(tickets)}...")

        # Step 2a: GP qty check
        gp_rows = await run_query(
            QUERY_GP_QTY.format(part=part.replace("'", "''"), location=location.replace("'", "''")),
            database="IntegrationDB",
        )
        gp_qty = gp_rows[0] if gp_rows else {}

        # Step 2b: RINV check
        rinv_rows = await run_query(
            QUERY_RINV.format(part=part.replace("'", "''"), location=location.replace("'", "''")),
            database="Inventory",
        )

        # Step 3: Classify
        classification = classify(row, gp_qty, rinv_rows)

        on_hand = gp_qty.get("QTYONHND", 0)
        alloc = gp_qty.get("ATYALLOC", 0)
        needed = row.get("QuantityNeeded") or 0
        deficit = max(0, needed - on_hand)

        detail_rows.append({
            "Company":          row.get("Company", ""),
            "TicketID":         row.get("TicketID", ""),
            "PartNumber":       part,
            "QuantityNeeded":   needed,
            "Location":         location,
            "StatusID":         row.get("StatusID", ""),
            "StatusDescription": row.get("StatusDescription", ""),
            "ErrorCategory":    classification["category"],
            "GPQtyOnHand":      on_hand,
            "GPAllocated":      alloc,
            "GPAvailable":      on_hand - alloc,
            "Deficit":          deficit,
            "HasRINV":          "Yes" if rinv_rows else "No",
            "RetryCount":       row.get("RetryCount", ""),
            "IntegrationError": row.get("IntegrationError", ""),
            "RecommendedAction": classification["action"],
            "IntegrationID":    row.get("IntegrationID", ""),
        })

    print(f"\nStep 3: Classified {len(detail_rows)} rows.\n")

    # Step 4: Write Excel
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(os.path.dirname(__file__), f"audit_{timestamp}.xlsx")
    write_excel(detail_rows, filename)


if __name__ == "__main__":
    asyncio.run(main())
