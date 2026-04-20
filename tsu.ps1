# TSUNAMI — Windows entry point
# PowerShell equivalent of the `tsu` bash script
#Requires -Version 5.1

$ErrorActionPreference = 'Stop'

$DIR = Split-Path -Parent (Resolve-Path $MyInvocation.MyCommand.Path)
Set-Location $DIR

# ── Auto-update on launch (silent, non-blocking) ────────────────────────────
if (Test-Path "$DIR\.git") {
    try {
        # Ensure tracking is set (installer may init without it)
        git branch --set-upstream-to=origin/main main 2>$null
        $local = (git rev-parse HEAD 2>$null).Trim()
        git fetch origin main --quiet 2>$null
        $remote = (git rev-parse origin/main 2>$null).Trim()
        if ($local -ne $remote) {
            git pull --ff-only --quiet 2>$null
            if ($LASTEXITCODE -eq 0) {
                $sha = (git rev-parse --short HEAD).Trim()
                Write-Host "  Updated to $sha"
            }
        }
    } catch { }  # offline is fine
}

# ── Command dispatch ──────────────────────────────────────────────────────────
switch ($args[0]) {
    { $_ -in 'kill', 'stop' } {
        Write-Host "  Killing all Tsunami processes..."
        # Kill by port
        foreach ($port in @(8090, 8092, 8094, 3000, 3002, 3003, 9876)) {
            $stale = netstat -ano 2>$null | Where-Object { $_ -match ":${port}\b" } | ForEach-Object {
                if ($_ -match '\s(\d+)\s*$') { $Matches[1] }
            } | Where-Object { $_ -and $_ -ne '0' } | Sort-Object -Unique
            foreach ($p in $stale) {
                try { Stop-Process -Id ([int]$p) -Force -EA SilentlyContinue } catch {}
            }
        }
        # Kill serve_transformers by command line
        try {
            Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='python3.exe'" -EA SilentlyContinue | Where-Object {
                $_.CommandLine -match "serve_transformers"
            } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
        } catch {}
        # Kill ALL orphaned Python scripts by command line (Get-CimInstance works on modern Windows)
        try {
            Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='python3.exe'" -EA SilentlyContinue | Where-Object {
                $_.CommandLine -match "tsunami_daemon_start|tsunami_server_start|ws_bridge|file_watcher|serve_daemon|tsunami\.server|tsunami\.cli|serve_diffusion"
            } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
        } catch {
            # Fallback for older Windows without Get-CimInstance
            Get-WmiObject Win32_Process -Filter "Name='python.exe' OR Name='python3.exe'" -EA SilentlyContinue | Where-Object {
                $_.CommandLine -match "tsunami_daemon_start|tsunami_server_start|ws_bridge|file_watcher|serve_daemon|tsunami\.server|tsunami\.cli|serve_diffusion"
            } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
        }
        Write-Host "  All processes killed"
        exit 0
    }
    'update' {
        Write-Host "  Updating Tsunami..."
        git pull --ff-only
        if ($LASTEXITCODE -eq 0) {
            $sha = git rev-parse --short HEAD
            Write-Host "  OK Updated to $sha"
        } else {
            Write-Host "  X Update failed"
        }
        exit $LASTEXITCODE
    }
    'version' {
        $sha = git rev-parse --short HEAD
        $date = (git log -1 --format='%ci') -replace ' .*', ''
        Write-Host "Tsunami $sha ($date)"
        exit 0
    }
}

# ── Helpers ───────────────────────────────────────────────────────────────────
function Test-ModelServer {
    try {
        $wc = New-Object System.Net.WebClient
        $result = $wc.DownloadString('http://localhost:8090/health')
        return $result -match '"ok"'
    } catch { return $false }
}

function Test-BackendServer {
    try {
        $wc = New-Object System.Net.WebClient
        $result = $wc.DownloadString('http://localhost:3000/api/health')
        return $true
    } catch { return $false }
}

# Kill stale servers from previous runs — prevents serving old code
function Kill-StaleServers {
    # Kill anything on our ports
    foreach ($port in @(3000, 3002, 3003, 8090, 8092, 8094, 9876)) {
        $stale = netstat -ano 2>$null | Where-Object { $_ -match ":${port}\b" -and $_ -match "LISTENING" } | ForEach-Object {
            if ($_ -match '\s(\d+)\s*$') { $Matches[1] }
        } | Where-Object { $_ -and $_ -ne '0' } | Sort-Object -Unique
        foreach ($p in $stale) {
            try { Stop-Process -Id ([int]$p) -Force -EA SilentlyContinue } catch {}
        }
    }
    # Also kill orphaned Python daemon/server scripts (by command line)
    try {
        Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='python3.exe'" -EA SilentlyContinue | Where-Object {
            $_.CommandLine -match "tsunami_daemon_start|tsunami_server_start|ws_bridge|file_watcher|serve_daemon|tsunami\.server|serve_diffusion"
        } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
    } catch {
        Get-WmiObject Win32_Process -Filter "Name='python.exe' OR Name='python3.exe'" -EA SilentlyContinue | Where-Object {
            $_.CommandLine -match "tsunami_daemon_start|tsunami_server_start|ws_bridge|file_watcher|serve_daemon|tsunami\.server|serve_diffusion"
        } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
    }
}
Kill-StaleServers

