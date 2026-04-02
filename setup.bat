@echo off
setlocal EnableExtensions EnableDelayedExpansion
if defined TSUNAMI_SETUP_RUNNING exit /b 0
set "TSUNAMI_SETUP_RUNNING=1"

title Tsunami - Installing...
color 0B

set "TSUNAMI_DIR=%USERPROFILE%\tsunami"

if exist "%TSUNAMI_DIR%" (
    echo.
    choice /c YN /n /m "Existing tsunami install found. Upgrade? [Y/N]: "
    if errorlevel 2 exit /b
    if errorlevel 1 rmdir /s /q "%TSUNAMI_DIR%"
)

set "MODELS_DIR=%TSUNAMI_DIR%\models"
set "LLAMA_DIR=%TSUNAMI_DIR%\llama-server"
set "LOG_DIR=%USERPROFILE%\tsunami-setup-logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%i"
if not defined STAMP set "STAMP=%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%-%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "STAMP=%STAMP: =0%"
set "LOG_FILE=%LOG_DIR%\setup-%STAMP%.log"

set "CUDA_MAJOR="
set "CUDA_FLAVOR="
set "LLAMA_MAIN_URL="
set "LLAMA_DLL_URL="
set "LLAMA_CPU_URL=https://github.com/ggml-org/llama.cpp/releases/download/b8628/llama-b8628-bin-win-cpu-x64.zip"

call :log "Tsunami setup started"
call :log "Environment initialized"

echo.
echo   ========================================
echo    TSUNAMI - Autonomous AI Agent
echo    One-Click Windows Setup
echo   ========================================
echo.
echo   Logging to: %LOG_FILE%

where git >nul 2>&1
if errorlevel 1 (
    echo   [!] Git not found. Installing via winget...
    winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements >>"%LOG_FILE%" 2>&1
    if errorlevel 1 (
        echo   [X] Install git manually: https://git-scm.com/download/win
        echo       Log: %LOG_FILE%
        pause
        exit /b 1
    )
    echo   [OK] Git installed
)

where python >nul 2>&1
if errorlevel 1 (
    echo   [!] Python not found. Installing via winget...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements >>"%LOG_FILE%" 2>&1
    if errorlevel 1 (
        echo   [X] Install Python manually: https://python.org/downloads
        echo       Log: %LOG_FILE%
        pause
        exit /b 1
    )
    echo   [OK] Python installed - RESTART this script after install
    pause
    exit /b 0
)
echo   [OK] Python found

echo   [..] Refreshing tsunami repo...
call :log "Running git clone"
git clone https://github.com/gobbleyourdong/tsunami.git "%TSUNAMI_DIR%" >>"%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo   [X] Git clone failed
    echo       Log: %LOG_FILE%
    pause
    exit /b 1
)
cd /d "%TSUNAMI_DIR%"
echo   [OK] Repo ready

echo   [..] Installing Python packages...
call :log "Installing Python packages"
python -m pip install -q httpx pyyaml ddgs pillow websockets >>"%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo   [X] Python package install failed
    echo       Log: %LOG_FILE%
    pause
    exit /b 1
)
echo   [OK] Python packages

call :detect_cuda
call :log "CUDA detected major=!CUDA_MAJOR! flavor=!CUDA_FLAVOR!"
call :log "CUDA main URL: !LLAMA_MAIN_URL!"
call :log "CUDA DLL URL: !LLAMA_DLL_URL!"

