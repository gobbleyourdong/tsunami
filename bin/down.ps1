# Teardown the inference stack (Windows).
# SIGTERM (Stop-Process) first, force-kill (-Force) after 20s stragglers.

$ErrorActionPreference = "SilentlyContinue"

$Ports = @(8090, 8091, 8092, 8093, 8094, 8095)
$Names = @("proxy", "llama", "ernie", "controlnet", "qwen-edit", "wan-animate")

function Get-PortPids {
    param([int]$Port)
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conns) { return ($conns | Select-Object -ExpandProperty OwningProcess -Unique) }
    return @()
}

for ($i = 0; $i -lt $Ports.Count; $i++) {
    $port = $Ports[$i]
    $name = $Names[$i]
    $pids = Get-PortPids -Port $port
    if ($pids.Count -eq 0) {
        Write-Host "[skip] :$port ($name) not running"
        continue
    }
    Write-Host "[down] :$port ($name) — pids $($pids -join ', ')"
    foreach ($procId in $pids) {
        Stop-Process -Id $procId -ErrorAction SilentlyContinue
    }
}

# Wait up to 20s for graceful exit
$stillUp = @()
for ($i = 0; $i -lt 20; $i++) {
    $stillUp = @()
    foreach ($port in $Ports) {
        if ((Get-PortPids -Port $port).Count -gt 0) { $stillUp += $port }
    }
    if ($stillUp.Count -eq 0) { break }
    Start-Sleep -Seconds 1
}

if ($stillUp.Count -gt 0) {
    Write-Host "[force] still listening on: $($stillUp -join ' ') — force kill"
    foreach ($port in $stillUp) {
        $pids = Get-PortPids -Port $port
        foreach ($procId in $pids) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
}

Start-Sleep -Seconds 2
Write-Host ""
Write-Host "─── after teardown ───────────────────────────────────────────"
$listening = @()
foreach ($port in $Ports) {
    if ((Get-PortPids -Port $port).Count -gt 0) { $listening += $port }
}
if ($listening.Count -eq 0) {
    Write-Host "  (no target ports listening)"
} else {
    Write-Host "  still up: $($listening -join ', ')"
}
