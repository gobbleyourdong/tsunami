# TSUNAMI — One-Click Windows Installer (PowerShell)
# Usage:
#   iwr -useb https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/setup.ps1 | iex
#   — or —
#   .\setup.ps1
#
# Requirements: PowerShell 5.1+ or PowerShell 7+
#               Windows 10 / Windows Server 2019 or later
#               Visual Studio Build Tools (for llama.cpp)
#               curl.exe (built-in on Windows 10 1803+)

# Don't stop on every error — we handle failures gracefully (mirrors `set +e` in bash)
$ErrorActionPreference = "Continue"

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
Write-Host "  ${BOLD}║  TSUNAMI — Autonomous Execution   ║${RST}"
Write-Host "  ${BOLD}║   Local AI Agent, Zero Cloud      ║${RST}"
Write-Host "  ${BOLD}╚════════════════════════════════════╝${RST}"
Write-Host ""

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
$DIR        = if ($env:TSUNAMI_DIR) { $env:TSUNAMI_DIR } else { Join-Path $env:USERPROFILE "tsunami" }
$MODELS_DIR = Join-Path $DIR "models"
$LLAMA_DIR  = Join-Path $DIR "llama.cpp"

# ---------------------------------------------------------------------------
# GPU detection
# ---------------------------------------------------------------------------
$GPU       = "cpu"
$VRAM      = 0
$CUDA_ARCH = ""

