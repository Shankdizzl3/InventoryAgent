import os
import json
import re # Import regex module
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate

# Import your custom tool's underlying function, not the LangChain Tool object
# We need the direct function to call it after parsing LLM output
from langchain_tools import _call_admin_panel_job, AUTH_TOKEN

# --- Configuration ---
OLLAMA_MODEL = "phi3:mini"
CANCEL_PO_JOB_ID = 4 # The job ID for "Cancel PO main record"

def process_user_request_for_demo(user_request: str):
    """
    Demonstrates LLM intent recognition and direct tool invocation for a single request.
    This version is designed for clean, professional output.
    """
    print("\n" + "="*80)
    print(f" DEMONSTRATION SCENARIO: Processing a Purchase Order Cancellation Request")
    print("="*80 + "\n")

    print(f"1. Simulated User Request (ServiceNow Ticket Description):\n   \"{user_request}\"\n")

    llm = OllamaLLM(model=OLLAMA_MODEL)

    # --- Prompt for Intent and Parameter Extraction ---
    # We instruct the LLM to output a specific JSON format if a tool is needed.
    # Otherwise, it should respond naturally.
    prompt_template_string = """
You are an IT Support Assistant. Your task is to analyze user requests and determine if they require calling the 'cancel_po_main_record' tool.

**Tool Description:**
- `cancel_po_main_record(ponumber: str)`: Cancels a Purchase Order (PO) in the PurchaseOrderMain system. Use this tool when a user explicitly requests to cancel a PO and provides a PO number. The PO number must be a string of digits.

**Instructions:**
- If the user's request clearly indicates a need to cancel a PO and provides a PO number, respond with a JSON object in the following format:
  ```json
  {{
    "action": "call_tool",
    "tool_name": "cancel_po_main_record",
    "parameters": {{
      "ponumber": "THE_EXTRACTED_PO_NUMBER_HERE"
    }}
  }}
  ```
- If the user's request is about canceling a PO but is missing the PO number, respond with a JSON object in the following format:
  ```json
  {{
    "action": "ask_for_info",
    "missing_info": "ponumber",
    "message": "Please provide the Purchase Order number you wish to cancel."
  }}
  ```
- **IMPORTANT:** If the request is for something else entirely, or if no tool (including asking for PO info) is suitable, respond naturally in plain text. DO NOT output JSON in these cases. State clearly that you cannot fulfill the request or provide a helpful answer if possible.
- DO NOT include any conversational text or explanation outside of the JSON block if you are outputting JSON.

User Request: {user_input}
"""
    prompt = PromptTemplate.from_template(prompt_template_string)

    # Invoke the LLM
    print("2. Asking LLM for Intent and Parameters...")
    llm_raw_output = llm.invoke(prompt.format(user_input=user_request))
    print(f"   LLM Raw Output:\n{llm_raw_output}\n")

    # --- Extract JSON from Markdown code block ---
    json_match = re.search(r"```json\s*(.*?)\s*```", llm_raw_output, re.DOTALL)
    json_string = ""
    if json_match:
        json_string = json_match.group(1)
        print(f"3. Extracted JSON Intent from LLM Output:\n{json_string}\n")
    else:
        print("   No JSON code block found in LLM output. Treating as natural language response.")
        print(f"\n4. Final Response from LLM (Natural Language):\n   \"{llm_raw_output.strip()}\"")
        return # Exit the function if no JSON block is found

    try:
        # Attempt to parse the extracted JSON string
        parsed_output = json.loads(json_string)

        if parsed_output.get("action") == "call_tool":
            tool_name = parsed_output.get("tool_name")
            parameters = parsed_output.get("parameters", {})
            ponumber = parameters.get("ponumber")

            if tool_name == "cancel_po_main_record" and ponumber:
                print(f"4. LLM Identified Action: Call '{tool_name}' tool with PO Number: {ponumber}\n")
                print("5. Executing Custom API Call (Admin Panel Job 'Cancel PO main record')...")
                # Directly call the underlying API function
                api_call_result = _call_admin_panel_job(CANCEL_PO_JOB_ID, {"ponumber": ponumber}, AUTH_TOKEN)
                print(f"\n6. API Call Result:\n   {api_call_result}\n")
                
                # Formulate a concise final response based on the API result
                final_response_message = f"The request to cancel Purchase Order {ponumber} has been processed. Status: {api_call_result}"
                print(f"7. Final Response to User:\n   \"{final_response_message}\"")
            else:
                print("LLM requested an unknown tool or missing parameters.")
                print(f"\nFinal Response: I'm sorry, I couldn't process that request as the tool or parameters were not recognized.")

        elif parsed_output.get("action") == "ask_for_info":
            message = parsed_output.get("message", "I need more information to proceed.")
            print(f"4. LLM Identified Action: Ask for Missing Information")
            print(f"\n5. Final Response to User:\n   \"{message}\"")

        else:
            print("LLM outputted JSON but with an unknown action type.")
            print(f"\nFinal Response: I'm sorry, I couldn't understand the intended action from your request.")

    except json.JSONDecodeError as e:
        print(f"Error parsing extracted JSON: {e}")
        print(f"Problematic JSON string: '{json_string}'")
        print(f"\nFinal Response: An error occurred while interpreting the LLM's structured response.")
    except Exception as e:
        print(f"\nAn unexpected error occurred during processing: {e}")
        print(f"\nFinal Response: An internal error occurred while processing your request: {e}")


if __name__ == "__main__":
    # --- IMPORTANT: Ensure AUTH_TOKEN is set in langchain_tools.py ---
    if AUTH_TOKEN == "YOUR_BEARER_TOKEN_HERE":
        print("\033[91mERROR: Please update AUTH_TOKEN in langchain_tools.py before running this script.\033[0m")
        exit()

    # --- DEMONSTRATION SCENARIO ---
    # This simulates a user's request (e.g., from a ServiceNow ticket description).
    demo_user_request = "I need to cancel Purchase Order number 803080. Can you please process this?"
    process_user_request_for_demo(demo_user_request)
