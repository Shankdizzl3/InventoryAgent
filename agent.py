import ast
import asyncio
import json
import re

import mcp_client
from llm_utils import OLLAMA_MODEL, OLLAMA_BASE_URL, get_client

# --------------------------------------------------------------------------
# --- 1. CONFIGURATION ---
# --------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are an inventory reconciliation specialist for a field service company.\n"
    "You have read-only SQL Server access across three databases:\n\n"
    "Inventory.dbo.IntegrationTransactions — audit log of all inventory movements.\n"
    "  Key columns: ItPKey, ItGPDocID (prefix: TMIN=consume, TINV=transfer, RINV=removal, PINV=PO receipt),\n"
    "  ItPartNumber, ItOrigin, ItDestination, ItQty, ItIntegrationStatusID,\n"
    "  ItLongError, ItShortError, ItProcessDate, it_retry_count.\n"
    "  Status IDs: 1=Success, 2=Failure, 3=Failed Batch (can create stuck ATYALLOC),\n"
    "  4=Pending, 5=Processing, 6=Processed But Failed Qty Update, 9=Cancelled.\n\n"
    "IntegrationDB.dbo.IV00102 — GP item-location inventory (defacto truth for current qty).\n"
    "  Key columns: ITEMNMBR, LOCNCODE, QTYONHND, ATYALLOC, QTYCOMTD.\n\n"
    "T2Online.dbo.InventQuantities — Trakker qty view per part+location.\n"
    "  Key columns: IqtPartNumber, IqtLocationCode, IqtQtyOnHand, IqtQtyConsume,\n"
    "  IqtQtyTransferIn, IqtQtyTransferOut, IqtQtyAllocate.\n\n"
    "Before calling any tool, write one sentence starting with 'Plan: '. Then call the tool.\n"
    "When answering directly, respond normally."
)

# --------------------------------------------------------------------------
# --- 2. TOOL DEFINITIONS ---
# Only these 3 MCP tools are surfaced to the LLM.
# --------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_query",
            "description": (
                "Run a read-only SELECT query against a SQL Server database. "
                "Set database to 'Inventory', 'IntegrationDB', or 'T2Online' depending on the table. "
                "IntegrationTransactions and IntegrationStatusLookup are in Inventory. "
                "IV00102 and SOP10200 are in IntegrationDB. "
                "TicketCallMain, TicketPartsMain, and InventQuantities are in T2Online."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A valid T-SQL SELECT statement.",
                    },
                    "database": {
                        "type": "string",
                        "description": "Database name: 'Inventory', 'IntegrationDB', or 'T2Online'.",
                        "default": "Inventory",
                    },
                },
                "required": ["query", "database"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": (
                "List all tables in a database. "
                "Set database to 'Inventory', 'IntegrationDB', or 'T2Online'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "database": {
                        "type": "string",
                        "description": "Database name: 'Inventory', 'IntegrationDB', or 'T2Online'.",
                        "default": "Inventory",
                    },
                },
                "required": ["database"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_table",
            "description": (
                "Get column names, data types, and constraints for a specific table. "
                "Set database to 'Inventory', 'IntegrationDB', or 'T2Online'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tableName": {
                        "type": "string",
                        "description": "The table name, e.g. 'IntegrationTransactions'.",
                    },
                    "database": {
                        "type": "string",
                        "description": "Database name: 'Inventory', 'IntegrationDB', or 'T2Online'.",
                        "default": "Inventory",
                    },
                    "schema": {
                        "type": "string",
                        "description": "Schema name. Default is 'dbo'.",
                        "default": "dbo",
                    },
                },
                "required": ["tableName", "database"],
            },
        },
    },
]

# --------------------------------------------------------------------------
# --- 3. TOOL DISPATCH ---
# Maps Ollama tool names to mcp_client calls.
# --------------------------------------------------------------------------

async def dispatch_tool(name: str, args: dict) -> str:
    """Routes an Ollama tool call to the appropriate MCP tool."""
    if name in ("execute_query", "list_tables", "describe_table"):
        return await mcp_client.call_tool(name, args)
    return json.dumps({"error": f"Unknown tool: {name}"})


# --------------------------------------------------------------------------
# --- 4. CORE AGENT LOGIC ---
# --------------------------------------------------------------------------

_KNOWN_TOOLS = {"execute_query", "list_tables", "describe_table"}


