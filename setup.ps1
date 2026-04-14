# TSUNAMI — One-Click Windows Installer (PowerShell)
# Usage:
#   iwr -useb https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/setup.ps1 | iex
#   — or —
#   .\setup.ps1
#
# Requirements: PowerShell 5.1+ or PowerShell 7+
#               Windows 10 / Windows Server 2019 or later
#               curl.exe (built-in on Windows 10 1803+)

# Don't stop on every error — we handle failures gracefully (mirrors `set +e` in bash)
$ErrorActionPreference = "Continue"

# ALWAYS pause before window closes — no matter what happens
trap {
    Write-Host ""
    Write-Host "  ERROR: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Press any key to close..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

# ---------------------------------------------------------------------------
# ANSI color helpers (PowerShell 5+ honours VT sequences when ANSI is enabled)
# ---------------------------------------------------------------------------
function Enable-Ansi {
    if ($PSVersionTable.PSVersion.Major -ge 7) { return }   # PS7 enables ANSI by default
    try {
        $null = [System.Console]::OutputEncoding
        $mode = [System.Console]::Out
        # Enable VT processing on Windows console
        $kernel32 = Add-Type -MemberDefinition @"
            [DllImport("kernel32.dll", SetLastError=true)]
            public static extern bool GetConsoleMode(IntPtr hConsoleHandle, out uint lpMode);
            [DllImport("kernel32.dll", SetLastError=true)]
            public static extern bool SetConsoleMode(IntPtr hConsoleHandle, uint dwMode);
            [DllImport("kernel32.dll", SetLastError=true)]
            public static extern IntPtr GetStdHandle(int nStdHandle);
"@ -Name "Kernel32Ansi" -Namespace "Win32" -PassThru
        $handle = [Win32.Kernel32Ansi]::GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        $consoleMode = 0
        [void][Win32.Kernel32Ansi]::GetConsoleMode($handle, [ref]$consoleMode)
        [void][Win32.Kernel32Ansi]::SetConsoleMode($handle, $consoleMode -bor 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    } catch { <# best-effort — colors may not render in older terminals #> }
}
Enable-Ansi

$ESC  = [char]27
$BOLD = "$ESC[1m"
$RST  = "$ESC[0m"
$GRN  = "$ESC[32m"
$YLW  = "$ESC[33m"
$RED  = "$ESC[31m"
$CYN  = "$ESC[36m"

function Write-Ok    { param([string]$msg) Write-Host "  ${GRN}✓${RST} $msg" }
function Write-Warn  { param([string]$msg) Write-Host "  ${YLW}⚠${RST} $msg" }
function Write-Fail  { param([string]$msg) Write-Host "  ${RED}✗${RST} $msg" }
function Write-Step  { param([string]$msg) Write-Host "  ${CYN}→${RST} $msg" }

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  ${BOLD}╔════════════════════════════════════╗${RST}"
Write-Host "  ${BOLD}║  tsunami — the tide rises          ║${RST}"
Write-Host "  ${BOLD}║   Local AI Agent, Zero Cloud      ║${RST}"
Write-Host "  ${BOLD}╚════════════════════════════════════╝${RST}"
Write-Host ""

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
$DIR        = if ($env:TSUNAMI_DIR) { $env:TSUNAMI_DIR } else { Join-Path $env:USERPROFILE "tsunami" }
$MODELS_DIR = Join-Path $DIR "models"

# ---------------------------------------------------------------------------
# GPU detection
# ---------------------------------------------------------------------------
$GPU       = "cpu"
$VRAM      = 0
$CUDA_ARCH = ""

# Check PATH, then known Windows locations (dual-GPU laptops, WoW64 redirect, NVSMI folder)
$nvidiaSmi = Get-Command "nvidia-smi" -ErrorAction SilentlyContinue
if (-not $nvidiaSmi) {
    $nvidiaPaths = @(
        "C:\Windows\System32\nvidia-smi.exe",
        "C:\Windows\Sysnative\nvidia-smi.exe",
        "$env:ProgramFiles\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
        "${env:ProgramFiles(x86)}\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
        "C:\Windows\SysWOW64\nvidia-smi.exe"
    )
    foreach ($p in $nvidiaPaths) {
        if (Test-Path $p) { $nvidiaSmi = Get-Item $p; break }
    }
}
if ($nvidiaSmi) {
    $GPU = "cuda"
    $nvsmi = if ($nvidiaSmi.Source) { $nvidiaSmi.Source } else { $nvidiaSmi.FullName }
    try {
        $vramRaw = (& $nvsmi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null |
                    Select-Object -First 1).Trim()
        if ($vramRaw -and $vramRaw -ne "[N/A]" -and $vramRaw -match '^\d+$') {
            $VRAM = [int]$vramRaw
            Write-Ok "NVIDIA GPU — ${VRAM}MB VRAM"
        } else {
            Write-Ok "NVIDIA GPU — unified memory"
        }
    } catch {
        Write-Ok "NVIDIA GPU detected (could not read VRAM)"
    }

    # Detect CUDA compute capability so cmake doesn't have to query the GPU at configure time
    # (cmake's "native" detection fails in some environments even when nvidia-smi works fine)
    try {
        $capRaw = (& $nvsmi --query-gpu=compute_cap --format=csv,noheader 2>$null |
                   Select-Object -First 1).Trim()
        if ($capRaw -and $capRaw -match '^\d+\.\d+$') {
            # Convert "8.6" → "86" (cmake arch format)
            $CUDA_ARCH = $capRaw -replace '\.', ''
        }
    } catch { }
} else {
    Write-Warn "No GPU detected — will run on CPU (very slow)"
    Write-Warn "  Install NVIDIA drivers and CUDA for GPU acceleration"
}

# ---------------------------------------------------------------------------
# RAM detection
# ---------------------------------------------------------------------------
$RAM = 0
try {
    $ramBytes = (Get-CimInstance Win32_PhysicalMemory -ErrorAction Stop |
                 Measure-Object -Property Capacity -Sum).Sum
    $RAM = [math]::Floor($ramBytes / 1GB)
} catch {
    # Fallback for older systems
    try {
        $os = Get-WmiObject -Class Win32_OperatingSystem
        $RAM = [math]::Floor($os.TotalVisibleMemorySize / 1MB)
    } catch {
        $RAM = 8   # safe default if detection fails
        Write-Warn "Could not detect RAM — assuming ${RAM}GB"
    }
}
Write-Host "  RAM: ${RAM}GB"

# ---------------------------------------------------------------------------
# Capacity / mode selection — use VRAM when available, RAM as fallback
# ---------------------------------------------------------------------------
$MODE = "full"

# Use VRAM for GPU machines, RAM only for CPU-only
$CAPACITY_GB = if ($GPU -eq "cuda" -and $VRAM -gt 0) {
    [math]::Ceiling($VRAM / 1024)
} else {
    $RAM
}
$CAPACITY_SRC = if ($GPU -eq "cuda" -and $VRAM -gt 0) { "VRAM" } else { "RAM" }

if ($CAPACITY_GB -lt 8) {
    $MODE = "degraded"
    Write-Host "  → ${CAPACITY_GB}GB ${CAPACITY_SRC}: degraded mode (Gemma 4 E4B at reduced context)"
} else {
    $MODE = "full"
    Write-Host "  → ${CAPACITY_GB}GB ${CAPACITY_SRC}: full mode (Gemma 4 E4B, 5GB)"
}

# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------
$MISSING = @()

function Test-Dep {
    param([string]$cmd, [string]$hint)
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        Write-Ok $cmd
        return $true
    } else {
        Write-Fail "$cmd missing — $hint"
        $script:MISSING += $cmd
        return $false
    }
}

function Install-ViaWinget {
    param([string]$pkgId, [string]$displayName)
    if (-not (Get-Command "winget" -ErrorAction SilentlyContinue)) {
        return $false
    }
    Write-Step "Installing $displayName via winget (this may take a minute)..."
    try {
        & winget install --id $pkgId --silent --accept-source-agreements --accept-package-agreements 2>&1 | Out-Null
        # Refresh PATH for the current session so newly-installed tools resolve
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        return $true
    } catch {
        return $false
    }
}

Write-Host ""
Write-Host "  Checking dependencies..."

# Auto-install git if missing — it's the bootstrap everything else needs.
# Tries winget first (built into Windows 10 1809+); falls back to a printed
# link that the user can follow manually.
if (-not (Get-Command "git" -ErrorAction SilentlyContinue)) {
    Write-Step "git not found — attempting auto-install..."
    if (Install-ViaWinget "Git.Git" "Git for Windows") {
        if (Get-Command "git" -ErrorAction SilentlyContinue) {
            Write-Ok "git (auto-installed)"
        } else {
            Write-Fail "git install reported success but the 'git' command is still missing. You may need to restart this PowerShell window, then re-run setup."
            $MISSING += "git"
        }
    } else {
        Test-Dep "git" "winget install Git.Git  OR  https://git-scm.com" | Out-Null
    }
} else {
    Write-Ok "git"
}

# Accept either python3 or python
$PYTHON = $null
if (Get-Command "python3" -ErrorAction SilentlyContinue) {
    $PYTHON = "python3"
    Write-Ok "python3"
} elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
    $pyVer = (& python --version 2>&1) -replace "Python ", ""
    if ($pyVer -match "^3\.") {
        $PYTHON = "python"
        Write-Ok "python `($pyVer`)"
    } else {
        Write-Fail "python3 missing (found Python 2) — https://python.org/downloads"
        $MISSING += "python3"
    }
} else {
    Write-Fail "python3 missing — https://python.org/downloads  OR  winget install Python.Python.3"
    $MISSING += "python3"
}

# Accept either pip3 or pip
$PIP = $null
if (Get-Command "pip3" -ErrorAction SilentlyContinue) {
    $PIP = "pip3"
    Write-Ok "pip3"
} elseif (Get-Command "pip" -ErrorAction SilentlyContinue) {
    $PIP = "pip"
    Write-Ok "pip"
} else {
    Write-Fail "pip missing — re-install Python with 'pip' option checked"
    $MISSING += "pip"
}

if (Get-Command "cmake" -ErrorAction SilentlyContinue) {
    Write-Ok "cmake"
} else {
    Write-Warn "cmake not found — not needed for prebuilt binaries, only if building from source"
}

# C++ build tools check
$hasBuildTools        = $false
$cmakeCudaGenerator   = ""      # e.g. "Visual Studio 17 2022" if we want to force it
$cudaAllowUnsupported = $false  # set true when cmake will use MSVC > VS 2022

if (Get-Command "cl.exe" -ErrorAction SilentlyContinue) {
    $hasBuildTools = $true

    # Use vswhere.exe to determine what cmake will actually pick (it always uses the
    # latest VS installation, which may differ from the cl.exe in PATH).
    $vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vsWhere) {
        try {
            # installationVersion: "17.x" = VS 2022, "18.x" = VS 2026, etc.
            $latestVsVer = (& $vsWhere -latest -property installationVersion 2>$null |
                            Select-Object -First 1).Trim()
            if ($latestVsVer -match '^(\d+)\.') {
                $latestVsMajor = [int]$Matches[1]
                if ($latestVsMajor -ge 18) {
                    # cmake will pick VS 2026+. CUDA 13.x only supports up to VS 2022.
                    # Prefer forcing VS 2022 generator if VS 2022 is also installed.
                    $vs2022Path = (& $vsWhere -version "[17.0,18.0)" -property installationPath 2>$null |
                                   Select-Object -First 1)
                    if ($vs2022Path) {
                        $cmakeCudaGenerator = "Visual Studio 17 2022"
                        Write-Ok "MSVC cl.exe (VS 2026+ present; will force VS 2022 generator for CUDA)"
                    } else {
                        # Only VS 2026+ available — must use -allow-unsupported-compiler
                        $cudaAllowUnsupported = $true
                        Write-Ok "MSVC cl.exe (VS 2026+ only; will use -allow-unsupported-compiler for CUDA)"
                    }
                } else {
                    Write-Ok "MSVC cl.exe (VS 20$(20 + $latestVsMajor - 17), C++ build tools)"
                }
            } else {
                Write-Ok "MSVC cl.exe (C++ build tools)"
            }
        } catch {
            Write-Ok "MSVC cl.exe (C++ build tools)"
        }
    } else {
        Write-Ok "MSVC cl.exe (C++ build tools)"
    }
} elseif (Get-Command "msbuild" -ErrorAction SilentlyContinue) {
    $hasBuildTools = $true
    Write-Ok "MSBuild (C++ build tools)"
} else {
    Write-Warn "C++ build tools not found in PATH (optional)"
}

