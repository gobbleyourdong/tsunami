@echo off
title Tsunami - Installing...
color 0B

echo.
echo   ========================================
echo    TSUNAMI - Autonomous AI Agent
echo    One-Click Windows Setup
echo   ========================================
echo.

set TSUNAMI_DIR=%USERPROFILE%\tsunami
set MODELS_DIR=%TSUNAMI_DIR%\models
set LLAMA_DIR=%TSUNAMI_DIR%\llama-server

:: Check for git
where git >nul 2>&1
if errorlevel 1 (
    echo   [!] Git not found. Installing via winget...
    winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements >nul 2>&1
    if errorlevel 1 (
        echo   [X] Install git manually: https://git-scm.com/download/win
        pause
        exit /b 1
    )
    echo   [OK] Git installed
)

:: Check for Python
where python >nul 2>&1
if errorlevel 1 (
    echo   [!] Python not found. Installing via winget...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements >nul 2>&1
    if errorlevel 1 (
        echo   [X] Install Python manually: https://python.org/downloads
        pause
        exit /b 1
    )
    echo   [OK] Python installed - RESTART this script after install
    pause
    exit /b 0
)
echo   [OK] Python found

:: Clone or update repo
if exist "%TSUNAMI_DIR%\.git" (
    echo   [..] Updating tsunami...
    cd /d "%TSUNAMI_DIR%"
    git pull --ff-only >nul 2>&1
) else (
    echo   [..] Cloning tsunami...
    git clone https://github.com/gobbleyourdong/tsunami.git "%TSUNAMI_DIR%" >nul 2>&1
)
cd /d "%TSUNAMI_DIR%"
echo   [OK] Repo ready

:: Python deps
echo   [..] Installing Python packages...
python -m pip install -q httpx pyyaml ddgs pillow websockets 2>nul
echo   [OK] Python packages

:: Download llama-server for Windows
if not exist "%LLAMA_DIR%\llama-server.exe" (
    echo.
    echo   [..] Downloading llama-server for Windows...
    mkdir "%LLAMA_DIR%" 2>nul

    :: Get latest release tag
    echo   Finding latest llama.cpp release...
    for /f "tokens=*" %%i in ('curl -sI https://github.com/ggerganov/llama.cpp/releases/latest 2^>nul ^| findstr /i "location:"') do set REDIR=%%i
    for /f "tokens=8 delims=/" %%i in ("%REDIR%") do set LLAMA_TAG=%%i
    :: Clean CR/LF
    set LLAMA_TAG=%LLAMA_TAG: =%
    if "%LLAMA_TAG%"=="" set LLAMA_TAG=b8611
    echo   Latest: %LLAMA_TAG%

    :: Download (CUDA for NVIDIA, CPU fallback)
    where nvidia-smi >nul 2>&1
    if errorlevel 1 (
        echo   No NVIDIA GPU - downloading CPU version...
        set LLAMA_URL=https://github.com/ggerganov/llama.cpp/releases/download/%LLAMA_TAG%/llama-%LLAMA_TAG%-bin-win-cpu-x64.zip
    ) else (
        echo   NVIDIA GPU found - downloading CUDA version...
        set LLAMA_URL=https://github.com/ggerganov/llama.cpp/releases/download/%LLAMA_TAG%/llama-%LLAMA_TAG%-bin-win-cuda-12.4-x64.zip
    )

    curl -fSL --progress-bar -o "%LLAMA_DIR%\llama-server.zip" "%LLAMA_URL%"
    if errorlevel 1 (
        echo   [!] CUDA download failed, trying CPU version...
        curl -fSL --progress-bar -o "%LLAMA_DIR%\llama-server.zip" "https://github.com/ggerganov/llama.cpp/releases/download/%LLAMA_TAG%/llama-%LLAMA_TAG%-bin-win-cpu-x64.zip"
    )

    :: Extract
    echo   [..] Extracting...
    powershell -Command "Expand-Archive -Force '%LLAMA_DIR%\llama-server.zip' '%LLAMA_DIR%'" 2>nul
    del "%LLAMA_DIR%\llama-server.zip" 2>nul

    :: Find the exe (might be in a subfolder)
    for /r "%LLAMA_DIR%" %%f in (llama-server.exe) do (
        if not "%%f"=="%LLAMA_DIR%\llama-server.exe" (
            move "%%f" "%LLAMA_DIR%\llama-server.exe" >nul 2>&1
        )
    )
)

if exist "%LLAMA_DIR%\llama-server.exe" (
    echo   [OK] llama-server ready
) else (
    echo   [X] llama-server download failed
    echo       Download manually from: https://github.com/ggerganov/llama.cpp/releases
    echo       Put llama-server.exe in %LLAMA_DIR%
    pause
    exit /b 1
)

