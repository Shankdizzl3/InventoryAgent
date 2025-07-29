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

def process_user_request(user_request: str):
    """
    Uses LLM for intent recognition and parameter extraction, then directly calls the tool.
    """
    print(f"\n--- Processing User Request: {user_request} ---")

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
- If the request is for something else entirely, or if no tool is suitable, respond naturally in plain text, stating that you cannot fulfill the request or providing a helpful answer if possible.
- DO NOT include any conversational text or explanation outside of the JSON block if you are outputting JSON.

User Request: {user_input}
"""
    prompt = PromptTemplate.from_template(prompt_template_string)

    # Invoke the LLM
    print("Asking LLM for intent and parameters...")
    llm_output = llm.invoke(prompt.format(user_input=user_request))
    print(f"LLM Raw Output:\n{llm_output}\n")

    # --- NEW: Extract JSON from Markdown code block ---
    json_match = re.search(r"```json\s*(.*?)\s*```", llm_output, re.DOTALL)
    json_string = ""
    if json_match:
        json_string = json_match.group(1)
        print(f"Extracted JSON String:\n{json_string}\n")
    else:
        print("No JSON code block found in LLM output.")
        # If no JSON block, proceed as if it's a natural language response
        print("LLM outputted a natural language response (not JSON).")
        print(f"\nFinal Response: {llm_output}")
        return # Exit the function if no JSON block is found

    try:
        # Attempt to parse the extracted JSON string
        parsed_output = json.loads(json_string)

        if parsed_output.get("action") == "call_tool":
            tool_name = parsed_output.get("tool_name")
            parameters = parsed_output.get("parameters", {})
            ponumber = parameters.get("ponumber")

            if tool_name == "cancel_po_main_record" and ponumber:
                print(f"LLM wants to call tool: {tool_name} with ponumber: {ponumber}")
                # Directly call the underlying API function
                result = _call_admin_panel_job(CANCEL_PO_JOB_ID, {"ponumber": ponumber}, AUTH_TOKEN)
                print("\nTool Execution Result:")
                print(result)
                print(f"\nFinal Response: The request to cancel PO {ponumber} has been processed. Result: {result}")
            else:
                print("LLM requested an unknown tool or missing parameters.")
                print(f"\nFinal Response: I'm sorry, I couldn't process that request as the tool or parameters were not recognized.")

        elif parsed_output.get("action") == "ask_for_info":
            message = parsed_output.get("message", "I need more information to proceed.")
            print(f"\nFinal Response: {message}")

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
    # Ensure AUTH_TOKEN is set in langchain_tools.py
    if AUTH_TOKEN == "YOUR_BEARER_TOKEN_HERE":
        print("\033[91mERROR: Please update AUTH_TOKEN in langchain_tools.py before running this script.\033[0m")
        exit()

    # Scenario 1: Direct Match
    process_user_request("I need to cancel Purchase Order number 803080. Can you please process this?")

    # Scenario 2: Request it cannot handle
    process_user_request("What is the current weather in London?")

    # Scenario 3: Missing Info
    process_user_request("I need to cancel a purchase order. Which one?")
