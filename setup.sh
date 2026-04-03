#!/bin/bash
# TSUNAMI — One-Click Installer (Mac + Linux)
# curl -sSL https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/setup.sh | bash
set +e

echo "
  ╔════════════════════════════════════╗
  ║  TSUNAMI — Autonomous Execution   ║
  ║   Local AI Agent, Zero Cloud      ║
  ╚════════════════════════════════════╝
"

DIR="${TSUNAMI_DIR:-$HOME/tsunami}"
MODELS_DIR="$DIR/models"
LLAMA_DIR="$DIR/llama-server"
LLAMA_RELEASE="b8628"

# --- Detect platform ---
OS=$(uname -s)
ARCH=$(uname -m)
GPU=""
VRAM=0

if [ "$OS" = "Darwin" ]; then
  RAM=$(sysctl -n hw.memsize 2>/dev/null | awk '{print int($1/1073741824)}')
else
  RAM=$(free -g 2>/dev/null | awk '/^Mem:/{print $2}')
fi
RAM=${RAM:-8}

# GPU detection
if command -v nvidia-smi &>/dev/null; then
  GPU="cuda"
  VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
  if [ "$VRAM" = "[N/A]" ] || [ -z "$VRAM" ]; then
    echo "  ✓ NVIDIA GPU — unified memory (${RAM}GB shared)"
    CAPACITY=$RAM
  else
    echo "  ✓ NVIDIA GPU — ${VRAM}MB VRAM"
    CAPACITY=$(( (VRAM + 1023) / 1024 ))  # round up
  fi
elif [ -d "/opt/rocm" ]; then
  GPU="rocm"
  CAPACITY=$RAM
  echo "  ✓ AMD ROCm detected"
elif [ "$OS" = "Darwin" ] && [ "$ARCH" = "arm64" ]; then
  GPU="metal"
  CAPACITY=$RAM
  echo "  ✓ Apple Silicon — ${RAM}GB unified memory"
else
  GPU="cpu"
  CAPACITY=$RAM
  echo "  ⚠ No GPU detected — will run on CPU (slow)"
fi

echo "  Memory: ${CAPACITY}GB"

# --- Auto-scale (8GB threshold matches Windows) ---
if [ "$CAPACITY" -lt 10 ] 2>/dev/null; then
  MODE="lite"
  WAVE="2B"
  echo "  → lite mode (2B only)"
else
  MODE="full"
  WAVE="9B"
  echo "  → full mode (9B wave + 2B eddies)"
fi

# --- Check dependencies ---
echo ""
echo "  Checking dependencies..."
MISSING=""
check_dep() {
  if ! command -v "$1" &>/dev/null; then
    MISSING="$MISSING $1"
    if [ "$OS" = "Darwin" ]; then
      echo "  ✗ $1 missing — brew install $2"
    else
      echo "  ✗ $1 missing — sudo apt install $2"
    fi
  else
    echo "  ✓ $1"
  fi
}

check_dep git "git"
check_dep python3 "python3"
check_dep curl "curl"

# pip3 might not be separate on some systems
if ! command -v pip3 &>/dev/null; then
  if python3 -m pip --version &>/dev/null; then
    echo "  ✓ pip (via python3 -m pip)"
    PIP="python3 -m pip"
  else
    MISSING="$MISSING pip3"
    echo "  ✗ pip3 missing — sudo apt install python3-pip"
  fi
else
  echo "  ✓ pip3"
  PIP="pip3"
fi

# Mac: check for Xcode CLI tools
if [ "$OS" = "Darwin" ] && ! xcode-select -p &>/dev/null; then
  echo "  → Installing Xcode Command Line Tools..."
  xcode-select --install 2>/dev/null
  echo "  ⚠ Xcode CLI tools installing — re-run this script after it finishes"
  return 2>/dev/null || exit 1
fi

# Node.js (optional — agent works without it)
if ! command -v node &>/dev/null; then
  echo "  ⚠ Node.js not found — optional, agent runs via Python"
  echo "    Install: brew install node (Mac) or sudo apt install nodejs npm (Linux)"
else
  echo "  ✓ node $(node -v)"
fi

if [ -n "$MISSING" ]; then
  echo ""
  echo "  ✗ Missing:$MISSING"
  if [ "$OS" = "Darwin" ]; then
    echo "    brew install$MISSING"
  else
    echo "    sudo apt install$MISSING"
  fi
  return 2>/dev/null || exit 1
fi

# --- Clone repo ---
echo ""
if [ -d "$DIR/.git" ]; then
  echo "  → Updating..."
  cd "$DIR" && git pull --ff-only 2>/dev/null || true
elif [ -d "$DIR/tsunami" ]; then
  # Installed by installer — init git for auto-updates
  echo "  → Initializing git for auto-updates..."
  cd "$DIR"
  git init -b main 2>/dev/null
  git remote add origin "https://github.com/gobbleyourdong/tsunami.git" 2>/dev/null
  git fetch origin main --quiet 2>/dev/null
  git reset --hard origin/main 2>/dev/null
  git branch --set-upstream-to=origin/main main 2>/dev/null