# Node.js — install via winget if missing
if (Get-Command "node" -ErrorAction SilentlyContinue) {
    $nodeVer = (& node -v 2>$null)
    Write-Ok "node $nodeVer"
} else {
    Write-Step "Installing Node.js..."
    $nodeInstalled = $false

    if (Get-Command "winget" -ErrorAction SilentlyContinue) {
        & winget install --id OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
        # Refresh PATH in current session
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH", "User")
        if (Get-Command "node" -ErrorAction SilentlyContinue) {
            $nodeVer = (& node -v 2>$null)
            Write-Ok "Node.js $nodeVer installed via winget"
            $nodeInstalled = $true
        }
    }

    if (-not $nodeInstalled) {
        Write-Warn "Node.js install failed — agent works via Python REPL"
        Write-Warn "  Install manually: winget install OpenJS.NodeJS.LTS"
        Write-Warn "  OR download from https://nodejs.org"
    }
}

# Abort if critical deps are missing
if ($MISSING.Count -gt 0) {
    Write-Host ""
    Write-Fail "Missing dependencies: $($MISSING -join ', ')"
    Write-Host "    Install them and re-run this script."
    Write-Host ""; Write-Host "  Press any key to close..."; $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    return
}

# ---------------------------------------------------------------------------
# Clone or update repo
# ---------------------------------------------------------------------------
Write-Host ""
if (Test-Path (Join-Path $DIR ".git")) {
    Write-Step "Updating existing installation..."
    Push-Location $DIR
    & git pull --ff-only 2>&1 | Out-Null
    Pop-Location
} elseif (Test-Path (Join-Path $DIR "tsunami")) {
    # Installed by installer — files exist but no .git. Init for future updates.
    Write-Step "Initializing git for auto-updates..."
    Push-Location $DIR
    & git init -b main 2>&1 | Out-Null
    & git remote add origin "https://github.com/gobbleyourdong/tsunami.git" 2>&1 | Out-Null
    & git fetch origin main --quiet 2>&1 | Out-Null
    & git reset --hard origin/main 2>&1 | Out-Null
    & git branch --set-upstream-to=origin/main main 2>&1 | Out-Null
    Pop-Location
} else {
    Write-Step "Cloning tsunami..."
    & git clone https://github.com/gobbleyourdong/tsunami.git "$DIR"
}