def _try_parse_func_call(text: str) -> tuple[str, dict] | None:
    """Parse 'tool_name(key="val", ...)' plain-text syntax into (name, args). Returns None on failure."""
    try:
        tree = ast.parse(text.strip(), mode="eval")
        node = tree.body
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            args = {}
            for kw in node.keywords:
                v = kw.value
                if isinstance(v, ast.Constant):
                    args[kw.arg] = v.value
                else:
                    args[kw.arg] = ast.literal_eval(v)
            return node.func.id, args
    except Exception:
        pass
    return None


def _parse_turn1(msg) -> tuple[str, list[tuple[str, dict]]]:
    """
    Returns (reasoning_text, [(fn_name, fn_args), ...]).
    Tries (1) native tool_calls, (2) JSON array in content, (3) plain-text call syntax.
    """
    content = msg.content or ""

    # Strip <|/tool_call|> suffix phi4-mini may append
    tool_marker = content.find("<|/tool_call|>")
    body = content[:tool_marker].strip() if tool_marker != -1 else content.strip()

    # --- 1. Native structured tool_calls ---
    if msg.tool_calls:
        json_start = body.find("[")
        reasoning = body[:json_start].strip() if json_start > 0 else ""
        calls = [(tc.function.name, tc.function.arguments) for tc in msg.tool_calls]
        return reasoning, calls

    # --- 2. JSON array embedded in content ---
    json_start = body.find("[")
    if json_start != -1:
        reasoning = body[:json_start].strip() if json_start > 0 else ""
        json_str = body[json_start: body.rfind("]") + 1]
        try:
            items = json.loads(json_str)
            calls = []
            for item in items:
                func = item.get("function", {})
                name = func.get("name") or item.get("name")
                args = item.get("arguments") or func.get("arguments") or {}
                if name and isinstance(args, dict):
                    calls.append((name, args))
            if calls:
                return reasoning, calls
        except json.JSONDecodeError:
            pass

    # --- 3. Plain-text function call: execute_query(key="val", ...) ---
    for tool_name in _KNOWN_TOOLS:
        idx = body.find(f"{tool_name}(")
        if idx != -1:
            reasoning = body[:idx].strip()
            parsed = _try_parse_func_call(body[idx:].strip())
            if parsed:
                return reasoning, [parsed]

    # No tool call — entire body is a direct answer (reasoning used as-is by caller)
    return "", []


async def _stream_response(client, messages: list):
    """Stream Turn 2 (summary), printing content tokens as they arrive."""
    async for chunk in await client.chat(
        model=OLLAMA_MODEL, messages=messages, stream=True
    ):
        content = chunk.message.content or ""
        if content:
            print(content, end="", flush=True)
    print()  # trailing newline


async def run_agent(user_request: str):
    """
    Async agent loop. Sends the user request to Ollama, executes any
    tool calls via the MCP server, then streams the final summary.
    """
    print("==============================================")
    print(f"USER: {user_request}")
    print("==============================================\n")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_request},
    ]
    client = get_client()

    # --- Agentic loop: up to 4 turns to handle tool calls and retries ---
    MAX_TURNS = 4
    for turn in range(MAX_TURNS):
        is_first_turn = turn == 0
        if is_first_turn:
            print("Thinking...", flush=True)

        response = await client.chat(model=OLLAMA_MODEL, messages=messages, tools=TOOLS)
        msg = response.message

        reasoning, tool_calls = _parse_turn1(msg)
        if reasoning:
            print(f"[Thinking] {reasoning}\n")

        if not tool_calls:
            # Model answered directly — print and stop
            print("[Response]")
            print(msg.content)
            break

        messages.append(msg)
        for fn_name, fn_args in tool_calls:
            print(f"--- TOOL CALL: {fn_name}({fn_args}) ---")
            result = await dispatch_tool(fn_name, fn_args)
            print(f"--- TOOL RESULT: {len(result)} chars ---\n")
            messages.append({"role": "tool", "content": result})

        # If this was the last allowed turn, force a final summary
        if turn == MAX_TURNS - 1:
            print("[Response]")
            await _stream_response(client, messages)
            break

    print("\n==========================")
    print("= DONE                   =")
    print("==========================\n")


# --------------------------------------------------------------------------
# --- 5. ENTRY POINT ---
# --------------------------------------------------------------------------

async def main():
    print("Inventory Agent — type 'exit' or 'quit' to stop.\n")
    while True:
        try:
            user_request = input("Query: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if not user_request:
            continue
        if user_request.lower() in ("exit", "quit", "q"):
            print("Exiting.")
            break
        await run_agent(user_request)

if __name__ == "__main__":
    asyncio.run(main())