:: Detect VRAM (NVIDIA) or RAM (CPU/integrated)
echo.
set VRAM_MB=0
set RAM_GB=8
where nvidia-smi >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%i in ('nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2^>nul') do set VRAM_MB=%%i
)
for /f "tokens=2 delims==" %%i in ('wmic computersystem get TotalPhysicalMemory /value 2^>nul') do set RAM_BYTES=%%i
set /a RAM_GB=%RAM_BYTES:~0,-9% 2>nul
if "%RAM_GB%"=="" set RAM_GB=8

if %VRAM_MB% GTR 0 (
    echo   GPU VRAM: %VRAM_MB%MB
    set /a VRAM_GB=%VRAM_MB%/1024
) else (
    echo   No NVIDIA GPU - using system RAM: %RAM_GB%GB
    set VRAM_GB=%RAM_GB%
)

:: Pick mode: need ~8GB for 9B + 2B, or 2GB for 2B only
set MODE=full
if %VRAM_GB% LSS 10 (
    set MODE=lite
    echo   [!] Under 10GB available - lite mode (2B only, 1.2GB download)
) else (
    echo   [OK] Full mode (9B wave + 2B eddies, 6.5GB download)
)

:: Download models
mkdir "%MODELS_DIR%" 2>nul

:: Always need 2B
if not exist "%MODELS_DIR%\Qwen3.5-2B-Q4_K_M.gguf" (
    echo   [..] Downloading 2B model - 1.2GB...
    curl -fSL --progress-bar -o "%MODELS_DIR%\Qwen3.5-2B-Q4_K_M.gguf" "https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf"
    echo   [OK] 2B model
) else (
    echo   [OK] 2B model already downloaded
)

:: Only download 9B if enough RAM
if "%MODE%"=="full" (
    if not exist "%MODELS_DIR%\Qwen3.5-9B-Q4_K_M.gguf" (
        echo   [..] Downloading 9B model - 5.3GB (this takes a few minutes^)...
        curl -fSL --progress-bar -o "%MODELS_DIR%\Qwen3.5-9B-Q4_K_M.gguf" "https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf"
        echo   [OK] 9B model
    ) else (
        echo   [OK] 9B model already downloaded
    )
)

:: Create start script based on mode
echo @echo off > "%TSUNAMI_DIR%\start.bat"
echo title Tsunami >> "%TSUNAMI_DIR%\start.bat"
echo color 0B >> "%TSUNAMI_DIR%\start.bat"
echo echo Starting Tsunami... >> "%TSUNAMI_DIR%\start.bat"
if "%MODE%"=="full" (
    echo start "" "%LLAMA_DIR%\llama-server.exe" -m "%MODELS_DIR%\Qwen3.5-9B-Q4_K_M.gguf" --port 8090 --ctx-size 32768 --parallel 1 --n-gpu-layers 99 --jinja --chat-template-kwargs "{\"enable_thinking\":false}" >> "%TSUNAMI_DIR%\start.bat"
    echo start "" "%LLAMA_DIR%\llama-server.exe" -m "%MODELS_DIR%\Qwen3.5-2B-Q4_K_M.gguf" --port 8092 --ctx-size 16384 --parallel 4 --n-gpu-layers 99 --jinja --chat-template-kwargs "{\"enable_thinking\":false}" >> "%TSUNAMI_DIR%\start.bat"
) else (
    echo start "" "%LLAMA_DIR%\llama-server.exe" -m "%MODELS_DIR%\Qwen3.5-2B-Q4_K_M.gguf" --port 8090 --ctx-size 16384 --parallel 1 --n-gpu-layers 99 --jinja --chat-template-kwargs "{\"enable_thinking\":false}" >> "%TSUNAMI_DIR%\start.bat"
    echo echo   Lite mode - 2B only >> "%TSUNAMI_DIR%\start.bat"
)
echo timeout /t 5 /nobreak ^>nul >> "%TSUNAMI_DIR%\start.bat"
echo cd /d "%TSUNAMI_DIR%" >> "%TSUNAMI_DIR%\start.bat"
echo python desktop\ws_bridge.py >> "%TSUNAMI_DIR%\start.bat"

:: Create desktop shortcut
echo Creating shortcut...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Tsunami.lnk'); $sc.TargetPath = '%TSUNAMI_DIR%\start.bat'; $sc.WorkingDirectory = '%TSUNAMI_DIR%'; $sc.Description = 'Tsunami AI Agent'; $sc.Save()" 2>nul

echo.
echo   ========================================
echo    TSUNAMI INSTALLED
echo   ========================================
echo.
echo   Desktop shortcut created: Tsunami
echo   Or run: %TSUNAMI_DIR%\start.bat
echo.
echo   Then open in browser:
echo   file:///%TSUNAMI_DIR:\=/%/desktop/index.html
echo.
pause