# Ensure tsu.ps1 exists in install dir (may not be present in older installs)
$tsuPs1Dest = Join-Path $DIR "tsu.ps1"
if (-not (Test-Path $tsuPs1Dest)) {
    # tsu.ps1 is included in the repo — it should be present after clone/pull.
    # This fallback handles edge cases (e.g., running against an older checkout).
    $tsuPs1Url = "https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/tsu.ps1"
    try {
        Invoke-RestMethod -Uri $tsuPs1Url -OutFile $tsuPs1Dest -ErrorAction Stop
        Write-Ok "Downloaded tsu.ps1"
    } catch {
        Write-Fail "Could not download tsu.ps1 — re-clone the repo to get it."
    }
}

if (-not (Test-Path $DIR)) {
    Write-Fail "Repository clone failed — check your internet connection and try again."
    Write-Host ""; Write-Host "  Press any key to close..."; $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    return
}

Set-Location $DIR

# ---------------------------------------------------------------------------
# Python dependencies
# ---------------------------------------------------------------------------
Write-Step "Installing Python dependencies..."

# Install from requirements.txt first (core deps: httpx, pyyaml, rich, psutil, etc.)
$reqFile = Join-Path $DIR "requirements.txt"
if (Test-Path $reqFile) {
    $pipResult = & $PIP install -q -r $reqFile 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "pip install -r requirements.txt failed, retrying with --user flag..."
        & $PIP install --user -q -r $reqFile 2>&1 | Out-Null
    }
}

