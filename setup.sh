#!/bin/bash
# TSUNAMI — One-Click Installer
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

# RAM detection (works on both Linux and Mac)
if [ "$OS" = "Darwin" ]; then
  RAM=$(sysctl -n hw.memsize 2>/dev/null | awk '{print int($1/1073741824)}')
else
  RAM=$(free -g 2>/dev/null | awk '/^Mem:/{print $2}')
fi
RAM=${RAM:-8}  # default to 8GB if detection fails

# GPU detection
if command -v nvidia-smi &>/dev/null; then
  GPU="cuda"
  VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
  if [ "$VRAM" = "[N/A]" ] || [ -z "$VRAM" ]; then
    echo "  ✓ NVIDIA GPU — unified memory (${RAM}GB shared)"
  else
    echo "  ✓ NVIDIA GPU — ${VRAM}MB VRAM"
  fi
elif [ -d "/opt/rocm" ]; then
  GPU="rocm"
  echo "  ✓ AMD ROCm detected"
elif [ "$OS" = "Darwin" ] && [ "$ARCH" = "arm64" ]; then
  GPU="metal"
  echo "  ✓ Apple Silicon — ${RAM}GB unified memory"
else
  GPU="cpu"
  echo "  ⚠ No GPU detected — will run on CPU (very slow)"
fi

echo "  RAM: ${RAM}GB"

# --- Auto-scale ---
if [ "$RAM" -lt 8 ] 2>/dev/null; then
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
      echo "  ✗ $1 missing — brew install $1"
    else
      echo "  ✗ $1 missing — apt install $2"
    fi
  else
    echo "  ✓ $1"
  fi
}

check_dep git "git"
check_dep python3 "python3"
check_dep pip3 "python3-pip"
check_dep cmake "cmake"

# Mac: check for Xcode CLI tools
if [ "$OS" = "Darwin" ] && ! xcode-select -p &>/dev/null; then
  echo "  → Installing Xcode Command Line Tools..."
  xcode-select --install 2>/dev/null
  echo "  ⚠ Xcode CLI tools required — run the installer that popped up, then re-run this script"
  exit 1
fi

# Install Node if missing
if ! command -v node &>/dev/null; then
  echo "  → Installing Node.js..."
  if [ "$OS" = "Darwin" ]; then
    if command -v brew &>/dev/null; then
      brew install node 2>/dev/null
    else
      echo "  ⚠ Install Homebrew first: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
      echo "    Then re-run this script."
    fi
  else
    curl -fsSL https://fnm.vercel.app/install | bash 2>/dev/null
    export PATH="$HOME/.local/share/fnm:$PATH"
    eval "$(fnm env)" 2>/dev/null
    fnm install --lts 2>/dev/null
  fi
  if command -v node &>/dev/null; then
    echo "  ✓ Node.js $(node -v)"
  else
    echo "  ⚠ Node.js not installed — CLI won't work but agent runs via Python"
  fi
else
  echo "  ✓ node $(node -v)"
fi

if [ -n "$MISSING" ]; then
  echo ""
  echo "  ✗ Missing:$MISSING"
  if [ "$OS" = "Darwin" ]; then
    echo "    Install with: brew install$MISSING"
  else
    echo "    Install with: sudo apt install$MISSING"
  fi
  exit 1
fi

# --- Clone repo ---
echo ""
if [ -d "$DIR/.git" ]; then
  echo "  → Updating..."
  cd "$DIR" && git pull --ff-only 2>/dev/null || true
else
  echo "  → Cloning tsunami..."
  git clone https://github.com/gobbleyourdong/tsunami.git "$DIR"
fi
cd "$DIR"

# --- Python deps ---
echo "  → Installing Python dependencies..."
DEPS="httpx pyyaml ddgs pillow"
pip3 install -q $DEPS 2>/dev/null || \
pip3 install --break-system-packages -q $DEPS 2>/dev/null || \
pip3 install --user -q $DEPS 2>/dev/null || \
echo "  ⚠ pip install failed — try: pip3 install $DEPS"

# SD-Turbo image generation (~2GB model, auto-downloads on first use)
echo "  → Installing image generation (SD-Turbo)..."
pip3 install -q diffusers torch transformers accelerate 2>/dev/null || \
pip3 install --break-system-packages -q diffusers torch transformers accelerate 2>/dev/null || \
pip3 install --user -q diffusers torch transformers accelerate 2>/dev/null || \
echo "  ⚠ diffusers install failed — image gen won't work (pip3 install diffusers torch)"

