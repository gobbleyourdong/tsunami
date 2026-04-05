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
        # Kill llama-server by name
        Get-Process -Name "llama-server" -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
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
    'swarm' {
        $rest = @($args | Select-Object -Skip 1)
        if ($args.Length -lt 2 -or -not $rest[0]) {
            Write-Error 'Usage: tsu swarm "task description" [num_workers]'
            exit 1
        }
        $task = $rest[0]
        $workers = if ($rest.Length -gt 1) { $rest[1] } else { '2' }
        python -m tsunami.orchestrate $task $workers
        exit $LASTEXITCODE
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

function Find-LlamaServer {
    $cmd1 = Get-Command 'llama-server.exe' -EA SilentlyContinue
    $cmd2 = Get-Command 'llama-server' -EA SilentlyContinue
    $candidates = @(
        $(if ($cmd1) { $cmd1.Source }),
        $(if ($cmd2) { $cmd2.Source }),
        "$DIR\llama-server\llama-server.exe",
        "$DIR\llama.cpp\llama-server.exe",
        "$DIR\llama.cpp\build\bin\Release\llama-server.exe",
        "$DIR\llama.cpp\build\bin\llama-server.exe",
        "$env:USERPROFILE\tsunami\llama-server\llama-server.exe",
        "$env:USERPROFILE\tsunami\llama.cpp\llama-server.exe",
        "$env:USERPROFILE\tsunami\llama.cpp\build\bin\Release\llama-server.exe"
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return $null
}

function Find-Model([string]$pattern) {
    # Check multiple locations — installer vs setup.ps1 vs setup.bat
    $searchDirs = @(
        "$DIR\models",
        "$env:USERPROFILE\tsunami\models",
        "$DIR\..\models"
    )
    foreach ($d in $searchDirs) {
        $found = Get-ChildItem -Path $d -EA SilentlyContinue |
                 Where-Object { $_.Name -like $pattern } |
                 Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    return $null
}

# ── Start model server if not running ─────────────────────────────────────────
$ModelPid = $null
if (-not (Test-ModelServer)) {
    $llama = Find-LlamaServer
    if (-not $llama) {
        Write-Warning "llama-server not found — skipping model server. Run setup.ps1 to install."
    } else {
        $logFile = "$env:TEMP\llama-server.log"
        $llamaArgs = @('--host', '0.0.0.0', '--port', '8090', '--ctx-size', '32768', '--n-gpu-layers', '99')

        # Check VRAM — skip large models on <10GB cards
        $vramGB = 0
        try {
            $nvsmi = if (Get-Command "nvidia-smi" -EA SilentlyContinue) { "nvidia-smi" }
                     elseif (Test-Path "C:\Windows\Sysnative\nvidia-smi.exe") { "C:\Windows\Sysnative\nvidia-smi.exe" }
                     elseif (Test-Path "C:\Windows\System32\nvidia-smi.exe") { "C:\Windows\System32\nvidia-smi.exe" }
                     else { $null }
            if ($nvsmi) {
                $vramMB = [int](& $nvsmi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null |
                          Select-Object -First 1).Trim()
                $vramGB = [math]::Ceiling($vramMB / 1024)
            }
        } catch {}
        $degraded = $vramGB -gt 0 -and $vramGB -lt 8
        if ($degraded) { Write-Host "  ${vramGB}GB VRAM — degraded mode (reduced context)" }

        # Model: Gemma 4 E4B (single model for all roles)
        $gemmaModel = Find-Model 'gemma-4-E4B*.gguf'
        # Fallback: check for any .gguf model
        if (-not $gemmaModel) {
            $gemmaModel = @('gemma*.gguf','Qwen*.gguf') |
                ForEach-Object { Find-Model $_ } | Where-Object { $_ } | Select-Object -First 1
        }

        if ($gemmaModel) {
            Write-Host "  Loading model..."
            $ctxSize = if ($degraded) { '8192' } else { '16384' }
            $modelArgs = @('--model', $gemmaModel) + $llamaArgs + @('-fa', 'on',
                '--ctx-size', $ctxSize, '--parallel', '2')
        } else {
            Write-Warning "No .gguf model found in $DIR\models — run setup.ps1 to download models."
            $modelArgs = $null
        }

        if ($modelArgs) {
            $proc = Start-Process -FilePath $llama -ArgumentList $modelArgs `
                        -RedirectStandardOutput $logFile -RedirectStandardError "$logFile.err" `
                        -WindowStyle Hidden -PassThru
            $ModelPid = $proc.Id

            Write-Host "  Starting up..."
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
$bridgePath = Join-Path (Join-Path $DIR "desktop") "ws_bridge.py"
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
$watcherPath = Join-Path (Join-Path $DIR "desktop") "file_watcher.py"
if (Test-Path $watcherPath) {
    $watcherLog = Join-Path $env:TEMP "tsunami_watcher.log"
    $watcherProc = Start-Process -FilePath python -ArgumentList $watcherPath `
                       -WorkingDirectory $DIR `
                       -RedirectStandardOutput $watcherLog -RedirectStandardError "$watcherLog.err" `
                       -WindowStyle Hidden -PassThru
    $WatcherPid = $watcherProc.Id
    Write-Host "  File watcher on ws://localhost:3003"
}

# Start serve daemon (auto-serves Vite projects on port 9876)
$DaemonPid = $null
$daemonScript = @"
import sys, os
sys.path.insert(0, r'$DIR')
os.chdir(r'$DIR')
from tsunami.serve_daemon import run_daemon
run_daemon(workspace='./workspace', port=9876)
"@
$tmpDaemon = Join-Path $env:TEMP "tsunami_daemon_start.py"
$daemonScript | Set-Content $tmpDaemon -Encoding UTF8
$daemonLog = Join-Path $env:TEMP "tsunami_daemon.log"
$daemonProc = Start-Process -FilePath python -ArgumentList $tmpDaemon `
                  -WorkingDirectory $DIR `
                  -RedirectStandardOutput $daemonLog -RedirectStandardError "$daemonLog.err" `
                  -WindowStyle Hidden -PassThru
$DaemonPid = $daemonProc.Id
Write-Host "  Serve daemon on http://localhost:9876"

# ── Cleanup on exit ───────────────────────────────────────────────────────────
$CleanupBlock = {
    if ($WatcherPid) {
        Stop-Process -Id $WatcherPid -Force -EA SilentlyContinue
    }
    if ($DaemonPid) {
        Stop-Process -Id $DaemonPid -Force -EA SilentlyContinue
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
