import asyncio
import json
import os

import ollama
from dotenv import load_dotenv

import mcp_client

load_dotenv()

# --------------------------------------------------------------------------
# --- 1. CONFIGURATION ---
# --------------------------------------------------------------------------

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi4-mini")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

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
                "Run a read-only SELECT query against the Inventory SQL Server database. "
                "Always set database to 'Inventory'. "
                "Example: SELECT * FROM dbo.IntegrationTransactions WHERE PartID = 'ABC123'"
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
                        "description": "Database name. Always use 'Inventory'.",
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
                "List all tables in the Inventory database. "
                "Use this to discover available tables before writing a query."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "database": {
                        "type": "string",
                        "description": "Database name. Always use 'Inventory'.",
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
                "Get column names, data types, and constraints for a specific table "
                "in the Inventory database. Use this before querying an unfamiliar table."
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
                        "description": "Database name. Always use 'Inventory'.",
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

async def run_agent(user_request: str):
    """
    Async agent loop. Sends the user request to Ollama, executes any
    tool calls via the MCP server, then returns the final summary.
    """
    print("==============================================")
    print(f"USER: {user_request}")
    print("==============================================\n")

    messages = [{"role": "user", "content": user_request}]
    client = ollama.AsyncClient(host=OLLAMA_BASE_URL)

    # --- Turn 1: model decides what tool to call ---
    response = await client.chat(
        model=OLLAMA_MODEL,
        messages=messages,
        tools=TOOLS,
    )
    msg = response.message

    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = tool_call.function.arguments

            print(f"--- TOOL CALL: {fn_name}({fn_args}) ---")

            result = await dispatch_tool(fn_name, fn_args)

            print(f"--- TOOL RESULT: {len(result)} chars ---\n")

            messages.append(msg)
            messages.append({"role": "tool", "content": result})

        # --- Turn 2: model summarizes the results ---
        final_response = await client.chat(
            model=OLLAMA_MODEL,
            messages=messages,
        )
        print("AGENT RESPONSE:")
        print(final_response.message.content)

    else:
        print("AGENT RESPONSE:")
        print(msg.content)

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
