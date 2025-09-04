import requests
import json
import re

# --------------------------------------------------------------------------
# --- 1. CONFIGURATION ---
# --------------------------------------------------------------------------

LLM_SERVER_URL = "http://localhost:8000/completion"
N_PREDICT = 1024
TEMPERATURE = 0.2
TOP_P = 0.9
STOP_TOKENS = ["<|end|>", "```"]

# --------------------------------------------------------------------------
# --- 2. AGENT'S SYSTEM PROMPT & IDENTITY ---
# --------------------------------------------------------------------------

# UPDATED: Added a 'JSON Response Format' section with a clear example
# to give the model a better template and reduce syntax errors.
SYSTEM_PROMPT = """You are a proactive Inventory Management Agent. Your task is to audit system logs, identify critical inventory discrepancies, and provide a detailed analysis followed by the precise, structured tool calls needed for a resolution.

**Available Tools:**
- `check_product_status(product_id: str)`: Retrieves the full inventory record for a given product ID.
- `adjust_quantity(product_id: str, new_quantity: int)`: Adjusts the inventory quantity for a specific product.
- `resolve_transaction(transaction_id: str)`: Re-processes a transaction that is flagged as 'stuck'.
- `update_product_data(product_id: str, field: str, new_value: str)`: Updates a specific field in the product's master data record.

**Instructions:**
1. Analyze the provided "System Report" to identify all issues.
2. Provide a step-by-step "Analysis" of the problems, explaining your reasoning.
3. Generate a JSON object of "Tool Calls".
4. Your entire response must be a single, valid JSON object.

**JSON Response Format:**
```json
{
  "analysis": "Your detailed, step-by-step reasoning goes here.",
  "tool_calls": [
    {
      "function": "tool_name_1",
      "arguments": {
        "param1": "value1"
      }
    },
    {
      "function": "tool_name_2",
      "arguments": {
        "param1": "value1",
        "param2": "value2"
      }
    }
  ]
}
```

**CRITICAL:** Your output MUST be only the JSON object and nothing else.
"""

# --------------------------------------------------------------------------
# --- 3. SIMULATED SYSTEM DATA (THE AGENT'S "INPUT") ---
# --------------------------------------------------------------------------

system_report = """
System Report:
- Product ID 'PROD-12345' in 'MAIN-WH' is reporting a negative quantity of -5.
- Transaction 'TXN-98765' has been flagged as 'stuck' for 48 hours.
- The last audit of product 'PROD-67890' showed a supplier ID 'SUP-OLD' that does not match the master record 'SUP-NEW'.
"""

# --------------------------------------------------------------------------
# --- 4. CORE AGENT LOGIC ---
# --------------------------------------------------------------------------

def query_llm(prompt: str) -> dict:
    """
    Sends a prompt to the LLM server and returns the parsed JSON response.
    """
    headers = {"Content-Type": "application/json"}
    data = {
        "prompt": prompt,
        "n_predict": N_PREDICT,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "stop": STOP_TOKENS,
    }

    print("--- Sending Prompt to LLM Server ---")
    print(prompt)
    print("------------------------------------")

    try:
        response = requests.post(LLM_SERVER_URL, headers=headers, data=json.dumps(data), timeout=120)
        response.raise_for_status()

        result = response.json()
        llm_content = result.get('content', '').strip()

        print("\n--- Received Raw Response from LLM ---")
        print(llm_content)
        print("--------------------------------------\n")

        # UPDATED: More robust JSON cleaning logic. It now finds the first '{'
        # and the last '}' to better isolate the JSON object.
        match = re.search(r'\{.*\}', llm_content, re.DOTALL)
        if not match:
            print("ERROR: No valid JSON object found in the response.")
            return None
        
        json_string = match.group(0)

        return json.loads(json_string)

    except requests.exceptions.RequestException as e:
        print(f"ERROR: An error occurred while communicating with the LLM server: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to decode JSON from LLM response after cleaning.")
        print(f"       Problematic string was: '{json_string}'")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def run_agent_cycle():
    """
    Executes one full cycle of the agent's workflow.
    """
    print("==============================================")
    print("= INITIATING PROACTIVE INVENTORY AUDIT CYCLE =")
    print("==============================================\n")

    full_prompt = (
        f"<|system|>\n{SYSTEM_PROMPT}<|end|>\n"
        f"<|user|>\n{system_report}<|end|>\n"
        f"<|assistant|>\n"
        "```json\n"
    )

    structured_response = query_llm(full_prompt)

    if structured_response:
        print("--- Successfully Parsed LLM Output ---")
        print(json.dumps(structured_response, indent=2))
        print("--------------------------------------\n")
        print("AGENT CYCLE COMPLETE: Ready for next phase (Tool Execution).")
    else:
        print("AGENT CYCLE FAILED: Could not get a valid structured response from the LLM.")

# --------------------------------------------------------------------------
# --- 5. SCRIPT EXECUTION ---
# --------------------------------------------------------------------------

if __name__ == "__main__":
    run_agent_cycle()

