import requests
import json

# --------------------------------------------------------------------------
# --- 1. CONFIGURATION ---
# --------------------------------------------------------------------------

# URL for the llama.cpp server endpoint
LLM_SERVER_URL = "http://localhost:8000/completion"

# LLM generation parameters
# These can be tuned to affect the creativity and length of the response
N_PREDICT = 1024       # Max number of tokens to generate
TEMPERATURE = 0.2    # Lower temperature for more deterministic, less creative output
TOP_P = 0.9          # Nucleus sampling parameter
STOP_TOKENS = ["\n"] # Tokens that will stop generation

# --------------------------------------------------------------------------
# --- 2. AGENT'S SYSTEM PROMPT & IDENTITY ---
# --------------------------------------------------------------------------

# This prompt defines the agent's mission, tools, and required output format.
# It is the core instruction that guides the LLM's reasoning process.
SYSTEM_PROMPT = """
You are a proactive Inventory Management Agent. Your task is to audit system logs, identify critical inventory discrepancies, and provide a detailed analysis followed by the precise, structured tool calls needed for a resolution. Always prioritize issues that affect product availability and transaction integrity.

**Available Tools:**
- `check_product_status(product_id: str)`: Retrieves the full inventory record for a given product ID.
- `adjust_quantity(product_id: str, new_quantity: int)`: Adjusts the inventory quantity for a specific product.
- `resolve_transaction(transaction_id: str)`: Re-processes a transaction that is flagged as 'stuck'.
- `update_product_data(product_id: str, field: str, new_value: str)`: Updates a specific field in the product's master data record.

**Instructions:**
1.  Analyze the provided "System Report" to identify all issues.
2.  Provide a step-by-step "Analysis" of the problems, explaining your reasoning for the chosen resolution path (Chain of Thought).
3.  Generate a JSON array of "Tool Calls" that contains the exact sequence of function calls required to fix the issues.
4.  Your entire response must be a single, valid JSON object with the keys "analysis" and "tool_calls".

**CRITICAL:** Your output MUST be only the JSON object and nothing else. Do not include any text before or after the JSON block.
"""

# --------------------------------------------------------------------------
# --- 3. SIMULATED SYSTEM DATA (THE AGENT'S "INPUT") ---
# --------------------------------------------------------------------------

# In a real-world scenario, this data would be fetched from a database or API.
# For now, we simulate a report that the agent needs to analyze.
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
        response = requests.post(LLM_SERVER_URL, headers=headers, data=json.dumps(data))
        response.raise_for_status()

        result = response.json()
        llm_content = result.get('content', '').strip()

        print("\n--- Received Raw Response from LLM ---")
        print(llm_content)
        print("--------------------------------------\n")

        # Attempt to parse the cleaned content as JSON
        return json.loads(llm_content)

    except requests.exceptions.RequestException as e:
        print(f"ERROR: An error occurred while communicating with the LLM server: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to decode JSON from LLM response.")
        print(f"       Raw content was: '{llm_content}'")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def run_agent_cycle():
    """
    Executes one full cycle of the agent's workflow:
    1. Constructs the full prompt.
    2. Queries the LLM.
    3. Prints the structured result.
    """
    print("==============================================")
    print("= INITIATING PROACTIVE INVENTORY AUDIT CYCLE =")
    print("==============================================\n")

    # Combine the system prompt with the specific input data for this cycle
    full_prompt = f"{SYSTEM_PROMPT}\n\nSystem Report:\n```\n{system_report}\n```\n\nJSON Response:"

    # Get the structured output from the LLM
    structured_response = query_llm(full_prompt)

    if structured_response:
        print("--- Successfully Parsed LLM Output ---")
        # Pretty-print the JSON for readability
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