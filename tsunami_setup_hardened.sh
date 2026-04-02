#!/usr/bin/env bash
# TSUNAMI - Hardened Installer Template
#
# This version fails closed by default:
# - no curl | bash
# - no mutable Git refs like main
# - no unverified model downloads
# - no system-wide pip installs
# - no shell rc edits unless explicitly enabled
#
# Required before running:
#   export TSUNAMI_REPO_REF="<pinned tag or commit ref>"
#   export LLAMA_CPP_REF="<pinned tag or commit ref>"
#   export MODEL_MANIFEST="/absolute/path/to/model-manifest.txt"
#
# MODEL_MANIFEST format:
#   repo|revision|filename|sha256
# Example:
#   unsloth/Qwen3.5-2B-GGUF|<hf-revision>|Qwen3.5-2B-Q4_K_M.gguf|<sha256>

set -Eeuo pipefail
IFS=$'\n\t'

readonly SCRIPT_NAME="$(basename "$0")"

trap 'echo "[$SCRIPT_NAME] failed at line $LINENO" >&2' ERR

echo "
  ╔════════════════════════════════════╗
  ║  TSUNAMI - Hardened Installation  ║
  ║  Local install with verification  ║
  ╚════════════════════════════════════╝
"

DIR="${TSUNAMI_DIR:-$HOME/tsunami}"
MODELS_DIR="$DIR/models"
VENV_DIR="$DIR/.venv"
TSUNAMI_REPO_URL="${TSUNAMI_REPO_URL:-https://github.com/gobbleyourdong/tsunami.git}"
LLAMA_CPP_URL="${LLAMA_CPP_URL:-https://github.com/ggerganov/llama.cpp.git}"
MODEL_MANIFEST="${MODEL_MANIFEST:-}"
INSTALL_SHELL_ALIAS="${INSTALL_SHELL_ALIAS:-0}"
ALLOW_UNPINNED_DEPS="${ALLOW_UNPINNED_DEPS:-0}"

require_env() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    echo "Missing required environment variable: $name" >&2
    exit 1
  fi
}

require_file() {
  local path="$1"
  if [ ! -f "$path" ]; then
    echo "Required file not found: $path" >&2
    exit 1
  fi
}

require_pinned_ref() {
  local ref="$1"
  case "$ref" in
    ""|main|master|HEAD|head|latest|stable)
      echo "Refusing mutable or empty ref: $ref" >&2
      exit 1
      ;;
  esac
}

require_sha256_value() {
  local value="$1"
  case "$value" in
    [0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]*)
      ;;
    *)
      echo "Invalid SHA-256 value: $value" >&2
      exit 1
      ;;
  esac

  if [ "${#value}" -ne 64 ]; then
    echo "Invalid SHA-256 length for: $value" >&2
    exit 1
  fi
}

sha256_bin() {
  if command -v sha256sum >/dev/null 2>&1; then
    echo "sha256sum"
    return
  fi
  if command -v shasum >/dev/null 2>&1; then
    echo "shasum -a 256"
    return
  fi
  echo "No SHA-256 tool found. Install coreutils or use a system with shasum." >&2
  exit 1
}

readonly SHA256_CMD="$(sha256_bin)"

sha256_file() {
  local file="$1"
  if [ "$SHA256_CMD" = "sha256sum" ]; then
    sha256sum "$file" | awk '{print $1}'
  else
    shasum -a 256 "$file" | awk '{print $1}'
  fi
}

verify_sha256() {
  local file="$1"
  local expected="$2"
  local actual
  actual="$(sha256_file "$file")"
  if [ "$actual" != "$expected" ]; then
    echo "Checksum mismatch for $file" >&2
    echo "Expected: $expected" >&2
    echo "Actual:   $actual" >&2
    exit 1
  fi
}

detect_ram_gb() {
  local ram
  ram="$(free -g 2>/dev/null | awk '/^Mem:/{print $2}' || true)"
  if [ -n "$ram" ]; then
    echo "$ram"
    return
  fi
  ram="$(sysctl -n hw.memsize 2>/dev/null | awk '{print int($1/1073741824)}' || true)"
  if [ -n "$ram" ]; then
    echo "$ram"
    return
  fi
  echo "0"
}

require_dep() {
  local dep="$1"
  local help="$2"
  if ! command -v "$dep" >/dev/null 2>&1; then
    echo "Missing dependency: $dep" >&2
    echo "Install it first: $help" >&2
    exit 1
  fi
  echo "  - $dep"
}