else
  echo "  → Cloning tsunami..."
  git clone https://github.com/gobbleyourdong/tsunami.git "$DIR"
fi
cd "$DIR"

# --- Python deps ---
echo "  → Installing Python dependencies..."
_pip_install() {
  $PIP install -q "$@" 2>/dev/null || \
  $PIP install --break-system-packages -q "$@" 2>/dev/null || \
  $PIP install --user -q "$@" 2>/dev/null
}

# Core (required)
_pip_install httpx pyyaml ddgs pillow websockets fastapi uvicorn rich psutil || \
  echo "  ⚠ pip install failed — try: $PIP install httpx pyyaml ddgs pillow websockets fastapi uvicorn"

# SD-Turbo image generation (optional — 2GB model auto-downloads on first use)
echo "  → Installing image generation (SD-Turbo)..."
_pip_install diffusers transformers accelerate || \
  echo "  ⚠ diffusers skipped — image gen won't work ($PIP install diffusers torch)"

# torch — only if not already installed (it's huge, ~2GB)
python3 -c "import torch" 2>/dev/null || {
  echo "  → Installing PyTorch (this may take a while)..."
  if [ "$GPU" = "cuda" ]; then
    _pip_install torch --index-url https://download.pytorch.org/whl/cu121 || \
    _pip_install torch
  else
    _pip_install torch --index-url https://download.pytorch.org/whl/cpu || \
    _pip_install torch
  fi
}

# Playwright (optional — for undertow QA)
_pip_install playwright 2>/dev/null && \
  python3 -m playwright install chromium 2>/dev/null && \
  echo "  ✓ Playwright (undertow QA)" || \
  echo "  ⚠ Playwright skipped — undertow QA won't work"

# --- Node CLI (optional) ---
if command -v node &>/dev/null && [ -d "$DIR/cli" ]; then
  echo "  → Installing CLI frontend..."
  cd "$DIR/cli" && npm install --silent 2>/dev/null && cd "$DIR"
fi

# --- llama-server (pre-built binary first, source build fallback) ---
echo ""
LLAMA_BIN="$LLAMA_DIR/llama-server"
[ "$OS" = "Darwin" ] || LLAMA_BIN="$LLAMA_DIR/llama-server"

# Also check legacy build path
LLAMA_BIN_BUILT="$DIR/llama.cpp/build/bin/llama-server"

if [ -f "$LLAMA_BIN" ] || [ -f "$LLAMA_BIN_BUILT" ]; then
  echo "  ✓ llama-server already installed"
else
  mkdir -p "$LLAMA_DIR"

  # Try pre-built binary first (fast, no cmake needed)
  DOWNLOAD_URL=""
  if [ "$OS" = "Darwin" ] && [ "$ARCH" = "arm64" ]; then
    DOWNLOAD_URL="https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_RELEASE/llama-$LLAMA_RELEASE-bin-macos-arm64.zip"
  elif [ "$OS" = "Darwin" ] && [ "$ARCH" = "x86_64" ]; then
    DOWNLOAD_URL="https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_RELEASE/llama-$LLAMA_RELEASE-bin-macos-x64.zip"
  elif [ "$OS" = "Linux" ] && [ "$ARCH" = "x86_64" ]; then
    if [ "$GPU" = "cuda" ]; then
      DOWNLOAD_URL="https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_RELEASE/llama-$LLAMA_RELEASE-bin-ubuntu-x64-cuda-12.4.zip"
    else
      DOWNLOAD_URL="https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_RELEASE/llama-$LLAMA_RELEASE-bin-ubuntu-x64.zip"
    fi
  elif [ "$OS" = "Linux" ] && [ "$ARCH" = "aarch64" ]; then
    # ARM Linux (RPi, Jetson, DGX Spark) — build from source
    DOWNLOAD_URL=""
  fi

  if [ -n "$DOWNLOAD_URL" ]; then
    echo "  → Downloading llama-server (pre-built)..."
    TMPZIP="/tmp/llama-server-$$.zip"
    curl -fSL --progress-bar -o "$TMPZIP" "$DOWNLOAD_URL"
    if [ -f "$TMPZIP" ] && [ "$(stat -c%s "$TMPZIP" 2>/dev/null || stat -f%z "$TMPZIP" 2>/dev/null)" -gt 10000 ]; then
      unzip -q -o "$TMPZIP" -d "$LLAMA_DIR" 2>/dev/null
      rm -f "$TMPZIP"
      # Find and move llama-server to root
      FOUND=$(find "$LLAMA_DIR" -name "llama-server" -type f | head -1)
      if [ -n "$FOUND" ] && [ "$FOUND" != "$LLAMA_BIN" ]; then
        mv "$FOUND" "$LLAMA_BIN" 2>/dev/null
      fi
      chmod +x "$LLAMA_BIN" 2>/dev/null
      echo "  ✓ llama-server (pre-built)"
    else
      echo "  ⚠ Pre-built download failed — building from source..."
      rm -f "$TMPZIP"
      DOWNLOAD_URL=""
    fi
  fi

  # Fallback: build from source
  if [ ! -f "$LLAMA_BIN" ]; then
    if ! command -v cmake &>/dev/null; then
      echo "  ✗ cmake needed to build llama.cpp from source"
      echo "    Install: brew install cmake (Mac) or sudo apt install cmake (Linux)"
      echo "    Or download a pre-built binary from https://github.com/ggml-org/llama.cpp/releases"
    else
      echo "  → Building llama.cpp from source (2-5 minutes)..."
      SRC_DIR="$DIR/llama.cpp"
      [ -d "$SRC_DIR" ] || git clone --depth 1 https://github.com/ggml-org/llama.cpp "$SRC_DIR"

      CMAKE_ARGS="-DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF"
      case "$GPU" in
        cuda)  CMAKE_ARGS="$CMAKE_ARGS -DGGML_CUDA=ON" ;;
        rocm)  CMAKE_ARGS="$CMAKE_ARGS -DGGML_HIP=ON" ;;
        metal) CMAKE_ARGS="$CMAKE_ARGS -DGGML_METAL=ON" ;;
      esac

      cmake "$SRC_DIR" -B "$SRC_DIR/build" $CMAKE_ARGS
      CORES=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
      cmake --build "$SRC_DIR/build" --config Release -j"$CORES" --target llama-server

      if [ -f "$SRC_DIR/build/bin/llama-server" ]; then
        cp "$SRC_DIR/build/bin/llama-server" "$LLAMA_BIN"
        chmod +x "$LLAMA_BIN"
        echo "  ✓ llama-server (built from source)"
      else
        echo "  ✗ Build failed"
      fi
    fi
  fi
