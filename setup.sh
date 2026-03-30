#!/bin/bash
# TSUNAMI — One-Click Installer
# curl -sSL https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/setup.sh | bash
# Don't exit on error — we handle failures gracefully
set +e

echo "
  ╔════════════════════════════════════╗
  ║     TSUNAMI — Agentic Reborn      ║
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
RAM=$(free -g 2>/dev/null | awk '/^Mem:/{print $2}' || sysctl -n hw.memsize 2>/dev/null | awk '{print int($1/1073741824)}')

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

# --- Capacity check ---
MODEL_SIZE="27B"
if [ "$RAM" -lt 16 ] 2>/dev/null; then
  echo ""
  echo "  ⚠ WARNING: ${RAM}GB RAM is below minimum (16GB)"
  echo "    Tsunami needs at least 16GB for the 2B model"
  echo "    Recommended: 32GB+ for the 27B model"
  MODEL_SIZE="2B"
elif [ "$RAM" -lt 32 ] 2>/dev/null; then
  echo "  → ${RAM}GB RAM: will use Q4 quantization (smaller, faster)"
  MODEL_SIZE="27B-Q4"
elif [ "$RAM" -lt 64 ] 2>/dev/null; then
  echo "  → ${RAM}GB RAM: will use Q4 quantization"
  MODEL_SIZE="27B-Q4"
else
  echo "  → ${RAM}GB RAM: will use Q8 quantization (best quality)"
  MODEL_SIZE="27B-Q8"
fi

# --- Check dependencies ---
MISSING=""
check_dep() {
  if ! command -v "$1" &>/dev/null; then
    MISSING="$MISSING $1"
    echo "  ✗ $1 missing — $2"
  else
    echo "  ✓ $1"
  fi
}

echo ""
echo "  Checking dependencies..."
check_dep git "apt install git / brew install git"
check_dep python3 "apt install python3 / brew install python3"
check_dep cmake "apt install cmake / brew install cmake"

# Install Node if missing (for Ink CLI)
if ! command -v node &>/dev/null; then
  echo "  → Installing Node.js..."
  if [ "$OS" = "Darwin" ]; then
    # macOS
    if command -v brew &>/dev/null; then
      brew install node 2>/dev/null
    else
      curl -fsSL https://fnm.vercel.app/install | bash 2>/dev/null
      export PATH="$HOME/.local/share/fnm:$PATH"
      eval "$(fnm env)" 2>/dev/null
      fnm install --lts 2>/dev/null
    fi
  else
    # Linux — use fnm (fast node manager)
    curl -fsSL https://fnm.vercel.app/install | bash 2>/dev/null
    export PATH="$HOME/.local/share/fnm:$PATH"
    eval "$(fnm env)" 2>/dev/null
    fnm install --lts 2>/dev/null
  fi
  if command -v node &>/dev/null; then
    echo "  ✓ Node.js $(node -v) installed"
  else
    echo "  ⚠ Node.js install failed — agent works via Python REPL (install node manually for full CLI)"
  fi
else
  echo "  ✓ node $(node -v)"
fi

if [ -n "$MISSING" ]; then
  echo ""
  echo "  ✗ Missing dependencies:$MISSING"
  echo "    Install them and re-run this script."
  exit 1
fi

# --- Clone repo ---
echo ""
if [ -d "$DIR/.git" ]; then
  echo "  → Updating existing installation..."
  cd "$DIR" && git pull --ff-only 2>/dev/null || true
else
  echo "  → Cloning tsunami..."
  git clone https://github.com/gobbleyourdong/tsunami.git "$DIR"
fi
cd "$DIR"

# --- Python deps ---
echo "  → Installing Python dependencies..."
pip3 install -q httpx pyyaml 'duckduckgo-search>=7' 2>/dev/null || \
pip3 install --break-system-packages -q httpx pyyaml 'duckduckgo-search>=7' 2>/dev/null || \
pip3 install --user -q httpx pyyaml 'duckduckgo-search>=7' 2>/dev/null || \
echo "  ⚠ pip install failed — try: pip3 install --break-system-packages httpx pyyaml"

