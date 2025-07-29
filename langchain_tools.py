import requests
import json
import os
from langchain.tools import tool
from pydantic import BaseModel, Field

# --- Configuration ---
API_BASE_URL = "https://api-ir.staging.serviceexpress.com/v1/adminpanel"
API_JOB_RUN_ENDPOINT = f"{API_BASE_URL}/job/run"

# --- Authorization Token ---
# IMPORTANT: Replace 'YOUR_BEARER_TOKEN_HERE' with your actual Authorization Token.
# This token will be used by the tool when called.
AUTH_TOKEN = "f58a1284-720c-4836-9546-b862d43ccfe2" # Ensure this is your actual token

# --- Define the API Call Function (Generic Admin Panel Job Runner) ---
def _call_admin_panel_job(job_id: int, params: dict, auth_token: str) -> str:
    """
    Internal function to make the actual HTTP POST request to the Admin Panel API.
    This is a generic function that can be used by various Admin Panel jobs.
    """
    if not auth_token or auth_token == "YOUR_BEARER_TOKEN_HERE":
        return "Error: Authorization token is missing or placeholder. Cannot execute API call."

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "id": job_id,
        "params": params
    }

    print(f"\n[Tool Call] Attempting to call API: {API_JOB_RUN_ENDPOINT}")
    print(f"[Tool Call] Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(API_JOB_RUN_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)

        # As observed, the API returns an empty body on success (HTTP 200)
        # We'll return a success message that the LLM can understand.
        # Check if ponumber is in params to make the message more generic
        po_num_info = f" for PO number {params.get('ponumber')}" if 'ponumber' in params else ""
        return f"Successfully executed Admin Panel job ID {job_id}{po_num_info}. Status: {response.status_code} OK."

    except requests.exceptions.HTTPError as e:
        error_message = f"HTTP Error {e.response.status_code}: {e.response.text}"
        print(f"[Tool Call] Error: {error_message}")
        return f"API call failed with HTTP Error: {e.response.status_code}. Details: {e.response.text}"
    except requests.exceptions.ConnectionError as e:
        error_message = f"Connection Error: {e}"
        print(f"[Tool Call] Error: {error_message}")
        return f"API call failed due to connection error: {e}"
    except requests.exceptions.Timeout as e:
        error_message = f"Timeout Error: {e}"
        print(f"[Tool Call] Error: {error_message}")
        return f"API call timed out: {e}"
    except requests.exceptions.RequestException as e:
        error_message = f"An unexpected request error occurred: {e}"
        print(f"[Tool Call] Error: {error_message}")
        return f"API call failed with an unexpected error: {e}"
    except Exception as e:
        error_message = f"An unexpected Python error occurred during API call: {e}"
        print(f"[Tool Call] Error: {error_message}")
        return f"An internal error occurred while trying to call the API: {e}"


# --- Input Schema for Cancel PO Main Record Tool ---
class CancelPOInput(BaseModel):
    """Input for the cancel_po_main_record tool."""
    ponumber: str = Field(description="The Purchase Order number to be cancelled. This must be a string consisting of digits.")

# --- Define the LangChain Tool: Cancel PO Main Record ---
@tool("cancel_po_main_record", args_schema=CancelPOInput)
def cancel_po_main_record(ponumber: str) -> str:
    """
    Cancels an entire Purchase Order (PO) in the PurchaseOrderMain system.
    Use this tool when a user explicitly requests to cancel an entire PO and provides a PO number.
    The PO number must be a string of digits.
    """
    job_id = 4 # Job ID for "Cancel PO main record"
    params = {"ponumber": ponumber.strip()}
    return _call_admin_panel_job(job_id, params, AUTH_TOKEN)


# --- NEW: Input Schema for Cancel PO Quantity Tool ---
class CancelPOQuantityInput(BaseModel):
    """Input for the cancel_po_quantity tool."""
    ponumber: str = Field(description="The Purchase Order number for which to cancel/update the quantity. This must be a string consisting of digits.")
    # If the quantity itself is a parameter for this job, you would add it here:
    # quantity_to_cancel: int = Field(description="The quantity to cancel for the specified PO.")

# --- NEW: Define the LangChain Tool: Cancel PO Quantity ---
@tool("cancel_po_quantity", args_schema=CancelPOQuantityInput)
def cancel_po_quantity(ponumber: str) -> str:
    """
    Cancels or updates the quantity of items for a specific Purchase Order (PO) in the system.
    This tool is used when the user wants to adjust the quantity of an existing PO, often setting it to zero.
    Use this when the user mentions cancelling a quantity or reducing items for a PO.
    The PO number must be a string of digits.
    """
    job_id = 6 # Job ID for "Cancel PO quantity" from your image
    params = {"ponumber": ponumber.strip()}
    # If the job requires a specific quantity parameter, you'd include it here, e.g.:
    # params = {"ponumber": ponumber.strip(), "quantity": quantity_to_cancel}
    return _call_admin_panel_job(job_id, params, AUTH_TOKEN)


# --- Example of how to use the tools (for testing this script directly) ---
if __name__ == "__main__":
    print("--- Testing LangChain Tools Directly ---")

    if AUTH_TOKEN == "YOUR_BEARER_TOKEN_HERE":
        print("\033[91mPlease update AUTH_TOKEN in the script before running.\033[0m")
    else:
        # Test Cancel PO Main Record
        test_po_main = "803080"
        print(f"\nCalling cancel_po_main_record tool with PO: {test_po_main}")
        result_main = cancel_po_main_record.run(test_po_main)
        print("Tool Execution Result (Main PO Cancellation):")
        print(result_main)

        # Test Cancel PO Quantity
        test_po_quantity = "803080" # Use a test PO number for quantity cancellation
        print(f"\nCalling cancel_po_quantity tool with PO: {test_po_quantity}")
        result_quantity = cancel_po_quantity.run(test_po_quantity)
        print("Tool Execution Result (PO Quantity Cancellation):")
        print(result_quantity)
