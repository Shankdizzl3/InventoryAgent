"""
inventory_tools.py — Thin shims over mcp_client.call_tool().

Each function corresponds to one MCP tool exposed by mssql-mcp-server.
No database credentials or pyodbc logic lives here — everything routes
through the MCP server process.
"""

import mcp_client

DATABASE = "Inventory"


async def execute_query(query: str, database: str = DATABASE) -> str:
    """Run a read-only SELECT query against the Inventory database."""
    return await mcp_client.call_tool("execute_query", {
        "query": query,
        "database": database,
    })


async def list_tables(database: str = DATABASE, schema: str | None = None) -> str:
    """List tables in the Inventory database."""
    args: dict = {"database": database}
    if schema:
        args["schema"] = schema
    return await mcp_client.call_tool("list_tables", args)


async def describe_table(
    table_name: str,
    database: str = DATABASE,
    schema: str = "dbo",
) -> str:
    """Get column details for a table in the Inventory database."""
    return await mcp_client.call_tool("describe_table", {
        "tableName": table_name,
        "database": database,
        "schema": schema,
    })


async def get_transactions_for_part(part_number: str) -> str:
    """
    High-level helper: fetch all IntegrationTransactions rows for a part.
    Kept for backwards compatibility with callers that used the old interface.
    """
    sql = (
        "SELECT IntegrationTransactionID, PartID, TransactionType, Quantity, "
        "Status, ErrorMessage, CreatedDate, ModifiedDate "
        "FROM dbo.IntegrationTransactions "
        f"WHERE PartID = '{part_number}' "
        "ORDER BY CreatedDate DESC;"
    )
    return await execute_query(sql)
