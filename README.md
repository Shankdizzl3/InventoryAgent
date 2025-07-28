# **LLM Agent for Support Tickets \- Proof of Concept (PoC)**

This repository contains a Proof of Concept (PoC) for an LLM-powered agent designed to simulate the resolution of IT support tickets by interacting with custom APIs. The current PoC focuses on demonstrating the agent's ability to interpret a ticket description and trigger a "Cancel PO" API call using a local Large Language Model (LLM) via Ollama and LangChain.

## **Project Structure**

llm\_poc/  
├── venv/                 \# Python virtual environment  
├── langchain\_tools.py    \# Defines the custom API as a LangChain Tool  
├── llm\_agent.py          \# Contains the LangChain Agent setup and execution logic  
├── ollama\_test.py        \# (Optional) Simple script to test Ollama Python integration  
└── README.md             \# This file

## **Setup Instructions**

Follow these steps to get the PoC running on your local machine.

### **1\. Install Ollama & Download Model**

First, ensure [Ollama](https://ollama.com/) is installed on your system.

Once installed, download the phi3:mini model, which is recommended for systems with 16GB RAM:

ollama pull phi3:mini

### **2\. Python Environment Setup**

It's highly recommended to use a Python virtual environment to manage project dependencies.

1. **Navigate to your project directory:**  
   cd path/to/your/llm\_poc

2. **Create a virtual environment:**  
   python \-m venv POC

3. **Activate the virtual environment:**  
   * **On Windows:**  
     .\\POC\\Scripts\\activate

   * **On macOS/Linux:**  
     source POC/bin/activate

(You should see (POC) at the beginning of your command prompt, indicating the virtual environment is active.)

4. **Install Python dependencies:**  
   pip install langchain langchain-community langchain-ollama pydantic requests

### **3\. Configure API Authorization Token**

The cancel\_po\_main\_record tool requires an authorization token to interact with your Admin Panel API.

1. Open langchain\_tools.py.  
2. Locate the AUTH\_TOKEN variable near the top of the file:  
   AUTH\_TOKEN \= "YOUR\_BEARER\_TOKEN\_HERE"

3. **Replace "YOUR\_BEARER\_TOKEN\_HERE" with your actual Bearer token.**  
   * **Important:** In a production environment, this token should be loaded from environment variables or a secure secrets management system, not hardcoded directly in the file.

### **4\. Configure Test PO Number**

For testing the cancel\_po\_main\_record tool, you'll need a valid test Purchase Order (PO) number from your IR/staging environment.

1. Open langchain\_tools.py.  
2. Locate the test\_po\_for\_tool variable in the if \_\_name\_\_ \== "\_\_main\_\_": block:  
   test\_po\_for\_tool \= "803080" \# Example, replace with a real test PO number

3. **Replace "803080" with a real, purely numeric PO number (as a string) that you can safely use for testing in your IR environment.**

## **How to Run the LLM Agent**

Once all setup steps are complete, you can run the agent script:

1. **Ensure your Ollama server is running in the background.** (You can verify by running ollama list in a new terminal, or by ensuring the Ollama service is active on your system).  
2. **Ensure your Python virtual environment is activated.**  
3. **Run the agent script:**  
   python llm\_agent.py

The script will execute three test scenarios:

1. A direct request to cancel a PO.  
2. A request the agent cannot handle (weather query).  
3. A request to cancel a PO with missing information (should prompt for it).

Observe the verbose output in your terminal to see the agent's thought process, tool calls, and final responses.

## **Future Work (Based on the 3-Day PoC Plan)**

This PoC focuses on the foundational pieces. Next steps for a more comprehensive solution would include:

* **ServiceNow API Integration:** Integrating with actual ServiceNow APIs for pulling tickets and updating records.  
* **Multiple Tools/Complex Tool Chaining:** Expanding the agent's capabilities to use multiple tools in sequence or concurrently.  
* **Error Handling & Fallback:** Implementing more robust error recovery and graceful degradation.  
* **Context Management/Memory:** Giving the LLM memory of past interactions within a conversation.  
* **RAG (Retrieval Augmented Generation):** Connecting the LLM to external knowledge bases for information retrieval.  
* **Production-Ready Code:** Refactoring the PoC code for production deployment, including robust logging, monitoring, and security.  
* **UI/Dashboard:** Developing a user interface for easier interaction beyond the command line.  
* **Performance Optimization:** Focusing on speed and efficiency for real-world usage.