if (Get-Command "nvidia-smi" -ErrorAction SilentlyContinue) {
    $GPU = "cuda"
    try {
        $vramRaw = (& nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null |
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
        $capRaw = (& nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>$null |
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
# Capacity / mode selection (mirrors bash logic exactly)
# ---------------------------------------------------------------------------
$MODE  = "full"
$QUEEN = "9B"

if ($RAM -lt 6) {
    $MODE  = "lite"
    $QUEEN = "2B"
    Write-Host "  → ${RAM}GB RAM: lite mode (2B only)"
} elseif ($RAM -lt 32) {
    $MODE  = "full"
    $QUEEN = "9B"
    Write-Host "  → ${RAM}GB RAM: full mode (9B queen + bees)"
} else {
    $MODE  = "full"
    $QUEEN = "27B"
    Write-Host "  → ${RAM}GB RAM: full mode (27B queen + bees)"
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

Write-Host ""
Write-Host "  Checking dependencies..."

Test-Dep "git"    "winget install Git.Git  OR  https://git-scm.com" | Out-Null

# Accept either python3 or python
$PYTHON = $null
if (Get-Command "python3" -ErrorAction SilentlyContinue) {
    $PYTHON = "python3"
    Write-Ok "python3"
} elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
    $pyVer = (& python --version 2>&1) -replace "Python ", ""
    if ($pyVer -match "^3\.") {
        $PYTHON = "python"
        Write-Ok "python ($pyVer)"
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

if (-not (Test-Dep "cmake" "winget install Kitware.CMake  OR  https://cmake.org/download")) {
    Write-Warn "  cmake is required to build llama.cpp"
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
    Write-Warn "C++ build tools not found in PATH"
    Write-Warn "  llama.cpp requires Visual Studio Build Tools"
    Write-Warn "  Install: winget install Microsoft.VisualStudio.2022.BuildTools"
    Write-Warn "  OR open a 'Developer Command Prompt for VS' and re-run this script"
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
    exit 1
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
        # Last-resort: generate a minimal launcher that delegates to tsunami_cmd
        @'
#!/usr/bin/env pwsh
$DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $DIR
& python "$DIR\tsunami_cmd" @args
'@ | Set-Content $tsuPs1Dest -Encoding UTF8
        Write-Ok "Generated tsu.ps1 launcher"
    }
}

if (-not (Test-Path $DIR)) {
    Write-Fail "Repository clone failed — check your internet connection and try again."
    exit 1
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

# Additional optional dependencies (search, AI/diffusion, etc.)
$pyExtraDeps = @(
    "duckduckgo-search>=7",
    "diffusers",
    "torch",
    "accelerate"
)
$pipResult = & $PIP install -q @pyExtraDeps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Warn "pip install failed, retrying with --user flag..."
    & $PIP install --user -q @pyExtraDeps 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "pip install failed — try manually:"
        Write-Warn "  $PIP install $($pyExtraDeps -join ' ')"
    }
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
# Build llama.cpp
# ---------------------------------------------------------------------------

# On Windows, Release binaries land in one of two locations depending on the
# CMake generator (Ninja vs MSBuild/Visual Studio)
$LLAMA_BIN_MSBUILD = Join-Path $LLAMA_DIR "build\bin\Release\llama-server.exe"
$LLAMA_BIN_NINJA   = Join-Path $LLAMA_DIR "build\bin\llama-server.exe"

function Get-LlamaBin {
    if (Test-Path $LLAMA_BIN_MSBUILD) { return $LLAMA_BIN_MSBUILD }
    if (Test-Path $LLAMA_BIN_NINJA)   { return $LLAMA_BIN_NINJA   }
    return $null
}

$existingBin = Get-LlamaBin
if ($existingBin) {
    Write-Ok "llama.cpp already built ($existingBin)"
} else {
    Write-Step "Building llama.cpp (this takes 2-5 minutes)..."

    if (-not (Test-Path $LLAMA_DIR)) {
        & git clone --depth 1 https://github.com/ggerganov/llama.cpp "$LLAMA_DIR"
    }

    # If a prior cmake configure used a different generator (e.g. VS 2026 was picked
    # before and we now want to force VS 2022), the cached CMakeCache.txt will conflict.
    # Wipe the build dir so cmake starts fresh.
    $cmakeCache = Join-Path $LLAMA_DIR "build\CMakeCache.txt"
    if ((Test-Path $cmakeCache) -and $cmakeCudaGenerator) {
        $cachedGen = (Select-String -Path $cmakeCache -Pattern 'CMAKE_GENERATOR:' |
                      Select-Object -First 1).Line
        if ($cachedGen -and $cachedGen -notmatch [regex]::Escape($cmakeCudaGenerator)) {
            Write-Host "  Clearing stale cmake cache (generator mismatch)..."
            Remove-Item -Recurse -Force (Join-Path $LLAMA_DIR "build")
        }
    }

    # Assemble cmake arguments
    $cmakeArgs = @(
        "$LLAMA_DIR",
        "-B", "$LLAMA_DIR\build",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DBUILD_SHARED_LIBS=OFF"
    )
    # Force a specific VS generator when we know cmake would otherwise pick an
    # incompatible version (e.g. VS 2026+ with CUDA 13.x).
    if ($cmakeCudaGenerator) {
        $cmakeArgs += "-G", $cmakeCudaGenerator
    }
    switch ($GPU) {
        "cuda" {
            $cmakeArgs += "-DGGML_CUDA=ON"
            if ($CUDA_ARCH) {
                $cmakeArgs += "-DCMAKE_CUDA_ARCHITECTURES=$CUDA_ARCH"
            }
            # CMAKE_CUDA_FLAGS is NOT applied during cmake's own CUDA compiler test,
            # so we also set CUDAFLAGS in the environment — nvcc reads that at every stage.
            if ($cudaAllowUnsupported) {
                $env:CUDAFLAGS = "-allow-unsupported-compiler"
                $cmakeArgs    += "-DCMAKE_CUDA_FLAGS=-allow-unsupported-compiler"
            }
        }
        "rocm" { $cmakeArgs += "-DGGML_HIP=ON" }   # unlikely on Windows but included
    }

    Write-Host ""
    Write-Host "  cmake configure..."
    & cmake @cmakeArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "cmake configure failed — check output above"
        if ($cmakeCudaGenerator) {
            Write-Warn "  Tried generator: $cmakeCudaGenerator"
            Write-Warn "  If error persists, open a 'Developer Command Prompt for VS 2022' and retry"
        } elseif ($cudaAllowUnsupported) {
            Write-Warn "  VS 2026+ + CUDA: if still failing, try upgrading CUDA toolkit"
            Write-Warn "  or remove llama.cpp\build and re-run after installing VS 2022"
        } else {
            Write-Warn "  Ensure Visual Studio Build Tools are installed:"
            Write-Warn "  winget install Microsoft.VisualStudio.2022.BuildTools"
            Write-Warn "  Then re-run this script from a Developer Command Prompt"
        }
    } else {
        $cores = (Get-WmiObject -Class Win32_Processor -ErrorAction SilentlyContinue |
                  Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
        if (-not $cores -or $cores -lt 1) { $cores = 4 }

        Write-Host "  cmake build (using $cores cores)..."
        & cmake --build "$LLAMA_DIR\build" --config Release -j $cores --target llama-server

        $builtBin = Get-LlamaBin
        if ($builtBin) {
            Write-Ok "llama.cpp built successfully"
        } else {
            Write-Fail "llama.cpp build FAILED — check cmake output above"
            if ($cmakeCudaGenerator -or $cudaAllowUnsupported) {
                Write-Warn "  Ensure you run from a Developer Command Prompt matching the generator"
            } else {
                Write-Warn "  You may need: winget install Microsoft.VisualStudio.2022.BuildTools"
            }
            Write-Warn "  Ensure you run this script from a Developer Command Prompt for VS"
            # Non-fatal — continue so models are still downloaded
        }
    }
}

# ---------------------------------------------------------------------------
# Download models
# ---------------------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $MODELS_DIR | Out-Null

# Confirm curl is available (built-in on Windows 10 1803+)
if (-not (Get-Command "curl.exe" -ErrorAction SilentlyContinue)) {
    Write-Fail "curl.exe not found — cannot download models automatically"
    Write-Warn "  Please download models manually from https://huggingface.co/unsloth"
    Write-Warn "  and place them in: $MODELS_DIR"
} else {

    function Get-Model {
        param(
            [string]$Repo,
            [string]$File
        )
        $dest = Join-Path $MODELS_DIR $File
        if (Test-Path $dest) {
            $sizeMB = [math]::Round((Get-Item $dest).Length / 1MB, 0)
            Write-Ok "$File (${sizeMB}MB)"
            return
        }
        Write-Step "Downloading $File..."
        $url = "https://huggingface.co/$Repo/resolve/main/$File"
        # Use curl with progress bar; --location follows redirects (HuggingFace uses them)
        & curl.exe -fSL --progress-bar -o "$dest" "$url"
        if ((Test-Path $dest) -and (Get-Item $dest).Length -gt 1000) {
            $sizeMB = [math]::Round((Get-Item $dest).Length / 1MB, 0)
            Write-Ok "$File (${sizeMB}MB)"
        } else {
            Write-Fail "Download failed: $File"
            if (Test-Path $dest) { Remove-Item $dest -Force }
        }
    }

    Write-Host ""

    # --- Always download 2B bee model ---
    Write-Host "  Downloading bee model (1.2GB)..."
    Get-Model "unsloth/Qwen3.5-2B-GGUF" "Qwen3.5-2B-Q4_K_M.gguf"
    Get-Model "unsloth/Qwen3.5-2B-GGUF" "mmproj-BF16.gguf"
    $mmproj = Join-Path $MODELS_DIR "mmproj-BF16.gguf"
    $mmproj2B = Join-Path $MODELS_DIR "mmproj-2B-BF16.gguf"
    if ((Test-Path $mmproj) -and -not (Test-Path $mmproj2B)) {
        Move-Item $mmproj $mmproj2B
    }

    # --- Queen model based on available RAM ---
    if ($QUEEN -eq "9B") {
        Write-Host "  Downloading queen model (5.3GB)..."
        Get-Model "unsloth/Qwen3.5-9B-GGUF" "Qwen3.5-9B-Q4_K_M.gguf"
        Get-Model "unsloth/Qwen3.5-9B-GGUF" "mmproj-BF16.gguf"
        $mmproj9B = Join-Path $MODELS_DIR "mmproj-9B-BF16.gguf"
        if ((Test-Path $mmproj) -and -not (Test-Path $mmproj9B)) {
            Move-Item $mmproj $mmproj9B
        }
    } elseif ($QUEEN -eq "27B") {
        Write-Host "  Downloading queen model (27GB)..."
        Get-Model "unsloth/Qwen3.5-27B-GGUF" "Qwen3.5-27B-Q8_0.gguf"
        Get-Model "unsloth/Qwen3.5-27B-GGUF" "mmproj-BF16.gguf"
        $mmproj27B = Join-Path $MODELS_DIR "mmproj-27B-BF16.gguf"
        if ((Test-Path $mmproj) -and -not (Test-Path $mmproj27B)) {
            Move-Item $mmproj $mmproj27B
        }
    }

    # --- Optional: image model if enough RAM ---
    if ((Get-Command "docker" -ErrorAction SilentlyContinue) -and $RAM -ge 48) {
        Write-Host ""
        Write-Step "Docker detected with ${RAM}GB RAM — downloading image model..."
        Get-Model "unsloth/Qwen-Image-2512-GGUF" "qwen-image-2512-Q4_K_M.gguf"
    }

    Write-Host ""
    Write-Ok "Models installed: $QUEEN queen + 2B bees"
    Write-Host "  Tsunami auto-detects and scales on startup."
}

# ---------------------------------------------------------------------------
# Create global command
# ---------------------------------------------------------------------------
Write-Host ""

# 1. Add llama.cpp build/bin to the user PATH (persistent)
$llamaBinDir = Join-Path $LLAMA_DIR "build\bin"
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$llamaBinDir*") {
    [Environment]::SetEnvironmentVariable(
        "PATH",
        "$userPath;$llamaBinDir",
        "User"
    )
    Write-Ok "Added llama.cpp binaries to user PATH"
}

# 2. Add $DIR to user PATH so `tsu` is accessible from anywhere
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
    $newContent = $cleaned + "`n`n# Tsunami AI Agent`n$psAlias`n`$env:PATH += `";$llamaBinDir`"`n"
    [System.IO.File]::WriteAllText($profilePath, $newContent)
    Write-Ok "Updated 'tsunami' entry in PowerShell profile"
} else {
    Add-Content -Path $profilePath -Value ""
    Add-Content -Path $profilePath -Value "# Tsunami AI Agent"
    Add-Content -Path $profilePath -Value $psAlias
    Add-Content -Path $profilePath -Value "`$env:PATH += `";$llamaBinDir`""
    Write-Ok "Added 'tsunami' to PowerShell profile ($profilePath)"
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
# List downloaded model files
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  Models:"
if (Test-Path $MODELS_DIR) {
    Get-ChildItem -Path $MODELS_DIR -Filter "*.gguf" -File | ForEach-Object {
        $sizeMB = [math]::Round($_.Length / 1MB, 0)
        Write-Ok "$($_.Name) (${sizeMB}MB)"
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
Write-Host "  ${BOLD}║  GPU: $GPU  |  RAM: ${RAM}GB  |  Queen: $QUEEN${RST}"
Write-Host "  ${BOLD}║                                            ║${RST}"
Write-Host "  ${BOLD}╚════════════════════════════════════════════╝${RST}"
Write-Host ""
Write-Host "  ${YLW}NOTE: Restart PowerShell (or run '. `$PROFILE') to use the 'tsunami' command.${RST}"
Write-Host ""
