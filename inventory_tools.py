import pyodbc
import json

# ==========================================================================
# == INVENTORY AGENT - TOOL IMPLEMENTATIONS                             ==
# ==========================================================================

# --------------------------------------------------------------------------
# --- 1. DATABASE CONFIGURATION (ACTION REQUIRED) ---
# --------------------------------------------------------------------------
# IMPORTANT: Replace these placeholder values with your actual database
# credentials. For production, use a secure method like environment
# variables or a secrets manager instead of hardcoding them.

DB_SERVER = "YOUR_DATABASE_SERVER_NAME"
DB_DATABASE = "Inventory"
DB_USERNAME = "YOUR_USERNAME"
DB_PASSWORD = "YOUR_PASSWORD"
DB_DRIVER = "{ODBC Driver 17 for SQL Server}" # Common driver, adjust if needed

# Construct the connection string
DB_CONNECTION_STRING = (
    f"DRIVER={DB_DRIVER};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_DATABASE};"
    f"UID={DB_USERNAME};"
    f"PWD={DB_PASSWORD};"
)

# --------------------------------------------------------------------------
# --- 2. TOOL IMPLEMENTATIONS ---
# --------------------------------------------------------------------------

def get_transactions_for_part(part_number: str) -> str:
    """
    Connects to the Inventory database and retrieves all transactions
    from the IntegrationTransactions table for a specific part number.
    """
    print(f"--- EXECUTING TOOL: get_transactions_for_part ---")
    print(f"    - part_number: {part_number}")

    # The SQL query to execute.
    # We use a parameterized query (?) to prevent SQL injection.
    sql_query = """
        SELECT
            IntegrationTransactionID,
            PartID,
            TransactionType,
            Quantity,
            Status,
            ErrorMessage,
            CreatedDate,
            ModifiedDate
        FROM
            dbo.IntegrationTransactions
        WHERE
            PartID = ?
        ORDER BY
            CreatedDate DESC;
    """

    results = []
    try:
        # Establish a connection to the database
        with pyodbc.connect(DB_CONNECTION_STRING, timeout=10) as conn:
            cursor = conn.cursor()
            # Execute the query with the part number as a parameter
            cursor.execute(sql_query, part_number)

            # Fetch all rows from the query result
            rows = cursor.fetchall()
            
            # Get column names from the cursor description
            columns = [column[0] for column in cursor.description]

            # Convert each row to a dictionary
            for row in rows:
                results.append(dict(zip(columns, row)))

            print(f"    - Result: Found {len(results)} transactions in the database.")

    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        print(f"ERROR: Database query failed. SQLSTATE: {sqlstate}")
        print(ex)
        return json.dumps({"error": f"Database error: {ex}"})
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during database connection: {e}")
        return json.dumps({"error": f"An unexpected error occurred: {e}"})

    # Return the list of transaction dictionaries as a JSON string
    # The default=str is used to handle data types like datetime
    return json.dumps(results, indent=2, default=str)

# --- Other tools can be added back here later ---

