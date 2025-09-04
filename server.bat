@echo off
:: ==========================================================================
:: == Batch Script to Start the llama.cpp LLM Server for the AI Agent      ==
:: ==========================================================================
:: This script automates the process of launching the llama-server.exe with
:: the correct model, context size, and port settings.
::
:: INSTRUCTIONS:
:: 1. UPDATE the 'LLAMA_CPP_DIR' variable to the main llama.cpp folder path.
:: 2. UPDATE the 'MODEL_NAME' variable with the exact filename of your model.
:: 3. Save this file.
:: 4. Double-click 'start_llm_server.bat' to run it.
:: ==========================================================================

echo [INFO] Setting up server configuration...

:: ---vvv--- PLEASE UPDATE THESE TWO VARIABLES ---vvv---

:: 1. Set the full path to your main 'llama.cpp' directory
::    Example: set LLAMA_CPP_DIR=C:\Users\YourName\Desktop\llama.cpp
set LLAMA_CPP_DIR=C:\Users\mshank.GRANDRAPIDS\Desktop\llama.cpp

:: 2. Set the exact filename of the GGUF model you downloaded.
::    This model should be located in the '%LLAMA_CPP_DIR%\models' folder.
set MODEL_NAME=phi-3-mini-128k-instruct.Q4_K_M.gguf

:: ---^^^--- PLEASE UPDATE THESE TWO VARIABLES ---^^^---

:: --- Server Parameters (can be changed if needed) ---
set PORT=8000
set CONTEXT_SIZE=4096

:: --- Constructing Paths ---
set SERVER_EXECUTABLE=%LLAMA_CPP_DIR%\build\bin\Release\llama-server.exe
:: FINAL CORRECTION: Added the missing backslash after '\models'
set MODEL_PATH=%LLAMA_CPP_DIR%\models%MODEL_NAME%

:: --- Validation ---
if not exist "%SERVER_EXECUTABLE%" (
echo [ERROR] Server executable not found at: %SERVER_EXECUTABLE%
echo [ERROR] Please check that your 'LLAMA_CPP_DIR' path is correct and that you have built the project.
pause
exit /b
)
if not exist "%MODEL_PATH%" (
echo [ERROR] Model file not found at: %MODEL_PATH%
echo [ERROR] Please check your 'LLAMA_CPP_DIR' and 'MODEL_NAME' variables. Make sure the model is in the 'models' subfolder.
pause
exit /b
)

:: --- Launch Server ---
echo [INFO] Starting LLM server on http://localhost:%PORT%
echo [INFO] Model: %MODEL_NAME%
echo [INFO] Context Size: %CONTEXT_SIZE%
echo.
echo    To stop the server, close this window or press CTRL+C.
echo.

:: Change directory to where the executable is, as in your README's Step 4.1
cd /d "%LLAMA_CPP_DIR%\build\bin\Release"
:: Run the command using the full path to the model, as in your README's Step 4.3
%SERVER_EXECUTABLE% -m "%MODEL_PATH%" -c %CONTEXT_SIZE% --port %PORT%

:: The script will end when the server is closed.