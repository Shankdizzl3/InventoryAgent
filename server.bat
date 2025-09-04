@echo off
set LLAMA_CPP_DIR=C:\Users\mshank.GRANDRAPIDS\Desktop\llama.cpp
set MODEL_NAME=phi-3-mini-128k-instruct.Q4_K_M.gguf
set PORT=8000
set CONTEXT_SIZE=4096

set SERVER_EXECUTABLE=%LLAMA_CPP_DIR%\build\bin\Release\llama-server.exe

:: CORRECTED LINE: Points to the Release directory where you moved the model.
set MODEL_PATH=%LLAMA_CPP_DIR%\build\bin\Release\%MODEL_NAME%

if not exist "%SERVER_EXECUTABLE%" (
    echo [ERROR] Server executable not found at: %SERVER_EXECUTABLE%
    pause
    exit /b
)
if not exist "%MODEL_PATH%" (
    echo [ERROR] Model file not found at: %MODEL_PATH%
    echo [ERROR] The script is now looking in the 'build\bin\Release' folder.
    echo [ERROR] Verify the model file is actually there.
    pause
    exit /b
)

echo [INFO] Starting LLM server...
cd /d "%LLAMA_CPP_DIR%\build\bin\Release"
%SERVER_EXECUTABLE% -m "%MODEL_PATH%" -c %CONTEXT_SIZE% --port %PORT%