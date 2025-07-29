import os
import json
import re # Import regex module
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate

# Import your custom tool's underlying functions
# Now importing both the main PO cancellation and the quantity cancellation tool
from langchain_tools import _call_admin_panel_job, AUTH_TOKEN, cancel_po_main_record, cancel_po_quantity

# --- Configuration ---
OLLAMA_MODEL = "phi3:mini"
CANCEL_PO_MAIN_JOB_ID = 4 # Job ID for "Cancel PO main record"
CANCEL_PO_QUANTITY_JOB_ID = 6 # Job ID for "Cancel PO quantity"

def process_user_request_for_demo(user_request: str):
    """
    Demonstrates LLM intent recognition and direct tool invocation for a single request.
    This version is designed for clean, professional output.
    """
    print("\n" + "="*80)
    print(f" DEMONSTRATION SCENARIO: Processing a Purchase Order Cancellation Request")
    print("="*80 + "\n")

    # 1. Simulated User Request (e.g., from a ServiceNow Ticket Description)
    print(f"1. Simulated User Request (Ticket Description):\n   \"{user_request}\"\n")

    llm = OllamaLLM(model=OLLAMA_MODEL)

    # --- Prompt for Intent and Parameter Extraction ---
    # This prompt instructs the LLM on its role and how to use the available tools.
    # It guides the LLM to output a specific JSON format if a tool is needed,
    # or plain text if the request is out of scope or requires clarification.
    prompt_template_string = """
You are an IT Support Assistant. Your task is to analyze user requests and determine if they require calling any of the available tools.

**Available Tools:**
- `cancel_po_main_record(ponumber: str)`: Cancels an entire Purchase Order (PO) in the PurchaseOrderMain system, including its associated quantities. Use this tool when a user explicitly requests to cancel an *entire* PO and provides a PO number. The PO number must be a string of digits.
- `cancel_po_quantity(ponumber: str)`: Cancels or updates the quantity of items for a specific Purchase Order (PO). This tool is used when the user wants to adjust the quantity of an existing PO, often setting it to zero, or cancelling only a part of the PO, *without* cancelling the entire PO record. Use this when the user mentions cancelling a quantity, reducing items, or cancelling only a part of a PO. The PO number must be a string of digits.

**Instructions:**
- If the user's request clearly indicates a need to call a tool and provides all necessary parameters, respond with a JSON object in the following format:
  ```json
  {{
    "action": "call_tool",
    "tool_name": "THE_TOOL_NAME_HERE",
    "parameters": {{
      "param1": "VALUE1",
      "param2": "VALUE2"
    }}
  }}
  ```
- If the user's request is about using a tool but is missing required information, respond with a JSON object in the following format:
  ```json
  {{
    "action": "ask_for_info",
    "missing_info": "PARAMETER_NAME",
    "message": "Please provide the missing information."
  }}
  ```
- **IMPORTANT:** If the request is for something else entirely, or if no tool (including asking for info) is suitable, respond naturally in plain text. DO NOT output JSON in these cases. State clearly that you cannot fulfill the request or provide a helpful answer if possible.
- **CRITICAL:** When outputting JSON, ensure your response contains ONLY the JSON code block (```json...```). Do NOT include any other text, explanations, or conversational phrases before or after the JSON block.

User Request: {user_input}
"""
    prompt = PromptTemplate.from_template(prompt_template_string)

    # 2. Asking LLM for Intent and Parameters
    print("2. LLM Processing Request (Intent Recognition & Parameter Extraction):")
    llm_raw_output = llm.invoke(prompt.format(user_input=user_request))
    print(f"   LLM Raw Output:\n{llm_raw_output}\n")

    # --- Attempt to Extract and Parse JSON from LLM Output ---
    json_match = re.search(r"```json\s*(.*?)\s*```", llm_raw_output, re.DOTALL)
    json_string = ""
    if json_match:
        json_string = json_match.group(1)
        print(f"3. Extracted and Parsed LLM's Structured Intent (JSON):\n{json_string}\n")
    else:
        print("   No JSON code block found in LLM output. LLM responded in natural language.")
        # If no JSON block, treat it as a natural language response
        print(f"\n4. Final Response to User (Natural Language):\n   \"{llm_raw_output.strip()}\"")
        return # Exit the function if no JSON block is found

    try:
        parsed_output = json.loads(json_string)

        if parsed_output.get("action") == "call_tool":
            tool_name = parsed_output.get("tool_name")
            parameters = parsed_output.get("parameters", {})
            ponumber = parameters.get("ponumber") # Both tools use ponumber

            if tool_name == "cancel_po_main_record" and ponumber:
                print(f"4. Detected Action: Call '{tool_name}' tool with PO Number: {ponumber}\n")
                
                # --- NEW: Chain both API calls for full PO cancellation ---
                print("5a. Executing Custom API Call (Admin Panel Job 'Cancel PO main record')...")
                api_call_main_result = _call_admin_panel_job(CANCEL_PO_MAIN_JOB_ID, {"ponumber": ponumber}, AUTH_TOKEN)
                print(f"6a. API Call Result (Main PO): {api_call_main_result}\n")

                print("5b. Executing Custom API Call (Admin Panel Job 'Cancel PO quantity')...")
                api_call_quantity_result = _call_admin_panel_job(CANCEL_PO_QUANTITY_JOB_ID, {"ponumber": ponumber}, AUTH_TOKEN)
                print(f"6b. API Call Result (PO Quantity): {api_call_quantity_result}\n")
                
                # Formulate a concise final response based on both API results
                final_response_message = (
                    f"Purchase Order {ponumber} has been successfully processed for full cancellation (main record and quantity). "
                    f"Main PO status: {api_call_main_result}. Quantity status: {api_call_quantity_result}."
                )
                print(f"7. Final Response to User:\n   \"{final_response_message}\"")
            
            elif tool_name == "cancel_po_quantity" and ponumber:
                print(f"4. Detected Action: Call '{tool_name}' tool with PO Number: {ponumber}\n")
                print("5. Executing Custom API Call (Admin Panel Job 'Cancel PO quantity')...")
                api_call_result = _call_admin_panel_job(CANCEL_PO_QUANTITY_JOB_ID, {"ponumber": ponumber}, AUTH_TOKEN)
                print(f"\n6. API Call Result:\n   {api_call_result}\n")
                
                final_response_message = f"The quantity for Purchase Order {ponumber} has been successfully processed for cancellation/adjustment."
                print(f"7. Final Response to User:\n   \"{final_response_message}\"")

            else:
                print("   LLM requested an unknown tool or missing parameters in JSON.")
                print(f"\nFinal Response: I'm sorry, I couldn't process that request as the tool or parameters were not recognized.")

        elif parsed_output.get("action") == "ask_for_info":
            message = parsed_output.get("message", "I need more information to proceed.")
            print(f"4. Detected Action: Ask for Missing Information")
            print(f"\n5. Final Response to User:\n   \"{message}\"")

        else:
            print("   LLM outputted JSON with an unknown action type.")
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

    # --- DEMONSTRATION SCENARIOS ---
    # Scenario 1: Full PO Cancellation (now triggers both main and quantity cancellation)
    demo_user_request_1 = "I need to cancel Purchase Order number 803080. Can you please process this?"
    process_user_request_for_demo(demo_user_request_1)
