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
AUTH_TOKEN = "0a31a57f-6615-42b5-9062-8b043770a52d" # Ensure this is your actual token

# --- Define the API Call Function ---
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
        return f"Successfully executed Admin Panel job ID {job_id} for PO number {params.get('ponumber')}. Status: {response.status_code} OK."

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


# --- Define the Input Schema for the LangChain Tool ---
class CancelPOInput(BaseModel):
    """Input for the cancel_po_main_record tool."""
    ponumber: str = Field(description="The Purchase Order number to be cancelled. This must be a string consisting of digits.")

# --- Define the LangChain Tool using the @tool decorator ---
@tool("cancel_po_main_record", args_schema=CancelPOInput)
def cancel_po_main_record(ponumber: str) -> str:
    """
    Cancels a Purchase Order (PO) in the PurchaseOrderMain system.
    Use this tool when a user explicitly requests to cancel a PO and provides a PO number.
    The PO number must be a string of digits.
    """
    # The job ID for "Cancel PO main record" from your provided image
    job_id = 4
    params = {"ponumber": ponumber}
    return _call_admin_panel_job(job_id, params, AUTH_TOKEN)

# --- Example of how to use the tool (for testing this script directly) ---
if __name__ == "__main__":
    print("--- Testing LangChain Tool Directly ---")

    # IMPORTANT: Use a test PO number that is valid for cancellation in your IR environment.
    # Ensure this PO number is a string.
    test_po_for_tool = "803080" # Example, replace with a real test PO number

    if AUTH_TOKEN == "YOUR_BEARER_TOKEN_HERE":
        print("\033[91mPlease update AUTH_TOKEN in the script before running.\033[0m")
    else:
        print(f"Calling cancel_po_main_record tool with PO: {test_po_for_tool}")
        result = cancel_po_main_record.run(test_po_for_tool)
        print("\nTool Execution Result:")
        print(result)

        # Example of a prompt that might trigger this tool (for conceptual understanding)
        print("\n--- Example Prompt for LLM ---")
        print("User: I need to cancel PO number 803080. Can you do that?")
        print("LLM (thinking): The user wants to cancel a PO. I have a tool 'cancel_po_main_record' that can do this. It requires a 'ponumber'. The user provided '803080'.")
        print("LLM (calling tool): cancel_po_main_record(ponumber='803080')")
        print("LLM (receiving output): Successfully executed Admin Panel job ID 4 for PO number 803080. Status: 200 OK.")
        print("LLM (responding): I have successfully initiated the cancellation for PO number 803080.")