if not exist "%LLAMA_DIR%\llama-server.exe" (
    echo.
    echo   [..] Downloading llama-server for Windows...
    if not exist "%LLAMA_DIR%" mkdir "%LLAMA_DIR%" >nul 2>&1

    set "USE_GPU=0"
    if defined LLAMA_MAIN_URL if defined LLAMA_DLL_URL set "USE_GPU=1"

    if "!USE_GPU!"=="1" (
        echo   NVIDIA GPU found - downloading Windows x64 ^(CUDA !CUDA_FLAVOR!^)...
        echo   Main package: !LLAMA_MAIN_URL!
        echo   CUDA DLLs:    !LLAMA_DLL_URL!
        call :log "Using CUDA llama package: !LLAMA_MAIN_URL!"
        call :log "Using CUDA DLL package: !LLAMA_DLL_URL!"
        curl -fL --progress-bar -o "%LLAMA_DIR%\llama-server.zip" "!LLAMA_MAIN_URL!"
        >>"%LOG_FILE%" 2>&1 curl -I -L "!LLAMA_MAIN_URL!"
        if errorlevel 1 (
            echo   [!] CUDA package download failed, trying CPU version...
            call :log "CUDA package failed; falling back to CPU package: %LLAMA_CPU_URL%"
            set "USE_GPU=0"
            curl -fL --progress-bar -o "%LLAMA_DIR%\llama-server.zip" "%LLAMA_CPU_URL%"
            >>"%LOG_FILE%" 2>&1 curl -I -L "%LLAMA_CPU_URL%"
            if errorlevel 1 (
                echo   [X] CPU fallback download failed
                echo       Log: %LOG_FILE%
                pause
                exit /b 1
            )
        )
    ) else (
        echo   No compatible NVIDIA CUDA version detected - downloading CPU package...
        call :log "Using CPU llama package: %LLAMA_CPU_URL%"
        curl -fL --progress-bar -o "%LLAMA_DIR%\llama-server.zip" "%LLAMA_CPU_URL%"
        >>"%LOG_FILE%" 2>&1 curl -I -L "%LLAMA_CPU_URL%"
        if errorlevel 1 (
            echo   [X] CPU package download failed
            echo       Log: %LOG_FILE%
            pause
            exit /b 1
        )
    )

    echo   [..] Extracting llama.cpp package...
    powershell -NoProfile -Command "Expand-Archive -Force '%LLAMA_DIR%\llama-server.zip' '%LLAMA_DIR%'" >>"%LOG_FILE%" 2>&1
    if errorlevel 1 (
        echo   [X] llama package extraction failed
        echo       Log: %LOG_FILE%
        pause
        exit /b 1
    )
    del "%LLAMA_DIR%\llama-server.zip" >nul 2>&1

    if "!USE_GPU!"=="1" (
        echo   [..] Downloading CUDA runtime DLLs...
        curl -fL --progress-bar -o "%LLAMA_DIR%\cudart.zip" "!LLAMA_DLL_URL!"
        >>"%LOG_FILE%" 2>&1 curl -I -L "!LLAMA_DLL_URL!"
        if errorlevel 1 (
            echo   [!] CUDA DLL download failed - continuing without bundled DLLs
            call :log "CUDA DLL download failed"
        ) else (
            echo   [..] Extracting CUDA runtime DLLs...
            powershell -NoProfile -Command "Expand-Archive -Force '%LLAMA_DIR%\cudart.zip' '%LLAMA_DIR%'" >>"%LOG_FILE%" 2>&1
            if errorlevel 1 (
                echo   [!] CUDA DLL extraction failed
                call :log "CUDA DLL extraction failed"
            )
            del "%LLAMA_DIR%\cudart.zip" >nul 2>&1
        )
    )

    for /r "%LLAMA_DIR%" %%f in (llama-server.exe) do (
        if /I not "%%~ff"=="%LLAMA_DIR%\llama-server.exe" move /Y "%%~ff" "%LLAMA_DIR%\llama-server.exe" >nul 2>&1
    )
)

if exist "%LLAMA_DIR%\llama-server.exe" (
    echo   [OK] llama-server ready
) else (
    echo   [X] llama-server download failed
    echo       Expected at: %LLAMA_DIR%\llama-server.exe
    echo       Log: %LOG_FILE%
    pause
    exit /b 1
)

echo.
set "VRAM_MB=0"
set "VRAM_GB=0"
set "RAM_GB=8"
set "RAM_BYTES="
set "VRAM_RAW="

where nvidia-smi >nul 2>&1
if not errorlevel 1 (
    for /f "usebackq skip=1 tokens=1 delims=," %%i in (`nvidia-smi --query-gpu=memory.total --format=csv 2^>nul`) do (
        if not defined VRAM_RAW set "VRAM_RAW=%%i"
    )
)

