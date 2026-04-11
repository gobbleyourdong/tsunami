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
set "LOG_DIR=%USERPROFILE%\tsunami-setup-logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%i"
if not defined STAMP set "STAMP=%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%-%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "STAMP=%STAMP: =0%"
set "LOG_FILE=%LOG_DIR%\setup-%STAMP%.log"

call :log "Tsunami setup started"

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
    echo   [OK] Python installed
    pause
    exit /b 0
)
echo   [OK] Python found
set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;%ProgramFiles%\Python312;%ProgramFiles%\Python312\Scripts;%PATH%"
echo   [..] Refreshing tsunami repo...
call :log "Running git clone"
set "PATH=%ProgramFiles%\Git\cmd;%ProgramFiles(x86)%\Git\cmd;%PATH%"
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
set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;%ProgramFiles%\Python312;%ProgramFiles%\Python312\Scripts;%PATH%"
python -m pip install -q httpx pyyaml ddgs pillow websockets fastapi uvicorn rich psutil >>"%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo   [X] Python package install failed
    echo       Log: %LOG_FILE%
    pause
    exit /b 1
)
echo   [OK] Python packages

echo   [..] Installing model server dependencies...
call :log "Installing transformers + torch"
python -m pip install -q transformers accelerate >>"%LOG_FILE%" 2>&1

REM Install PyTorch with CUDA if available
where nvidia-smi >nul 2>&1
if not errorlevel 1 (
    echo   [..] Installing PyTorch with CUDA support...
    python -m pip install -q torch --index-url https://download.pytorch.org/whl/cu128 >>"%LOG_FILE%" 2>&1
    if errorlevel 1 (
        python -m pip install -q torch --index-url https://download.pytorch.org/whl/cu121 >>"%LOG_FILE%" 2>&1
    )
) else (
    echo   [..] Installing PyTorch (CPU)...
    python -m pip install -q torch --index-url https://download.pytorch.org/whl/cpu >>"%LOG_FILE%" 2>&1
)
echo   [OK] Model server dependencies

echo   [..] Installing SD-Turbo image generation...
python -m pip install -q diffusers >>"%LOG_FILE%" 2>&1
echo   [OK] Image generation

if not exist "%MODELS_DIR%" mkdir "%MODELS_DIR%" >nul 2>&1
echo.
echo   Place merged HuggingFace model weights in: %MODELS_DIR%\^<model-name^>\
echo   The model directory should contain config.json + model files.

echo @echo off > "%TSUNAMI_DIR%\start.bat"
echo setlocal EnableExtensions EnableDelayedExpansion >> "%TSUNAMI_DIR%\start.bat"
echo title Tsunami >> "%TSUNAMI_DIR%\start.bat"
echo color 0B >> "%TSUNAMI_DIR%\start.bat"
echo echo Starting Tsunami... >> "%TSUNAMI_DIR%\start.bat"
echo cd /d "%TSUNAMI_DIR%" >> "%TSUNAMI_DIR%\start.bat"
echo start "" python desktop\ws_bridge.py >> "%TSUNAMI_DIR%\start.bat"
echo start "" python -m http.server 9876 --directory "%TSUNAMI_DIR%\desktop" >> "%TSUNAMI_DIR%\start.bat"
echo timeout /t 2 /nobreak ^>nul >> "%TSUNAMI_DIR%\start.bat"
echo start http://localhost:9876 >> "%TSUNAMI_DIR%\start.bat"

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
echo   Open: http://localhost:9876
echo.
pause
exit /b 0

:log
echo [%DATE% %TIME%] %~1>>"%LOG_FILE%"
goto :eof