# SD-Turbo image generation (~2GB model, auto-downloads on first use)
Write-Step "Installing image generation (SD-Turbo)..."

# Install torch with CUDA support if GPU detected, CPU-only otherwise
if ($GPU -eq "cuda") {
    Write-Step "  Installing PyTorch with CUDA support..."
    & $PIP install -q torch --index-url https://download.pytorch.org/whl/cu128 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "CUDA torch failed, trying cu121..."
        & $PIP install -q torch --index-url https://download.pytorch.org/whl/cu121 2>&1 | Out-Null
    }
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "PyTorch with CUDA"
    } else {
        Write-Warn "CUDA torch failed — falling back to CPU"
        & $PIP install -q torch 2>&1 | Out-Null
    }
} else {
    & $PIP install -q torch --index-url https://download.pytorch.org/whl/cpu 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { & $PIP install -q torch 2>&1 | Out-Null }
}

$pyExtraDeps = @(
    "duckduckgo-search>=7",
    "diffusers",
    "transformers",
    "accelerate"
)
$pipResult = & $PIP install -q @pyExtraDeps 2>&1
if ($LASTEXITCODE -ne 0) {
    & $PIP install --user -q @pyExtraDeps 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "diffusers install failed -- image gen won't work"
    }
}

# Optional: playwright for undertow QA
Write-Step "Installing Playwright (undertow QA)..."
& $PIP install -q playwright 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    & $PYTHON -m playwright install chromium 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "Playwright (undertow QA)"
    } else {
        Write-Warn "Playwright browser install failed -- undertow QA won't work"
    }
} else {
    Write-Warn "Playwright skipped -- undertow QA won't work"
}