# Optional: playwright for undertow QA
pip3 install -q playwright 2>/dev/null && python3 -m playwright install chromium 2>/dev/null && \
echo "  ✓ Playwright (undertow QA)" || echo "  ⚠ Playwright skipped — undertow QA won't work"

# --- Node deps ---
if command -v node &>/dev/null && [ -d "$DIR/cli" ]; then
  echo "  → Installing CLI..."
  cd "$DIR/cli" && npm install --silent 2>/dev/null && cd "$DIR"
fi

# --- Build llama.cpp ---
LLAMA_DIR="$DIR/llama.cpp"
LLAMA_BIN="$LLAMA_DIR/build/bin/llama-server"

if [ ! -f "$LLAMA_BIN" ]; then
  echo "  → Building llama.cpp (2-5 minutes)..."
  if [ ! -d "$LLAMA_DIR" ]; then
    git clone --depth 1 https://github.com/ggerganov/llama.cpp "$LLAMA_DIR"
  fi

  CMAKE_ARGS="-DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF"
  case "$GPU" in
    cuda)  CMAKE_ARGS="$CMAKE_ARGS -DGGML_CUDA=ON" ;;
    rocm)  CMAKE_ARGS="$CMAKE_ARGS -DGGML_HIP=ON" ;;
    metal) CMAKE_ARGS="$CMAKE_ARGS -DGGML_METAL=ON" ;;
  esac

  cmake "$LLAMA_DIR" -B "$LLAMA_DIR/build" $CMAKE_ARGS
  CORES=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
  cmake --build "$LLAMA_DIR/build" --config Release -j"$CORES" --target llama-server

  if [ -f "$LLAMA_BIN" ]; then
    echo "  ✓ llama.cpp built"
  else
    echo "  ✗ llama.cpp build FAILED"
    if [ "$OS" = "Darwin" ]; then
      echo "    Try: xcode-select --install"
    else
      echo "    Try: sudo apt install build-essential cmake"
    fi
    exit 1
  fi
else
  echo "  ✓ llama.cpp already built"
fi

# --- Download models ---
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

echo ""

# 2B eddy model (always needed)
echo "  Downloading eddy model (1.2GB)..."
download "unsloth/Qwen3.5-2B-GGUF" "Qwen3.5-2B-Q4_K_M.gguf"

# 9B wave model
if [ "$WAVE" = "9B" ]; then
  echo "  Downloading wave model (5.3GB)..."
  download "unsloth/Qwen3.5-9B-GGUF" "Qwen3.5-9B-Q4_K_M.gguf"
fi

echo ""
echo "  Models: $WAVE wave + 2B eddies"

# --- Shell alias ---
echo ""
chmod +x "$DIR/tsu" 2>/dev/null

# Prefer zsh on Mac, bash on Linux
SHELL_RC=""
if [ "$OS" = "Darwin" ]; then
  SHELL_RC="$HOME/.zshrc"
  touch "$SHELL_RC"  # zshrc might not exist yet
else
  [ -f "$HOME/.bashrc" ] && SHELL_RC="$HOME/.bashrc"
  [ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"
fi

if [ -n "$SHELL_RC" ] && ! grep -q "tsunami" "$SHELL_RC" 2>/dev/null; then
  echo "" >> "$SHELL_RC"
  echo "# Tsunami AI Agent" >> "$SHELL_RC"
  echo "alias tsunami='$DIR/tsu'" >> "$SHELL_RC"
  echo "export PATH=\"$LLAMA_DIR/build/bin:\$PATH\"" >> "$SHELL_RC"
  echo "  ✓ Added 'tsunami' to $(basename $SHELL_RC)"
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

echo ""
echo "  ╔════════════════════════════════════════╗"
echo "  ║        TSUNAMI INSTALLED               ║"
echo "  ╠════════════════════════════════════════╣"
echo "  ║                                        ║"
echo "  ║  source ~/${SHELL_RC##*/}                       ║"
echo "  ║  tsunami                               ║"
echo "  ║                                        ║"
echo "  ║  $GPU | ${RAM}GB | $WAVE wave          ║"
echo "  ╚════════════════════════════════════════╝"
echo ""
