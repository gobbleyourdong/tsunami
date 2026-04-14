#!/bin/bash
# TSUNAMI — One-Click Installer (Mac + Linux)
# curl -sSL https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/setup.sh | bash
set +e

echo "
  ╔════════════════════════════════════╗
  ║  tsunami — the tide rises          ║
  ║   Local AI Agent, Zero Cloud      ║
  ╚════════════════════════════════════╝
"

DIR="${TSUNAMI_DIR:-$HOME/tsunami}"
MODELS_DIR="$DIR/models"

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
    CAPACITY=$(( (VRAM + 1023) / 1024 ))
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

# Model serving + image generation
echo "  → Installing model server dependencies..."
_pip_install transformers accelerate torch || \
  echo "  ⚠ transformers/torch install failed — model server won't work"

# Image-gen Python backend is only used as a fallback — the production path
# is sd-server (stable-diffusion.cpp GGUF) installed below. diffusers still
# needed for the scaffolds/engine sprite pipeline which runs client-side.
_pip_install diffusers || \
  echo "  ⚠ diffusers skipped — fallback image gen won't work"

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

# ---------------------------------------------------------------------------
# Download pre-built llama-server + sd-server binaries.
# These are the production inference paths (GGUF, native CUDA kernels).
# Mac = arm64 Metal build; Linux CUDA = Ubuntu CUDA build; Windows has
# its own path in setup.ps1.
# ---------------------------------------------------------------------------
LLAMA_RELEASE="b8794"
SD_RELEASE="master-fd35047"
BIN_DIR="$DIR/bin"
mkdir -p "$BIN_DIR"

download_llama() {
  if [ -x "$BIN_DIR/llama-server" ]; then
    echo "  ✓ llama-server already installed"
    return
  fi
  local url=""
  if [ "$OS" = "Darwin" ] && [ "$ARCH" = "arm64" ]; then
    url="https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_RELEASE/llama-$LLAMA_RELEASE-bin-macos-arm64.tar.gz"
  elif [ "$OS" = "Linux" ] && [ "$GPU" = "cuda" ]; then
    # No official Linux CUDA pre-built; user needs to cmake build OR we ship
    # our own prebuilt. For now, instruct to build from source.
    echo "  ⚠ No pre-built Linux CUDA llama-server in upstream releases."
    echo "    Install from ggml-org/llama.cpp: cmake -DGGML_CUDA=ON && make -j"
    return
  else
    echo "  ⚠ Platform not covered — skip llama-server install"
    return
  fi
  echo "  → Downloading llama-server ($LLAMA_RELEASE, $OS/$ARCH)..."
  local tmp=$(mktemp -d)
  curl -fSL "$url" -o "$tmp/llama.tgz" && tar -xzf "$tmp/llama.tgz" -C "$tmp"
  find "$tmp" -name "llama-server" -type f -exec mv {} "$BIN_DIR/" \;
  chmod +x "$BIN_DIR/llama-server" 2>/dev/null
  rm -rf "$tmp"
  [ -x "$BIN_DIR/llama-server" ] && echo "  ✓ llama-server installed" || echo "  ✗ llama-server install failed"
}

download_sd() {
  if [ -x "$BIN_DIR/sd-server" ]; then
    echo "  ✓ sd-server already installed"
    return
  fi
  local url=""
  if [ "$OS" = "Darwin" ] && [ "$ARCH" = "arm64" ]; then
    url="https://github.com/leejet/stable-diffusion.cpp/releases/download/$SD_RELEASE/sd-$SD_RELEASE-bin-Darwin-macOS-15.7.4-arm64.zip"
  elif [ "$OS" = "Linux" ]; then
    echo "  ⚠ No pre-built Linux sd-server in upstream releases."
    echo "    Install from leejet/stable-diffusion.cpp: cmake -DSD_CUDA=ON && make -j"
    return
  else
    return
  fi
  echo "  → Downloading sd-server ($SD_RELEASE, $OS/$ARCH)..."
  local tmp=$(mktemp -d)
  curl -fSL "$url" -o "$tmp/sd.zip" && unzip -q "$tmp/sd.zip" -d "$tmp"
  find "$tmp" -name "sd-server" -type f -exec mv {} "$BIN_DIR/" \;
  chmod +x "$BIN_DIR/sd-server" 2>/dev/null
  rm -rf "$tmp"
  [ -x "$BIN_DIR/sd-server" ] && echo "  ✓ sd-server installed" || echo "  ✗ sd-server install failed"
}

download_llama
download_sd

# --- GGUF model weights (31B MoE for LM, Z-Image-Turbo Q4_K for images) ---
echo ""
mkdir -p "$MODELS_DIR"

fetch_model() {
  local repo="$1" file="$2" dest="$MODELS_DIR/$2"
  if [ -f "$dest" ]; then
    local sz=$(stat -c%s "$dest" 2>/dev/null || stat -f%z "$dest" 2>/dev/null)
    echo "  ✓ $file ($(( sz / 1024 / 1024 ))MB, cached)"
    return
  fi
  echo "  → Downloading $file..."
  curl -fSL --progress-bar "https://huggingface.co/$repo/resolve/main/$file" -o "$dest"
}

# Gemma-4-26B-A4B MoE MXFP4 — 15.5GB, native Blackwell fp4 tensor cores
fetch_model "unsloth/gemma-4-26B-A4B-it-GGUF" "gemma-4-26B-A4B-it-MXFP4_MOE.gguf"
fetch_model "unsloth/gemma-4-26B-A4B-it-GGUF" "mmproj-F16.gguf"
# Z-Image-Turbo Q4_K for sd-server
fetch_model "leejet/Z-Image-Turbo-GGUF" "z_image_turbo-Q4_K.gguf"
# Z-Image VAE
fetch_model "Comfy-Org/z_image_turbo" "split_files/vae/ae.safetensors"
mv "$MODELS_DIR/split_files/vae/ae.safetensors" "$MODELS_DIR/ae.safetensors" 2>/dev/null || true
rm -rf "$MODELS_DIR/split_files"
# Qwen3-4B text encoder for sd-server
fetch_model "unsloth/Qwen3-4B-GGUF" "Qwen3-4B-Q4_K_M.gguf"

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
echo "  ║  $GPU_LABEL | ${CAPACITY}GB | transformers    ║"
echo "  ╚════════════════════════════════════════╝"
echo ""