# ---------------------------------------------------------------------------
# Node / CLI frontend (optional)
# ---------------------------------------------------------------------------
$CLI_DIR = Join-Path $DIR "cli"
if ((Get-Command "node" -ErrorAction SilentlyContinue) -and (Test-Path $CLI_DIR)) {
    Write-Step "Installing CLI frontend..."
    Push-Location $CLI_DIR
    & npm install --silent 2>&1 | Out-Null
    Pop-Location
}

# ---------------------------------------------------------------------------
# Install model server dependencies (transformers + torch)
# ---------------------------------------------------------------------------
Write-Step "Installing model server dependencies (transformers, torch)..."
& $PYTHON -m pip install -q transformers accelerate 2>&1 | Out-Null

# Install PyTorch with CUDA if available
if ($GPU -eq "cuda") {
    Write-Step "Installing PyTorch with CUDA support..."
    & $PYTHON -m pip install -q torch --index-url https://download.pytorch.org/whl/cu128 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        & $PYTHON -m pip install -q torch --index-url https://download.pytorch.org/whl/cu121 2>&1 | Out-Null
    }
} else {
    Write-Step "Installing PyTorch (CPU)..."
    & $PYTHON -m pip install -q torch --index-url https://download.pytorch.org/whl/cpu 2>&1 | Out-Null
}

# SD-Turbo image generation
Write-Step "Installing SD-Turbo image generation..."
& $PYTHON -m pip install -q diffusers 2>&1 | Out-Null
Write-Ok "Model server dependencies installed"

# ---------------------------------------------------------------------------
# Model weights
# ---------------------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $MODELS_DIR | Out-Null
Write-Host ""
Write-Host "  Place merged HuggingFace model weights in: $MODELS_DIR\<model-name>\"
Write-Host "  The model directory should contain config.json + model files."
Write-Host "  SD-Turbo (~2GB) auto-downloads on first image generation via diffusers."

# ---------------------------------------------------------------------------
# Create global command
# ---------------------------------------------------------------------------
Write-Host ""

# 1. Add $DIR to user PATH so `tsu` is accessible from anywhere
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$DIR*") {
    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    [Environment]::SetEnvironmentVariable(
        "PATH",
        "$userPath;$DIR",
        "User"
    )
    Write-Ok "Added $DIR to user PATH"
}

