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

# SD-Turbo image generation (optional — 2GB model auto-downloads on first use)
echo "  → Installing image generation (SD-Turbo)..."
_pip_install diffusers || \
  echo "  ⚠ diffusers skipped — image gen won't work"

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

# --- Model weights ---
echo ""
mkdir -p "$MODELS_DIR"
echo "  Place merged HuggingFace model weights in: $MODELS_DIR/<model-name>/"
echo "  The model directory should contain config.json + model files."

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