function Find-ModelDir {
    # Find a merged HuggingFace model directory (has config.json)
    $searchDirs = @(
        "$DIR\models",
        "$env:USERPROFILE\tsunami\models",
        "$DIR\..\models"
    )
    foreach ($d in $searchDirs) {
        if (-not (Test-Path $d)) { continue }
        $found = Get-ChildItem -Path $d -Directory -EA SilentlyContinue |
                 Where-Object { Test-Path (Join-Path $_.FullName "config.json") } |
                 Sort-Object LastWriteTime -Descending |
                 Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    return $null
}

# ── Start model server if not running ─────────────────────────────────────────
$ModelPid = $null
if (-not (Test-ModelServer)) {
    $serveScript = Join-Path $DIR "tsunami\serve_transformers.py"
    $modelDir = Find-ModelDir
    if (-not $modelDir) {
        Write-Warning "No model found — place merged HuggingFace weights in $DIR\models\"
    } elseif (-not (Test-Path $serveScript)) {
        Write-Warning "serve_transformers.py not found"
    } else {
        Write-Host "  Loading model: $(Split-Path $modelDir -Leaf)..."
        $logFile = "$env:TEMP\tsunami_model.log"
        $modelArgs = @($serveScript, '--model', $modelDir, '--port', '8090')
        $proc = Start-Process -FilePath python -ArgumentList $modelArgs `
                    -RedirectStandardOutput $logFile -RedirectStandardError "$logFile.err" `
                    -WindowStyle Hidden -PassThru
        $ModelPid = $proc.Id

        $serverUp = $false
        for ($i = 0; $i -lt 120; $i++) {
            if (Test-ModelServer) { $serverUp = $true; break }
            Start-Sleep -Seconds 1
        }
        if ($serverUp) {
            Write-Host "  Ready"
        } else {
            Write-Warning "Startup failed — check $logFile.err"
        }
    }
}

# ── Start Python WebSocket backend if not running ─────────────────────────────
$ServerPid = $null
if (-not (Test-BackendServer)) {
    $serverLog = "$env:TEMP\tsunami_server.log"
    $serverScript = @"
import sys, os
sys.path.insert(0, r'$DIR')
from tsunami.server import start_server
start_server(host='0.0.0.0', port=3000)
"@
    $tmpScript = "$env:TEMP\tsunami_server_start.py"
    $serverScript | Set-Content $tmpScript -Encoding UTF8
    $srvProc = Start-Process -FilePath python -ArgumentList $tmpScript `
                   -RedirectStandardOutput $serverLog -RedirectStandardError "$serverLog.err" `
                   -WindowStyle Hidden -PassThru
    $ServerPid = $srvProc.Id

    for ($i = 0; $i -lt 20; $i++) {
        if (Test-BackendServer) { break }
        Start-Sleep -Milliseconds 500
    }
}


# Start WebSocket bridge (agent to UI on port 3002)
$BridgePid = $null
$bridgePath = Join-Path (Join-Path $DIR "ui") "ws_bridge.py"
if (Test-Path $bridgePath) {
    $bridgeLog = Join-Path $env:TEMP "tsunami_bridge.log"
    $bridgeProc = Start-Process -FilePath python -ArgumentList $bridgePath `
                      -WorkingDirectory $DIR `
                      -RedirectStandardOutput $bridgeLog -RedirectStandardError "$bridgeLog.err" `
                      -WindowStyle Hidden -PassThru
    $BridgePid = $bridgeProc.Id
    Start-Sleep -Seconds 1
    Write-Host "  WebSocket bridge on ws://localhost:3002"
} else {
    Write-Warning "ws_bridge.py not found -- agent streaming disabled"
}

# Start file watcher (pushes file changes to UI on port 3003)
$WatcherPid = $null
$watcherPath = Join-Path (Join-Path $DIR "ui") "file_watcher.py"
if (Test-Path $watcherPath) {
    $watcherLog = Join-Path $env:TEMP "tsunami_watcher.log"
    $watcherProc = Start-Process -FilePath python -ArgumentList $watcherPath `
                       -WorkingDirectory $DIR `
                       -RedirectStandardOutput $watcherLog -RedirectStandardError "$watcherLog.err" `
                       -WindowStyle Hidden -PassThru
    $WatcherPid = $watcherProc.Id
    Write-Host "  File watcher on ws://localhost:3003"
}

# ── Cleanup on exit ───────────────────────────────────────────────────────────
$CleanupBlock = {
    if ($WatcherPid) {
        Stop-Process -Id $WatcherPid -Force -EA SilentlyContinue
    }
    if ($BridgePid) {
        Stop-Process -Id $BridgePid -Force -EA SilentlyContinue
    }
    if ($ServerPid) {
        Stop-Process -Id $ServerPid -Force -EA SilentlyContinue
    }
    if ($ModelPid) {
        Stop-Process -Id $ModelPid -Force -EA SilentlyContinue
    }
}

# ── Open WebUI in browser ────────────────────────────────────────────────────
# The FastAPI backend on :3000 serves the UI — just open it
Start-Process "http://localhost:3000"
Write-Host "  Tsunami is running at http://localhost:3000"
Write-Host "  Press Ctrl+C to stop"

# ── Keep alive + cleanup ─────────────────────────────────────────────────────
try {
    while ($true) { Start-Sleep -Seconds 1 }
} catch { } finally {
    & $CleanupBlock
}