# 3. Add 'tsunami' function to PowerShell profile
$tsuPs1  = Join-Path $DIR "tsu.ps1"
$psAlias = "function tsunami { & `"$tsuPs1`" @args }"
$profilePath = $PROFILE   # resolves to the current user's profile file

if (-not (Test-Path (Split-Path $profilePath -Parent))) {
    New-Item -ItemType Directory -Force -Path (Split-Path $profilePath -Parent) | Out-Null
}

if (-not (Test-Path $profilePath)) {
    New-Item -ItemType File -Force -Path $profilePath | Out-Null
}

$profileContent = ""
try { $profileContent = [System.IO.File]::ReadAllText($profilePath) } catch {}

$correctEntry = $psAlias -replace '"', '"'
if ($profileContent -match "function tsunami\s*\{[^}]*`"$([regex]::Escape($tsuPs1))`"") {
    # Correct function already present
    Write-Ok "'tsunami' already present in PowerShell profile"
} elseif ($profileContent -match "tsunami") {
    # Stale entry (old Set-Alias or wrong path) — replace it
    $lines = $profileContent -split "`n"
    $lines = $lines | Where-Object { $_ -notmatch '(Set-Alias.*tsunami|function tsunami)' }
    $cleaned = ($lines -join "`n").TrimEnd()
    $newContent = $cleaned + "`n`n# Tsunami AI Agent`n$psAlias`n"
    [System.IO.File]::WriteAllText($profilePath, $newContent)
    Write-Ok "Updated 'tsunami' entry in PowerShell profile"
} else {
    Add-Content -Path $profilePath -Value ""
    Add-Content -Path $profilePath -Value "# Tsunami AI Agent"
    Add-Content -Path $profilePath -Value $psAlias
    Write-Ok "Added 'tsunami' to PowerShell profile `($profilePath`)"
}

# ---------------------------------------------------------------------------
# Verify installation
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  Verifying..."
Set-Location $DIR

$verifyScript = @"
import sys, io
# Force UTF-8 output so Unicode characters don't crash on cp1252 consoles
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from tsunami.config import TsunamiConfig
from tsunami.tools import build_registry
config = TsunamiConfig.from_yaml('config.yaml')
registry = build_registry(config)
print(f'  [OK] Agent: {len(registry.schemas())} tools ready')
"@

$env:PYTHONIOENCODING = "utf-8"
$verifyResult = & $PYTHON -c $verifyScript 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host $verifyResult
} else {
    Write-Warn "Verification failed — check Python deps"
    # Show actual error so user knows what to fix
    $verifyResult | ForEach-Object { Write-Host "  $_" }
    Write-Warn "  Try: $PIP install -r $DIR\requirements.txt"
}

# ---------------------------------------------------------------------------
# List model directories
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  Models:"
if (Test-Path $MODELS_DIR) {
    Get-ChildItem -Path $MODELS_DIR -Directory | Where-Object {
        Test-Path (Join-Path $_.FullName "config.json")
    } | ForEach-Object {
        Write-Ok "$($_.Name)"
    }
}

# ---------------------------------------------------------------------------
# Final banner
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  ${BOLD}╔════════════════════════════════════════════╗${RST}"
Write-Host "  ${BOLD}║          TSUNAMI INSTALLED                 ║${RST}"
Write-Host "  ${BOLD}╠════════════════════════════════════════════╣${RST}"
Write-Host "  ${BOLD}║                                            ║${RST}"
Write-Host "  ${BOLD}║  1. Restart PowerShell  OR  run:          ║${RST}"
Write-Host "  ${BOLD}║       . `$PROFILE                           ║${RST}"
Write-Host "  ${BOLD}║  2. tsunami                                ║${RST}"
Write-Host "  ${BOLD}║                                            ║${RST}"
Write-Host "  ${BOLD}║  Or directly: cd $DIR${RST}"
Write-Host "  ${BOLD}║              .\tsu.ps1                      ║${RST}"
Write-Host "  ${BOLD}║                                            ║${RST}"
$gpuLabel = if ($GPU -eq "cuda") { "NVIDIA" } else { "CPU (no GPU detected)" }
Write-Host "  ${BOLD}║  $gpuLabel  |  ${CAPACITY_SRC}: ${CAPACITY_GB}GB  |  transformers${RST}"
Write-Host "  ${BOLD}║                                            ║${RST}"
Write-Host "  ${BOLD}╚════════════════════════════════════════════╝${RST}"
Write-Host ""
Write-Host "  ${YLW}NOTE: Restart PowerShell (or run '. `$PROFILE') to use the 'tsunami' command.${RST}"
Write-Host ""

# Keep window open when double-clicked
if ($Host.Name -eq 'ConsoleHost') {
    Write-Host "  Press any key to close..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
