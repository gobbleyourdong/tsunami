# Bring up the consolidated inference stack (Windows).
#
#   :8090  tsunami proxy — FastAPI front-end
#   :8091  llama-server  — Gemma-4-26B-A4B MXFP4
#   :8092  ernie_server  — ERNIE-Image
#
# ERNIE_MODE env var:  gguf (default) | bf16 | base
#
# Idempotent. Run bin/down.ps1 for clean teardown.

$ErrorActionPreference = "Stop"

$ARK = (Resolve-Path "$PSScriptRoot\..").Path
$MODELS = if ($env:TSUNAMI_MODELS_DIR) { $env:TSUNAMI_MODELS_DIR } else { "$env:USERPROFILE\models_gguf" }
$LLAMA = "$ARK\bin\llama-server.exe"
$VENV_PY = if ($env:TSUNAMI_VENV) { "$env:TSUNAMI_VENV\Scripts\python.exe" } else { "$env:USERPROFILE\ComfyUI\comfyui-env\Scripts\python.exe" }
$LOG_DIR = $env:TEMP

# Fallback to python3/python on PATH if venv not found
if (-not (Test-Path $VENV_PY)) {
    $VENV_PY = (Get-Command python -ErrorAction SilentlyContinue).Source
}

$GEMMA_GGUF   = "$MODELS\gemma-4-26B-A4B-it-MXFP4_MOE.gguf"
$GEMMA_MMPROJ = "$MODELS\mmproj-26B-F16.gguf"
$ERNIE_GGUF   = "$MODELS\ernie-image-turbo-Q4_K_M.gguf"

function Test-PortListening {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $conn
}

function Wait-ForPort {
    param([int]$Port, [string]$Name, [string]$Path = "/health", [int]$Timeout = 240)
    Write-Host "  waiting for $Name on :$Port ..." -NoNewline
    for ($i = 0; $i -lt ($Timeout / 2); $i++) {
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:$Port$Path" -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop
            if ($r.StatusCode -eq 200) { Write-Host " ready"; return $true }
        } catch { }
        Start-Sleep -Seconds 2
    }
    Write-Host " TIMEOUT (still booting?)"
    return $false
}

function Start-BackgroundService {
    param([string]$Exe, [string[]]$Args, [string]$LogName)
    $logPath = Join-Path $LOG_DIR $LogName
    $p = Start-Process -FilePath $Exe -ArgumentList $Args `
        -RedirectStandardOutput $logPath -RedirectStandardError "$logPath.err" `
        -NoNewWindow -PassThru
    return $p
}

# ─── :8091 Gemma-4 agent ────────────────────────────────────────────────
if (Test-PortListening 8091) {
    Write-Host "[skip] :8091 already listening"
} else {
    Write-Host "[up]  :8091 llama-server (Gemma-4-26B-A4B MXFP4)"
    $gArgs = @(
        "--model", $GEMMA_GGUF,
        "--mmproj", $GEMMA_MMPROJ,
        "--port", "8091", "--host", "0.0.0.0",
        "-ngl", "999", "-c", "32768", "--jinja"
    )
    Start-BackgroundService -Exe $LLAMA -Args $gArgs -LogName "tsu-llama.log" | Out-Null
    Wait-ForPort -Port 8091 -Name "Gemma" -Path "/health" | Out-Null
}

# ─── :8092 ERNIE image-gen ──────────────────────────────────────────────
if (Test-PortListening 8092) {
    Write-Host "[skip] :8092 already listening"
} else {
    $mode = if ($env:ERNIE_MODE) { $env:ERNIE_MODE } else { "gguf" }
    switch ($mode) {
        "bf16" { $ernieArgs = @("--no-gguf", "--model", "Turbo"); $desc = "Turbo bf16 (16 GB, swap-capable)" }
        "base" { $ernieArgs = @("--no-gguf", "--model", "Base");  $desc = "ERNIE-Image Base (16 GB, 50-step keeper)" }
        default { $ernieArgs = @("--gguf", $ERNIE_GGUF, "--model", "Turbo"); $desc = "Turbo Q4_K_M (5 GB)" }
    }
    Write-Host "[up]  :8092 ernie_server ($desc)"
    $env:PYTHONPATH = $ARK
    $eArgs = @("-m", "tsunami.tools.ernie_server") + $ernieArgs + @(
        "--port", "8092", "--host", "0.0.0.0", "--pe-url", ""
    )
    Start-BackgroundService -Exe $VENV_PY -Args $eArgs -LogName "tsu-ernie.log" | Out-Null
    Wait-ForPort -Port 8092 -Name "ERNIE" -Path "/healthz" | Out-Null
}

# ─── :8090 tsunami proxy ────────────────────────────────────────────────
if (Test-PortListening 8090) {
    Write-Host "[skip] :8090 already listening"
} else {
    Write-Host "[up]  :8090 tsunami proxy"
    $env:LLAMA_SERVER_URL = "http://localhost:8091"
    $env:SD_SERVER_URL = "http://localhost:8092"
    $env:PYTHONPATH = $ARK
    $pArgs = @(
        "-u", "$ARK\tsunami\serve_transformers.py",
        "--model", "none", "--image-model", "none",
        "--port", "8090", "--host", "0.0.0.0"
    )
    Start-BackgroundService -Exe $VENV_PY -Args $pArgs -LogName "tsu-proxy.log" | Out-Null
    Wait-ForPort -Port 8090 -Name "proxy" -Path "/health" | Out-Null
}

$mode = if ($env:ERNIE_MODE) { $env:ERNIE_MODE } else { "gguf" }
Write-Host ""
Write-Host "─── Stack ready ───────────────────────────────────────────────"
Write-Host "  :8090  tsunami proxy              Get-Content $LOG_DIR\tsu-proxy.log -Wait"
Write-Host "  :8091  Gemma-4-26B-A4B (LM)       Get-Content $LOG_DIR\tsu-llama.log -Wait"
Write-Host "  :8092  ERNIE-Image ($mode)              Get-Content $LOG_DIR\tsu-ernie.log -Wait"
Write-Host ""
Write-Host "  Health:  curl :8090/health     curl :8091/health     curl :8092/healthz"
Write-Host ""