fi

# --- Download models ---
echo ""
mkdir -p "$MODELS_DIR"

download() {
  local repo="$1" file="$2"
  local dest="$MODELS_DIR/$file"
  [ -f "$dest" ] && echo "  ✓ $file ($(du -h "$dest" | cut -f1))" && return
  echo "  → Downloading $file..."
  curl -fSL --progress-bar -o "$dest" "https://huggingface.co/$repo/resolve/main/$file"
  if [ -f "$dest" ] && [ "$(stat -c%s "$dest" 2>/dev/null || stat -f%z "$dest" 2>/dev/null)" -gt 1000 ]; then
    echo "  ✓ $file ($(du -h "$dest" | cut -f1))"
  else
    echo "  ✗ Download failed: $file"
    rm -f "$dest"
  fi
}

# 2B eddy (always)
download "unsloth/Qwen3.5-2B-GGUF" "Qwen3.5-2B-Q4_K_M.gguf"

# 9B wave (full mode only)
if [ "$WAVE" = "9B" ]; then
  download "unsloth/Qwen3.5-9B-GGUF" "Qwen3.5-9B-Q4_K_M.gguf"
fi

echo ""
echo "  Models: $WAVE wave + 2B eddies"

# --- Shell alias ---
echo ""
chmod +x "$DIR/tsu" 2>/dev/null

SHELL_RC=""
if [ "$OS" = "Darwin" ]; then
  SHELL_RC="$HOME/.zshrc"
  touch "$SHELL_RC"
else
  [ -f "$HOME/.bashrc" ] && SHELL_RC="$HOME/.bashrc"
  [ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"
fi

if [ -n "$SHELL_RC" ] && ! grep -q "tsunami" "$SHELL_RC" 2>/dev/null; then
  echo "" >> "$SHELL_RC"
  echo "# Tsunami AI Agent" >> "$SHELL_RC"
  echo "alias tsunami='$DIR/tsu'" >> "$SHELL_RC"
  echo "export PATH=\"$LLAMA_DIR:\$PATH\"" >> "$SHELL_RC"
  echo "  ✓ Added 'tsunami' to $(basename "$SHELL_RC")"
fi

# --- Verify ---
echo ""
echo "  Verifying..."
cd "$DIR"
python3 -c "
from tsunami.config import TsunamiConfig
from tsunami.tools import build_registry
config = TsunamiConfig.from_yaml('config.yaml')
registry = build_registry(config)
print(f'  ✓ Agent: {len(registry.schemas())} tools ready')
" 2>/dev/null || echo "  ⚠ Verification failed — check Python deps"

# --- Done ---
GPU_LABEL="$GPU"
[ "$GPU" = "metal" ] && GPU_LABEL="Apple Silicon"
[ "$GPU" = "cpu" ] && GPU_LABEL="CPU only"

echo ""
echo "  ╔════════════════════════════════════════╗"
echo "  ║        TSUNAMI INSTALLED               ║"
echo "  ╠════════════════════════════════════════╣"
echo "  ║                                        ║"
echo "  ║  source ~/${SHELL_RC##*/}              ║"
echo "  ║  tsunami                               ║"
echo "  ║                                        ║"
echo "  ║  $GPU_LABEL | ${CAPACITY}GB | $WAVE wave          ║"
echo "  ╚════════════════════════════════════════╝"
echo ""
