# **LLM Agent Project Setup Guide**

This document outlines the steps required to set up a local LLM server on a Windows machine using llama.cpp and a quantized model. This guide is for a CPU-based inference workflow.

### **Prerequisites**

You must have the following software installed before proceeding:

1. **Git:** Used to clone the llama.cpp repository.  
   * **Link:** [https://git-scm.com/download/win](https://git-scm.com/download/win)  
2. **Visual Studio with C++ Build Tools:** Required to compile the llama.cpp C++ project.  
   * **Link:** [https://visualstudio.microsoft.com/downloads/](https://visualstudio.microsoft.com/downloads/)  
   * During installation, select the **"Desktop development with C++"** workload.  
3. **CMake:** A cross-platform build system that helps generate the project files for Visual Studio.  
   * **Link:** [https://cmake.org/download/](https://cmake.org/download/)  
   * During installation, be sure to check the option to **"Add CMake to system PATH for all users."**

### **Step 1: Download the llama.cpp Repository**

Open **Git Bash** and run the following command to download the project into your desired folder.

git clone https://github.com/ggerganov/llama.cpp.git  
cd llama.cpp

### **Step 2: Download the Quantized Model**

1. Navigate to the Hugging Face model page for the Phi-3 Mini GGUF model.  
   * **Link:** [https://huggingface.co/microsoft/Phi-3-mini-128k-instruct-GGUF](https://www.google.com/search?q=https://huggingface.co/microsoft/Phi-3-mini-128k-instruct-GGUF)  
2. Go to the **"Files and versions"** tab and download a suitable .gguf file (e.g., phi-3-mini-128k-instruct.Q4\_K\_M.gguf).  
3. Place the downloaded model file into the llama.cpp/models directory.

### **Step 3: Build the Project with CMake**

1. Open the **x64 Native Tools Command Prompt for VS** from the Start menu.  
2. Navigate to the llama.cpp directory.  
   cd C:\\Users\\mshank.GRANDRAPIDS\\Desktop\\llama.cpp

3. Run the following commands to configure and build the project, ensuring we disable the cURL feature to avoid errors.  
   mkdir build  
   cd build  
   cmake .. \-DLLAMA\_CURL=OFF  
   cmake \--build . \--config Release

### **Step 4: Run the LLM Server**

The build process created a set of executables in the build/bin/Release folder. To run the LLM as an API server, use the llama-server.exe executable.

1. Navigate to the Release directory.  
   cd build\\bin\\Release

2. Move the model file (phi-3-mini-128k-instruct.Q4\_K\_M.gguf) into this directory.  
3. Start the server on an available port (e.g., 8000).  
   .\\llama-server.exe \-m phi-3-mini-128k-instruct.Q4\_K\_M.gguf \-c 2048 \--port 8000

   * If port 8000 is in use, try another one (e.g., 8080, 8081).

### **Step 5: Interact with the Server via Python**

Once the server is running, you can use Python code to send requests to it.

1. Open a new terminal and install the requests library.  
   pip install requests

2. Create a Python file (e.g., client.py) and add the following code, ensuring the url matches the port you used to start the server.  
   import requests  
   import json

   url \= "http://localhost:8000/completion"

   prompt \= "A support ticket has come in about a stuck inventory transaction. It says 'Product ID 12345 is showing a negative quantity in the main warehouse'. What would you do first to solve this?"

   data \= {  
       "prompt": prompt,  
       "n\_predict": 256,  
       "temperature": 0.8,  
       "stop": \["\\n"\]  
   }

   headers \= {"Content-Type": "application/json"}

   try:  
       response \= requests.post(url, data=json.dumps(data), headers=headers)  
       response.raise\_for\_status()

       result \= response.json()

       if 'content' in result:  
           print("LLM Response:")  
           print(result\['content'\])  
       else:  
           print("Unexpected response format:", result)

   except requests.exceptions.RequestException as e:  
       print(f"An error occurred: {e}")

3. Run the Python script.  
   python client.py  
