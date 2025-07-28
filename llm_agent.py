import os
from langchain_ollama import OllamaLLM
from langchain.agents import AgentExecutor, create_react_agent # Changed to create_react_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Import your custom tool from the langchain_tools.py file
from langchain_tools import cancel_po_main_record

# --- Configuration ---
OLLAMA_MODEL = "llama3"

def setup_agent():
    """
    Sets up the Ollama LLM and a LangChain agent with the custom tool.
    """
    print(f"Initializing Ollama LLM with model: {OLLAMA_MODEL}")
    llm = OllamaLLM(model=OLLAMA_MODEL)

    tools = [cancel_po_main_record]

    # --- Agent Prompt for ReAct Agent ---
    # The ReAct agent requires a specific prompt structure for the LLM to follow.
    # It needs to know about the tools, tool names, and how to format its thoughts and actions.
    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessage(
                "You are an expert IT Support Assistant. Your primary goal is to resolve user "
                "requests by utilizing the available tools. "
                "Carefully analyze the user's request and determine if any of the tools "
                "can directly address it. If a tool is suitable, call it with the "
                "exact parameters extracted from the user's request. "
                "If no tool is suitable, respond by stating that you cannot fulfill the request "
                "and explain why, or ask for more information if needed. "
                "Always be concise and professional. "
                "You have access to the following tools:\n{tools}\n\n" # Tools description
                "Use the following format:\n\n"
                "Question: the input question you must answer\n"
                "Thought: you should always think about what to do\n"
                "Action: the action to take, should be one of [{tool_names}]\n" # Tool names for validation
                "Action Input: the input to the action\n"
                "Observation: the result of the action\n"
                "... (this Thought/Action/Action Input/Observation can repeat N times)\n"
                "Thought: I now know the final answer\n"
                "Final Answer: the final answer to the original input question"
            ),
            HumanMessage(content="{input}"), # This is where the user's query will go
            MessagesPlaceholder(variable_name="agent_scratchpad"), # This is where the agent's thoughts and tool calls will be displayed
        ]
    )

    print("Creating LangChain agent (ReAct type)...")
    # Create the agent using create_react_agent
    agent = create_react_agent(llm, tools, prompt)

    # Create the AgentExecutor. This is what actually runs the agent.
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

    print("Agent setup complete.")
    return agent_executor

if __name__ == "__main__":
    agent_executor = setup_agent()

    print("\n--- Testing Agent with a PO Cancellation Request ---")
    user_request_1 = "I need to cancel Purchase Order number 803080. Can you please process this?"
    print(f"User Request: {user_request_1}")
    try:
        response = agent_executor.invoke({"input": user_request_1})
        print("\nAgent's Final Response:")
        print(response["output"])
    except Exception as e:
        print(f"\nAn error occurred during agent invocation: {e}")
        print("Ensure Ollama is running and the 'llama3' model is available.")

    print("\n--- Testing Agent with a Request it cannot handle ---")
    user_request_2 = "What is the current weather in London?"
    print(f"User Request: {user_request_2}")
    try:
        response = agent_executor.invoke({"input": user_request_2})
        print("\nAgent's Final Response:")
        print(response["output"])
    except Exception as e:
        print(f"\nAn error occurred during agent invocation: {e}")