if defined VRAM_RAW (
    set "VRAM_RAW=!VRAM_RAW: MiB=!"
    set "VRAM_RAW=!VRAM_RAW:MB=!"
    set "VRAM_RAW=!VRAM_RAW: =!"
    2>nul set /a VRAM_MB=!VRAM_RAW!+0
    if errorlevel 1 set "VRAM_MB=0"
)

for /f "tokens=2 delims==" %%i in ('wmic computersystem get TotalPhysicalMemory /value 2^>nul') do set "RAM_BYTES=%%i"
if defined RAM_BYTES (
    2>nul set /a RAM_GB=!RAM_BYTES!/1024/1024/1024
    if errorlevel 1 set "RAM_GB=8"
)

if %VRAM_MB% GTR 0 (
    echo   GPU VRAM: %VRAM_MB%MB
    set /a VRAM_GB=%VRAM_MB%/1024
) else (
    echo   No NVIDIA GPU detected - using system RAM: %RAM_GB%GB
    set "VRAM_GB=%RAM_GB%"
)

set "MODE=full"
if %VRAM_GB% LSS 10 (
    set "MODE=lite"
    echo   [!] Under 10GB available - lite mode ^(2B only, 1.2GB download^)
) else (
    echo   [OK] Full mode ^(9B wave + 2B eddies, 6.5GB download^)
)

if not exist "%MODELS_DIR%" mkdir "%MODELS_DIR%" >nul 2>&1

if not exist "%MODELS_DIR%\Qwen3.5-2B-Q4_K_M.gguf" (
    echo   [..] Downloading 2B model - 1.2GB...
    curl -fL --progress-bar -o "%MODELS_DIR%\Qwen3.5-2B-Q4_K_M.gguf" "https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf"
    >>"%LOG_FILE%" 2>&1 curl -I -L "https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf"
    if errorlevel 1 (
        echo   [X] 2B model download failed
        echo       Log: %LOG_FILE%
        pause
        exit /b 1
    )
    echo   [OK] 2B model
) else (
    echo   [OK] 2B model already downloaded
)

if /I "%MODE%"=="full" (
    if not exist "%MODELS_DIR%\Qwen3.5-9B-Q4_K_M.gguf" (
        echo   [..] Downloading 9B model - 5.3GB ^(this takes a few minutes^)...
        curl -fL --progress-bar -o "%MODELS_DIR%\Qwen3.5-9B-Q4_K_M.gguf" "https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf"
        >>"%LOG_FILE%" 2>&1 curl -I -L "https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf"
        if errorlevel 1 (
            echo   [X] 9B model download failed
            echo       Log: %LOG_FILE%
            pause
            exit /b 1
        )
        echo   [OK] 9B model
    ) else (
        echo   [OK] 9B model already downloaded
    )
)

echo @echo off > "%TSUNAMI_DIR%\start.bat"
echo setlocal EnableExtensions EnableDelayedExpansion >> "%TSUNAMI_DIR%\start.bat"
echo title Tsunami >> "%TSUNAMI_DIR%\start.bat"
echo color 0B >> "%TSUNAMI_DIR%\start.bat"
echo echo Starting Tsunami... >> "%TSUNAMI_DIR%\start.bat"
if /I "%MODE%"=="full" (
    echo start "" "%LLAMA_DIR%\llama-server.exe" -m "%MODELS_DIR%\Qwen3.5-9B-Q4_K_M.gguf" --port 8090 --ctx-size 32768 --parallel 1 --n-gpu-layers 99 --jinja --chat-template-kwargs "{\"enable_thinking\":false}" >> "%TSUNAMI_DIR%\start.bat"
    echo start "" "%LLAMA_DIR%\llama-server.exe" -m "%MODELS_DIR%\Qwen3.5-2B-Q4_K_M.gguf" --port 8092 --ctx-size 16384 --parallel 4 --n-gpu-layers 99 --jinja --chat-template-kwargs "{\"enable_thinking\":false}" >> "%TSUNAMI_DIR%\start.bat"
) else (
    echo start "" "%LLAMA_DIR%\llama-server.exe" -m "%MODELS_DIR%\Qwen3.5-2B-Q4_K_M.gguf" --port 8090 --ctx-size 16384 --parallel 1 --n-gpu-layers 99 --jinja --chat-template-kwargs "{\"enable_thinking\":false}" >> "%TSUNAMI_DIR%\start.bat"
    echo echo   Lite mode - 2B only >> "%TSUNAMI_DIR%\start.bat"
)
echo timeout /t 5 /nobreak ^>nul >> "%TSUNAMI_DIR%\start.bat"
echo cd /d "%TSUNAMI_DIR%" >> "%TSUNAMI_DIR%\start.bat"
echo python desktop\ws_bridge.py >> "%TSUNAMI_DIR%\start.bat"
echo start "" "%TSUNAMI_DIR%\desktop\index.html" >> "%TSUNAMI_DIR%\start.bat"

