"""
mcp_client.py — Async MCP client wrapper for the mssql-mcp-server.

Spawns the Node.js MCP server process via stdio transport and exposes
a single call_tool() coroutine. The session is lazily initialized on
first use and reused for the lifetime of the Python process.
"""

import json
import os
from contextlib import AsyncExitStack

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

MCP_SERVER_PATH = os.getenv("MCP_SERVER_PATH", "")

# Module-level session state (lazy singleton)
_session: ClientSession | None = None
_exit_stack: AsyncExitStack | None = None


async def get_session() -> ClientSession:
    """
    Returns a live MCP ClientSession, initializing it on first call.
    The Node.js server process is spawned once and kept alive.
    """
    global _session, _exit_stack

    if _session is not None:
        return _session

    if not MCP_SERVER_PATH:
        raise RuntimeError(
            "MCP_SERVER_PATH is not set. Add it to your .env file.\n"
            "Example: MCP_SERVER_PATH=C:\\...\\mssql-mcp-server\\dist\\index.js"
        )

    server_params = StdioServerParameters(
        command="node",
        args=[MCP_SERVER_PATH],
    )

    _exit_stack = AsyncExitStack()
    read, write = await _exit_stack.enter_async_context(stdio_client(server_params))
    _session = await _exit_stack.enter_async_context(ClientSession(read, write))
    await _session.initialize()

    return _session


async def close_session() -> None:
    """Close the MCP session and kill the Node.js subprocess cleanly."""
    global _session, _exit_stack
    if _exit_stack is not None:
        try:
            await _exit_stack.aclose()
        except Exception:
            pass
    _session = None
    _exit_stack = None


async def call_tool(name: str, arguments: dict) -> str:
    """
    Calls a named MCP tool with the given arguments and returns
    the result as a JSON string.
    """
    session = await get_session()
    result = await session.call_tool(name, arguments)

    # MCP results are a list of content blocks; extract text content
    parts = []
    for content in result.content:
        if hasattr(content, "text"):
            parts.append(content.text)
        else:
            parts.append(str(content))

    combined = "\n".join(parts) if parts else ""

    # If it looks like JSON already, return as-is; otherwise wrap it
    try:
        json.loads(combined)
        return combined
    except (json.JSONDecodeError, ValueError):
        return json.dumps({"result": combined})


def parse_rows(raw: str) -> list[dict]:
    """
    Parse a raw JSON string from call_tool into a list of row dicts.
    Handles list responses, dict responses with rows/result/data/results keys,
    and single-dict responses. Returns [] on error or empty results.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return []

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("rows", "result", "data", "results"):
            if key in data and isinstance(data[key], list):
                return data[key]
        if not data.get("error"):
            return [data]
    return []
