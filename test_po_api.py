import requests
import json
import os

# --- Configuration ---
# Hardcoded URLs for different environments.
# Using the 'ir' environment as requested.
API_BASE_URL = "https://api-ir.staging.serviceexpress.com/v1/adminpanel"
API_JOB_RUN_ENDPOINT = f"{API_BASE_URL}/job/run"

# --- Authorization Token ---
# IMPORTANT: Replace 'YOUR_BEARER_TOKEN_HERE' with your actual Authorization Token.
# In a production environment, you would load this securely (e.g., from environment variables,
# a secrets manager, or a configuration file not committed to version control).
AUTH_TOKEN = "0a31a57f-6615-42b5-9062-8b043770a52d"

def call_cancel_po_api(job_id: int, po_number: str, auth_token: str):
    """
    Calls the "Cancel PO main record" API with authorization.

    Args:
        job_id (int): The ID of the job to run (e.g., 4 for Cancel PO).
        po_number (str): The Purchase Order number to cancel (must be a string, even if numeric).
        auth_token (str): The authorization token (e.g., Bearer token).

    Returns:
        dict: The JSON response from the API, or an error message.
    """
    if not auth_token or auth_token == "YOUR_BEARER_TOKEN_HERE":
        print("\033[91m- ERROR: Authorization token is missing or placeholder. Please set AUTH_TOKEN in the script.\033[0m")
        return {"error": "Authorization token is required and must be set."}

    headers = {
        "Authorization": f"Bearer {auth_token}", # Using Bearer token as per your boilerplate
        "Content-Type": "application/json"
    }

    payload = {
        "id": job_id,
        "params": {
            "ponumber": str(po_number) # Ensure it's explicitly a string for the payload
        }
    }

    print(f"Attempting to call API: {API_JOB_RUN_ENDPOINT}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    # For security, avoid printing the full auth token in production logs
    print(f"Headers (partial): {{'Authorization': 'Bearer [TOKEN_REDACTED]', 'Content-Type': 'application/json'}}")

    try:
        response = requests.post(API_JOB_RUN_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)

        print("\nAPI Call Successful!")
        print(f"Status Code: {response.status_code}")

        # --- NEW: Print raw response text for inspection ---
        print(f"Raw Response Body (text): '{response.text}'")
        # --- END NEW ---

        # Try to parse as JSON, but handle the potential error
        try:
            return response.json()
        except json.JSONDecodeError:
            print("\033[93mWarning: Response body is not valid JSON. Returning raw text as 'response_text'.\033[0m")
            return {"response_text": response.text, "status_code": response.status_code, "error": "Response not valid JSON"}

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response Body: {e.response.text}")
        return {"error": str(e), "response_body": e.response.text, "status_code": e.response.status_code}
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error: {e}")
        return {"error": str(e)}
    except requests.exceptions.Timeout as e:
        print(f"Timeout Error: {e}")
        return {"error": str(e)}
    except requests.exceptions.RequestException as e:
        print(f"An unexpected error occurred: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    print("--- Testing Cancel PO API Call ---")

    test_job_id = 4
    test_po_number = "803080" # Your test PO number

    api_response = call_cancel_po_api(test_job_id, test_po_number, AUTH_TOKEN)
    print("\nAPI Response (Parsed/Error):")
    print(json.dumps(api_response, indent=2))