echo Creating shortcut...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Tsunami.lnk'); $sc.TargetPath = '%TSUNAMI_DIR%\start.bat'; $sc.WorkingDirectory = '%TSUNAMI_DIR%'; $sc.Description = 'Tsunami AI Agent'; $sc.Save()" >>"%LOG_FILE%" 2>&1

echo.
echo   ========================================
echo    TSUNAMI INSTALLED
echo   ========================================
echo.
echo   Desktop shortcut created: Tsunami
echo   Or run: %TSUNAMI_DIR%\start.bat
echo   Log: %LOG_FILE%
echo.
echo   Then open in browser:
echo   file:///%TSUNAMI_DIR:\=/%/desktop/index.html
echo.
pause
exit /b 0

:detect_cuda
set "CUDA_MAJOR="
set "CUDA_FLAVOR="
set "LLAMA_MAIN_URL="
set "LLAMA_DLL_URL="
where nvidia-smi >nul 2>&1
if errorlevel 1 goto :eof
for /f "tokens=9" %%a in ('nvidia-smi 2^>nul ^| findstr /C:"CUDA Version:"') do set "CUDA_VERSION=%%a"
if not defined CUDA_VERSION goto :eof
for /f "tokens=1 delims=." %%a in ("!CUDA_VERSION!") do set "CUDA_MAJOR=%%~a"
if "!CUDA_MAJOR!"=="12" (
    set "CUDA_FLAVOR=12.4"
    set "LLAMA_MAIN_URL=https://github.com/ggml-org/llama.cpp/releases/download/b8628/llama-b8628-bin-win-cuda-12.4-x64.zip"
    set "LLAMA_DLL_URL=https://github.com/ggml-org/llama.cpp/releases/download/b8628/cudart-llama-bin-win-cuda-12.4-x64.zip"
) else if "!CUDA_MAJOR!"=="13" (
    set "CUDA_FLAVOR=13.1"
    set "LLAMA_MAIN_URL=https://github.com/ggml-org/llama.cpp/releases/download/b8628/llama-b8628-bin-win-cuda-13.1-x64.zip"
    set "LLAMA_DLL_URL=https://github.com/ggml-org/llama.cpp/releases/download/b8628/cudart-llama-bin-win-cuda-13.1-x64.zip"
) else if defined CUDA_MAJOR (
    2>nul set /a _cuda_test=!CUDA_MAJOR!+0
    if not errorlevel 1 if !_cuda_test! GEQ 13 (
        set "CUDA_FLAVOR=13.1"
        set "LLAMA_MAIN_URL=https://github.com/ggml-org/llama.cpp/releases/download/b8628/llama-b8628-bin-win-cuda-13.1-x64.zip"
        set "LLAMA_DLL_URL=https://github.com/ggml-org/llama.cpp/releases/download/b8628/cudart-llama-bin-win-cuda-13.1-x64.zip"
    )
)
goto :eof

:log
echo [%DATE% %TIME%] %~1>>"%LOG_FILE%"
goto :eof