clone_or_update_ref() {
  local url="$1"
  local path="$2"
  local ref="$3"

  require_pinned_ref "$ref"

  if [ ! -d "$path/.git" ]; then
    git clone --filter=blob:none "$url" "$path"
  fi

  git -C "$path" fetch --depth 1 origin "$ref"
  git -C "$path" checkout --detach FETCH_HEAD
  git -C "$path" submodule update --init --recursive
}

download_verified() {
  local url="$1"
  local dest="$2"
  local expected_sha="$3"
  local tmp

  require_sha256_value "$expected_sha"

  mkdir -p "$(dirname "$dest")"

  if [ -f "$dest" ]; then
    verify_sha256 "$dest" "$expected_sha"
    echo "  - verified cached $(basename "$dest")"
    return
  fi

  tmp="${dest}.partial"
  rm -f "$tmp"
  echo "  - downloading $(basename "$dest")"
  curl --fail --location --proto '=https' --tlsv1.2 --output "$tmp" "$url"
  verify_sha256 "$tmp" "$expected_sha"
  mv "$tmp" "$dest"
}

install_python_deps() {
  if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  python -m pip install --upgrade pip

  if [ -f "$DIR/requirements.lock" ]; then
    python -m pip install --require-virtualenv -r "$DIR/requirements.lock"
    return
  fi

  if [ "$ALLOW_UNPINNED_DEPS" = "1" ] && [ -f "$DIR/requirements.txt" ]; then
    echo "  - warning: installing unpinned requirements.txt because ALLOW_UNPINNED_DEPS=1"
    python -m pip install --require-virtualenv -r "$DIR/requirements.txt"
    return
  fi

  echo "No pinned Python lockfile found at $DIR/requirements.lock" >&2
  echo "Refusing to install mutable Python dependencies." >&2
  exit 1
}

install_node_deps() {
  if [ ! -d "$DIR/cli" ]; then
    return
  fi

  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "  - skipping CLI install: node/npm not present"
    return
  fi

  if [ -f "$DIR/cli/package-lock.json" ]; then
    (cd "$DIR/cli" && npm ci)
    return
  fi

  echo "  - skipping CLI install: package-lock.json missing"
}

pick_mode() {
  local ram="$1"
  if [ "$ram" -lt 6 ]; then
    echo "lite|2B"
  elif [ "$ram" -lt 32 ]; then
    echo "full|9B"
  else
    echo "full|27B"
  fi
}

gpu_mode() {
  local os="$1"
  local arch="$2"
  if command -v nvidia-smi >/dev/null 2>&1; then
    echo "cuda"
    return
  fi
  if [ -d "/opt/rocm" ]; then
    echo "rocm"
    return
  fi
  if [ "$os" = "Darwin" ] && [ "$arch" = "arm64" ]; then
    echo "metal"
    return
  fi
  echo "cpu"
}

build_llama() {
  local gpu="$1"
  local build_dir="$DIR/llama.cpp/build"
  local bin_path="$build_dir/bin/llama-server"
  local cmake_args
  local cores

  if [ -x "$bin_path" ]; then
    echo "  - llama.cpp already built"
    return
  fi

  cmake_args="-DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF"
  case "$gpu" in
    cuda) cmake_args="$cmake_args -DGGML_CUDA=ON" ;;
    rocm) cmake_args="$cmake_args -DGGML_HIP=ON" ;;
    metal) cmake_args="$cmake_args -DGGML_METAL=ON" ;;
  esac

  cmake "$DIR/llama.cpp" -B "$build_dir" $cmake_args
  cores="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"
  cmake --build "$build_dir" --config Release -j"$cores" --target llama-server

  if [ ! -x "$bin_path" ]; then
    echo "llama.cpp build did not produce $bin_path" >&2
    exit 1
  fi
}

download_models() {
  local queen="$1"
  local needed
  local repo
  local revision
  local filename
  local sha
  local line

  needed="Qwen3.5-2B-Q4_K_M.gguf"
  if [ "$queen" = "9B" ]; then
    needed="$needed
Qwen3.5-9B-Q4_K_M.gguf"
  elif [ "$queen" = "27B" ]; then
    needed="$needed
Qwen3.5-27B-Q8_0.gguf"
  fi

  echo "  Installing models listed in $MODEL_MANIFEST"
  while IFS='|' read -r repo revision filename sha; do
    [ -z "$repo" ] && continue
    [ "${repo#\#}" != "$repo" ] && continue

    require_pinned_ref "$revision"

    if ! printf '%s\n' "$needed" | grep -Fxq "$filename" && [ "$filename" != "mmproj-2B-BF16.gguf" ] && [ "$filename" != "mmproj-9B-BF16.gguf" ] && [ "$filename" != "mmproj-27B-BF16.gguf" ]; then
      continue
    fi

    download_verified \
      "https://huggingface.co/$repo/resolve/$revision/$filename" \
      "$MODELS_DIR/$filename" \
      "$sha"
  done < "$MODEL_MANIFEST"

  for line in $needed; do
    if [ ! -f "$MODELS_DIR/$line" ]; then
      echo "Required model missing after manifest processing: $line" >&2
      exit 1
    fi
  done

  if [ ! -f "$MODELS_DIR/mmproj-2B-BF16.gguf" ]; then
    echo "Required projector model missing: mmproj-2B-BF16.gguf" >&2
    exit 1
  fi

  if [ "$queen" = "9B" ] && [ ! -f "$MODELS_DIR/mmproj-9B-BF16.gguf" ]; then
    echo "Required projector model missing: mmproj-9B-BF16.gguf" >&2
    exit 1
  fi

  if [ "$queen" = "27B" ] && [ ! -f "$MODELS_DIR/mmproj-27B-BF16.gguf" ]; then
    echo "Required projector model missing: mmproj-27B-BF16.gguf" >&2
    exit 1
  fi
}