# --- Node deps (optional) ---
if command -v node &>/dev/null && [ -d "$DIR/cli" ]; then
  echo "  → Installing CLI frontend..."
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

  cmake "$LLAMA_DIR" -B "$LLAMA_DIR/build" $CMAKE_ARGS 2>/dev/null
  CORES=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
  cmake --build "$LLAMA_DIR/build" --config Release -j"$CORES" \
    --target llama-server 2>/dev/null
  echo "  ✓ llama.cpp built"
else
  echo "  ✓ llama.cpp already built"
fi

# --- Download models ---
mkdir -p "$MODELS_DIR"

download() {
  local repo="$1" file="$2"
  local dest
  dest="$(cd "$DIR" && mkdir -p models && cd models && pwd)/$file"
  [ -f "$dest" ] && echo "  ✓ $file ($(du -h "$dest" | cut -f1))" && return
  echo "  → Downloading $file..."
  local url="https://huggingface.co/$repo/resolve/main/$file"
  curl -fSL -o "$dest" "$url" 2>&1 | tail -1
  [ -f "$dest" ] && [ "$(stat -c%s "$dest" 2>/dev/null || stat -f%z "$dest" 2>/dev/null)" -gt 1000 ] \
    && echo "  ✓ $file ($(du -h "$dest" | cut -f1))" \
    || echo "  ✗ Download failed: $file"
}

echo ""
echo "  Downloading default model (1.2GB)..."

# Default: 2B — runs on anything, instant download
download "unsloth/Qwen3.5-2B-GGUF" "Qwen3.5-2B-Q4_K_M.gguf"

echo ""
echo "  The 2B model is installed. For better quality, add a larger model:"
echo ""
echo "    # 27B dense with vision (recommended for 32GB+ RAM):"
echo "    cd $DIR"
echo "    huggingface-cli download unsloth/Qwen3.5-27B-GGUF Qwen3.5-27B-Q8_0.gguf --local-dir models"
echo "    huggingface-cli download unsloth/Qwen3.5-27B-GGUF mmproj-BF16.gguf --local-dir models"
echo ""
echo "    Tsunami auto-detects models on startup — just drop the GGUF in models/."

# --- Create global command ---
echo ""
chmod +x "$DIR/tsu"
SHELL_RC=""
[ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"
[ -f "$HOME/.bashrc" ] && SHELL_RC="$HOME/.bashrc"

if [ -n "$SHELL_RC" ] && ! grep -q "tsunami" "$SHELL_RC" 2>/dev/null; then
  echo "" >> "$SHELL_RC"
  echo "# Tsunami AI Agent" >> "$SHELL_RC"
  echo "alias tsunami='$DIR/tsu'" >> "$SHELL_RC"
  echo "export PATH=\"$LLAMA_DIR/build/bin:\$PATH\"" >> "$SHELL_RC"
  echo "  ✓ Added 'tsunami' command to $(basename $SHELL_RC)"
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

# Check model files
echo ""
echo "  Models:"
for f in "$MODELS_DIR"/*.gguf; do
  [ -f "$f" ] && echo "  ✓ $(basename $f) ($(du -h "$f" | cut -f1))"
done

echo ""
echo "  ╔════════════════════════════════════════════╗"
echo "  ║          TSUNAMI INSTALLED                 ║"
echo "  ╠════════════════════════════════════════════╣"
echo "  ║                                            ║"
echo "  ║  1. source ~/${SHELL_RC##*/}                        ║"
echo "  ║  2. tsunami                                ║"
echo "  ║                                            ║"
echo "  ║  Or: cd $DIR && ./tsu        ║"
echo "  ║                                            ║"
echo "  ║  GPU: $GPU | RAM: ${RAM}GB | Model: $MODEL_SIZE   ║"
echo "  ╚════════════════════════════════════════════╝"
echo ""
