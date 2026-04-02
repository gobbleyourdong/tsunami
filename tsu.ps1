# TSUNAMI — Windows entry point
# PowerShell equivalent of the `tsu` bash script
#Requires -Version 5.1

$ErrorActionPreference = 'Stop'

$DIR = Split-Path -Parent (Resolve-Path $MyInvocation.MyCommand.Path)
Set-Location $DIR

# ── Command dispatch ──────────────────────────────────────────────────────────
switch ($args[0]) {
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

function Find-LlamaServer {
    $cmd1 = Get-Command 'llama-server.exe' -EA SilentlyContinue
    $cmd2 = Get-Command 'llama-server' -EA SilentlyContinue
    $candidates = @(
        $(if ($cmd1) { $cmd1.Source }),
        $(if ($cmd2) { $cmd2.Source }),
        "$DIR\llama.cpp\llama-server.exe",
        "$DIR\llama.cpp\build\bin\Release\llama-server.exe",
        "$DIR\llama.cpp\build\bin\llama-server.exe",
        "$env:USERPROFILE\llama.cpp\llama-server.exe",
        "$env:USERPROFILE\llama.cpp\build\bin\Release\llama-server.exe",
        "$env:USERPROFILE\llama.cpp\build\bin\llama-server.exe"
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return $null
}

function Find-Model([string]$pattern) {
    # Use Where-Object -like instead of -Filter: the Windows file API used by
    # -Filter treats the first dot as an extension separator, so patterns like
    # 'Qwen3.5*' fail to match 'Qwen3.5-27B-Q8_0.gguf'.
    $found = Get-ChildItem -Path "$DIR\models" -EA SilentlyContinue |
             Where-Object { $_.Name -like $pattern } |
             Select-Object -First 1
    if ($found) { return $found.FullName }
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
        $llamaArgs = @('--host', '0.0.0.0', '--port', '8090', '--ctx-size', '16384', '--n-gpu-layers', '99')

        # Model priority: 27B dense > 122B MoE > smaller text model
        $dense27   = Find-Model 'Qwen3.5-27B*.gguf'
        $mmproj27  = @('mmproj-27B*.gguf','mmproj-BF16.gguf','mmproj-F16.gguf') |
                     ForEach-Object { Find-Model $_ } | Where-Object { $_ } | Select-Object -First 1
        $moeModel  = Find-Model '*122B*-00001-of-*.gguf'
        $textModel = @('Qwen3*-8B*.gguf','Qwen3*-2B*.gguf') |
                     ForEach-Object { Find-Model $_ } | Where-Object { $_ } | Select-Object -First 1
        $mmprojSmall = Find-Model 'mmproj-2B-BF16.gguf'

        # Windows CommandLineToArgvW strips unquoted double-quotes from JSON values
        # e.g. {"enable_thinking":false} → {enable_thinking:false} (keys unquoted)
        # Proper Windows escaping: wrap in quotes and escape inner quotes with backslash
        # '"{\"enable_thinking\":false}"' → command line: "{\"enable_thinking\":false}"
        # → CommandLineToArgvW result: {"enable_thinking":false}  ✓
        $noThinkingArg = '"{\"enable_thinking\":false}"'

        if ($dense27) {
            Write-Host "  starting 27B dense: $(Split-Path -Leaf $dense27)"
            $modelArgs = @('--model', $dense27) + $llamaArgs + @('-fa', 'on',
                '--cache-type-k', 'bf16', '--cache-type-v', 'bf16',
                '--jinja', '--chat-template-kwargs', $noThinkingArg)
            if ($mmproj27) { $modelArgs += @('--mmproj', $mmproj27) }
        } elseif ($moeModel) {
            Write-Host "  starting 122B MoE: $(Split-Path -Leaf $moeModel)"
            $modelArgs = @('--model', $moeModel) + $llamaArgs + @('-fa', 'on',
                '--cache-type-k', 'q8_0', '--cache-type-v', 'q8_0')
        } elseif ($textModel) {
            $vizNote = if ($mmprojSmall) { ' + vision' } else { '' }
            Write-Host "  starting $(Split-Path -Leaf $textModel)$vizNote"
            $modelArgs = @('--model', $textModel) + $llamaArgs + @('-fa', 'on',
                '--jinja', '--chat-template-kwargs', $noThinkingArg)
            if ($mmprojSmall) { $modelArgs += @('--mmproj', $mmprojSmall) }
        } else {
            Write-Warning "No .gguf model found in $DIR\models — run setup.ps1 to download models."
            $modelArgs = $null
        }

        if ($modelArgs) {
            $proc = Start-Process -FilePath $llama -ArgumentList $modelArgs `
                        -RedirectStandardOutput $logFile -RedirectStandardError "$logFile.err" `
                        -WindowStyle Hidden -PassThru
            $ModelPid = $proc.Id

            Write-Host "  waiting for model to load (up to 120s)..."
            $serverUp = $false
            for ($i = 0; $i -lt 120; $i++) {
                if (Test-ModelServer) { $serverUp = $true; break }
                Start-Sleep -Seconds 1
            }
            if ($serverUp) {
                Write-Host "  server is running on http://localhost:8090"
            } else {
                Write-Warning "model server failed to start within 120s -- check $logFile.err"
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

# ── Cleanup on exit ───────────────────────────────────────────────────────────
$CleanupBlock = {
    if ($ServerPid) {
        Stop-Process -Id $ServerPid -Force -EA SilentlyContinue
    }
    if ($ModelPid) {
        Stop-Process -Id $ModelPid -Force -EA SilentlyContinue
    }
}

# ── Launch frontend ───────────────────────────────────────────────────────────
# Refresh PATH in case Node was installed in this session (e.g. by setup.ps1)
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("PATH", "User")
try {
    $npx = Get-Command npx -EA SilentlyContinue
    $cliModules = Test-Path "$DIR\cli\node_modules"

    if ($npx -and $cliModules) {
        Set-Location "$DIR\cli"
        & npx tsx app.jsx @($args | Select-Object -Skip 1)
    } else {
        # Python REPL fallback
        Set-Location $DIR
        $replScript = @"
import sys, asyncio
sys.path.insert(0, r'$DIR')
from tsunami.agent import Agent
from tsunami.config import TsunamiConfig

async def main():
    config = TsunamiConfig.from_yaml('config.yaml')
    config = TsunamiConfig.from_env(config)
    agent = Agent(config)
    print('TSUNAMI -- type a task, press Enter. Type exit to quit.')
    print()
    while True:
        try:
            task = input('> ')
        except (EOFError, KeyboardInterrupt):
            break
        if task.strip().lower() in ('exit', 'quit', 'q'):
            break
        if not task.strip():
            continue
        result = await agent.run(task)
        print(result)
        print()

asyncio.run(main())
"@
        python -c $replScript
    }
} finally {
    & $CleanupBlock
}
