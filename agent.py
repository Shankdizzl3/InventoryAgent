import json
import os
import ollama
from dotenv import load_dotenv
import inventory_tools

load_dotenv()

# --------------------------------------------------------------------------
# --- 1. CONFIGURATION ---
# --------------------------------------------------------------------------

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi4-mini")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# --------------------------------------------------------------------------
# --- 2. TOOL DEFINITIONS ---
# Tool schemas tell the model what functions are available and how to call them.
# --------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_transactions_for_part",
            "description": (
                "Retrieves all transaction records from the IntegrationTransactions "
                "table for a specific part number."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "part_number": {
                        "type": "string",
                        "description": "The part number (PartID) to look up.",
                    }
                },
                "required": ["part_number"],
            },
        },
    },
]

# Map tool names to their Python implementations
TOOL_REGISTRY = {
    "get_transactions_for_part": inventory_tools.get_transactions_for_part,
}

# --------------------------------------------------------------------------
# --- 3. CORE AGENT LOGIC ---
# --------------------------------------------------------------------------

def run_agent(user_request: str):
    """
    Runs the inventory agent for a given user request.
    Uses Ollama's native tool calling — no regex or manual JSON parsing needed.
    """
    print("==============================================")
    print(f"USER: {user_request}")
    print("==============================================\n")

    messages = [{"role": "user", "content": user_request}]
    client = ollama.Client(host=OLLAMA_BASE_URL)

    # --- Turn 1: Ask the model what tool to call ---
    response = client.chat(
        model=OLLAMA_MODEL,
        messages=messages,
        tools=TOOLS,
    )
    msg = response.message

    # If the model wants to call a tool, execute it
    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = tool_call.function.arguments

            print(f"--- TOOL CALL: {fn_name}({fn_args}) ---")

            if fn_name in TOOL_REGISTRY:
                result = TOOL_REGISTRY[fn_name](**fn_args)
            else:
                result = json.dumps({"error": f"Unknown tool: {fn_name}"})

            print(f"--- TOOL RESULT: {len(result)} chars ---\n")

            # Append assistant tool call and tool result to conversation
            messages.append(msg)
            messages.append({
                "role": "tool",
                "content": result,
            })

        # --- Turn 2: Ask the model to summarize the results ---
        final_response = client.chat(
            model=OLLAMA_MODEL,
            messages=messages,
        )
        print("AGENT RESPONSE:")
        print(final_response.message.content)

    else:
        # Model responded directly without a tool call
        print("AGENT RESPONSE:")
        print(msg.content)

    print("\n==========================")
    print("= DONE                   =")
    print("==========================\n")


# --------------------------------------------------------------------------
# --- 4. SCRIPT EXECUTION ---
# --------------------------------------------------------------------------

if __name__ == "__main__":
    part_to_investigate = "YOUR_TEST_PART_NUMBER"  # <-- Change this
    run_agent(f"Pull all transaction information for part number {part_to_investigate}.")