persist_shell_alias() {
  local shell_rc=""

  if [ "$INSTALL_SHELL_ALIAS" != "1" ]; then
    echo "  - not editing shell rc (set INSTALL_SHELL_ALIAS=1 to enable)"
    return
  fi

  if [ -f "$HOME/.zshrc" ]; then
    shell_rc="$HOME/.zshrc"
  elif [ -f "$HOME/.bashrc" ]; then
    shell_rc="$HOME/.bashrc"
  fi

  if [ -z "$shell_rc" ]; then
    echo "  - no supported shell rc file found"
    return
  fi

  if grep -q "alias tsunami=" "$shell_rc" 2>/dev/null; then
    echo "  - shell alias already present in $(basename "$shell_rc")"
    return
  fi

  {
    echo ""
    echo "# Tsunami AI Agent"
    echo "alias tsunami='$DIR/tsu'"
    echo "export PATH=\"$DIR/llama.cpp/build/bin:\$PATH\""
  } >> "$shell_rc"
  echo "  - added alias to $(basename "$shell_rc")"
}

verify_install() {
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  python - <<'PY'
from tsunami.config import TsunamiConfig
from tsunami.tools import build_registry

config = TsunamiConfig.from_yaml("config.yaml")
registry = build_registry(config)
print(f"  - Agent verified: {len(registry.schemas())} tools ready")
PY
}

require_env TSUNAMI_REPO_REF
require_env LLAMA_CPP_REF
require_env MODEL_MANIFEST
require_file "$MODEL_MANIFEST"

OS="$(uname -s)"
ARCH="$(uname -m)"
RAM="$(detect_ram_gb)"
GPU="$(gpu_mode "$OS" "$ARCH")"
MODE_AND_QUEEN="$(pick_mode "$RAM")"
MODE="${MODE_AND_QUEEN%%|*}"
QUEEN="${MODE_AND_QUEEN##*|}"

echo "Platform"
echo "  - OS: $OS"
echo "  - ARCH: $ARCH"
echo "  - RAM: ${RAM}GB"
echo "  - GPU mode: $GPU"
echo "  - install mode: $MODE"
echo "  - queen model: $QUEEN"

echo ""
echo "Checking dependencies"
require_dep git "brew install git OR apt install git"
require_dep curl "brew install curl OR apt install curl"
require_dep python3 "brew install python OR apt install python3 python3-venv"
require_dep pip3 "brew install python OR apt install python3-pip"
require_dep cmake "brew install cmake OR apt install cmake"

echo ""
echo "Cloning pinned refs"
clone_or_update_ref "$TSUNAMI_REPO_URL" "$DIR" "$TSUNAMI_REPO_REF"
clone_or_update_ref "$LLAMA_CPP_URL" "$DIR/llama.cpp" "$LLAMA_CPP_REF"

mkdir -p "$MODELS_DIR"

echo ""
echo "Installing Python dependencies"
install_python_deps

echo ""
echo "Installing CLI dependencies"
install_node_deps

echo ""
echo "Building llama.cpp"
build_llama "$GPU"

echo ""
echo "Downloading models"
download_models "$QUEEN"

echo ""
echo "Persisting shell alias"
chmod +x "$DIR/tsu"
persist_shell_alias

echo ""
echo "Verifying install"
verify_install

echo ""
echo "Installed model files"
for f in "$MODELS_DIR"/*.gguf; do
  [ -f "$f" ] || continue
  echo "  - $(basename "$f")"
done

echo ""
echo "Installation complete"
echo "  source ~/.zshrc    # if you enabled INSTALL_SHELL_ALIAS=1"
echo "  cd \"$DIR\" && ./tsu"
