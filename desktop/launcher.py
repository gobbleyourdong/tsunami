"""Tsunami Desktop Launcher — starts servers, opens UI.

For Windows: PyInstaller bundles this into a .exe
For Mac/Linux: python3 launcher.py

Starts:
1. llama-server (9B wave on :8090)
2. llama-server (2B eddy on :8092)
3. WebSocket bridge (agent on :3002)
4. Opens native window with the terminal UI
"""

import os
import sys
import json
import time
import signal
import subprocess
import threading
import asyncio
from pathlib import Path

# Find tsunami root
SCRIPT_DIR = Path(__file__).parent.resolve()
TSUNAMI_DIR = SCRIPT_DIR.parent
MODELS_DIR = TSUNAMI_DIR / "models"
UI_PATH = SCRIPT_DIR / "index.html"

processes = []


def find_model(pattern):
    """Find a model file matching the pattern."""
    for f in MODELS_DIR.glob(pattern):
        return str(f)
    return None


def find_llama_server():
    """Find llama-server binary. Downloads pre-built if missing on Windows."""
    llama_dir = TSUNAMI_DIR / "llama-server"
    candidates = [
        llama_dir / "llama-server.exe",
        llama_dir / "llama-server",
        TSUNAMI_DIR / "llama.cpp" / "build" / "bin" / "llama-server",
        TSUNAMI_DIR / "llama.cpp" / "build" / "bin" / "llama-server.exe",
        TSUNAMI_DIR / "llama.cpp" / "build" / "bin" / "Release" / "llama-server.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)

    # Try PATH
    import shutil
    found = shutil.which("llama-server")
    if found:
        return found

    # Not found — download pre-built binary
    print("  → llama-server not found, downloading pre-built binary...")
    return download_llama_server()


def download_llama_server():
    """Download pre-built llama-server from GitHub releases."""
    import platform
    import urllib.request
    import zipfile
    import tarfile

    llama_dir = TSUNAMI_DIR / "llama-server"
    llama_dir.mkdir(parents=True, exist_ok=True)

    # Get latest release tag
    try:
        import json
        req = urllib.request.Request(
            "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest",
            headers={"User-Agent": "Tsunami/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            tag = json.loads(resp.read())["tag_name"]
    except Exception:
        tag = "b8611"

    print(f"  Release: {tag}")

    system = platform.system()
    machine = platform.machine().lower()

    # Pick the right binary
    if system == "Windows":
        # Check for NVIDIA GPU
        has_nvidia = shutil.which("nvidia-smi") is not None
        if has_nvidia:
            asset = f"llama-{tag}-bin-win-cuda-12.4-x64.zip"
        else:
            asset = f"llama-{tag}-bin-win-cpu-x64.zip"
        ext = ".zip"
        binary_name = "llama-server.exe"
    elif system == "Darwin":
        if "arm" in machine or "aarch" in machine:
            asset = f"llama-{tag}-bin-macos-arm64.tar.gz"
        else:
            asset = f"llama-{tag}-bin-macos-x64.tar.gz"
        ext = ".tar.gz"
        binary_name = "llama-server"
    else:  # Linux
        asset = f"llama-{tag}-bin-ubuntu-x64.tar.gz"
        ext = ".tar.gz"
        binary_name = "llama-server"

    url = f"https://github.com/ggerganov/llama.cpp/releases/download/{tag}/{asset}"
    archive_path = llama_dir / f"llama{ext}"

    print(f"  Downloading {asset}...")
    try:
        urllib.request.urlretrieve(url, str(archive_path))
    except Exception as e:
        # Fallback to CPU version
        if "cuda" in asset:
            print(f"  CUDA download failed, trying CPU...")
            asset = asset.replace("cuda-12.4", "cpu")
            url = f"https://github.com/ggerganov/llama.cpp/releases/download/{tag}/{asset}"
            try:
                urllib.request.urlretrieve(url, str(archive_path))
            except Exception as e2:
                print(f"  ✗ Download failed: {e2}")
                return None
        else:
            print(f"  ✗ Download failed: {e}")
            return None

    # Extract
    print("  Extracting...")
    try:
        if ext == ".zip":
            with zipfile.ZipFile(str(archive_path), 'r') as z:
                z.extractall(str(llama_dir))
        else:
            with tarfile.open(str(archive_path), 'r:gz') as t:
                t.extractall(str(llama_dir))
    except Exception as e:
        print(f"  ✗ Extract failed: {e}")
        return None

    archive_path.unlink(missing_ok=True)

    # Find the binary in extracted files
    for f in llama_dir.rglob(binary_name):
        # Move to top level
        if f.parent != llama_dir:
            dest = llama_dir / binary_name
            f.rename(dest)
            f = dest
        # Make executable on Unix
        if system != "Windows":
            f.chmod(0o755)
        print(f"  ✓ {binary_name} ready")
        return str(f)

    print(f"  ✗ {binary_name} not found in archive")
    return None


def start_server(name, port, model, ctx_size=16384, parallel=1, extra_args=None):
    """Start a llama-server instance."""
    binary = find_llama_server()
    if not binary:
        print(f"  ✗ llama-server not found — build it first")
        return None

    if not model:
        print(f"  ✗ Model not found for {name}")
        return None

    cmd = [
        binary, "-m", model,
        "--port", str(port),
        "--ctx-size", str(ctx_size),
        "--parallel", str(parallel),
        "--n-gpu-layers", "99",
        "--jinja",
        "--chat-template-kwargs", '{"enable_thinking":false}',
    ]
    if extra_args:
        cmd.extend(extra_args)

    print(f"  → Starting {name} on :{port}...")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    processes.append(proc)
    return proc


def start_ws_bridge():
    """Start the WebSocket bridge that connects the UI to the agent."""
    bridge_path = SCRIPT_DIR / "ws_bridge.py"
    if not bridge_path.exists():
        print("  ✗ ws_bridge.py not found")
        return None

    proc = subprocess.Popen(
        [sys.executable, str(bridge_path)],
        cwd=str(TSUNAMI_DIR),
    )
    processes.append(proc)
    return proc


def open_ui():
    """Open the UI in a native window or browser."""
    url = f"file://{UI_PATH}"

    # Try pywebview first (native window)
    try:
        import webview
        webview.create_window(
            "Tsunami",
            str(UI_PATH),
            width=1200,
            height=800,
            background_color="#0a0a14",
        )
        webview.start()
        return
    except ImportError:
        pass

    # Fallback: open in browser
    import webbrowser
    webbrowser.open(url)
    print(f"  UI opened in browser: {url}")
    print("  For native window: pip install pywebview")
    # Keep alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def cleanup():
    """Kill all child processes."""
    for proc in processes:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except:
            proc.kill()


def get_available_memory_gb():
    """Get GPU VRAM (preferred) or system RAM in GB. Returns (gb, source)."""
    import shutil

    # Try NVIDIA VRAM first
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                text=True, timeout=5,
            )
            vram_mb = int(out.strip().split("\n")[0])
            if vram_mb > 0:
                return vram_mb // 1024, "GPU VRAM"
        except Exception:
            pass

    # Fallback to system RAM
    import platform
    try:
        if platform.system() == "Darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            return int(out.strip()) // (1024**3), "unified"
        elif platform.system() == "Windows":
            import ctypes
            mem = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(mem))
            return mem.value // (1024 * 1024), "RAM"
        else:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) // (1024 * 1024), "RAM"
    except Exception:
        pass
    return 8, "RAM"


def main():
    print("  ╔══════════════════════════╗")
    print("  ║   TSUNAMI DESKTOP        ║")
    print("  ╚══════════════════════════╝")
    print()

    # Detect VRAM/RAM and pick mode
    mem_gb, mem_source = get_available_memory_gb()
    print(f"  {mem_source}: {mem_gb}GB")

    if mem_gb < 10:
        mode = "lite"
        print("  → Lite mode (2B only — low memory detected)")
    else:
        mode = "full"
        print("  → Full mode (9B wave + 2B eddies)")

    # Find or download models
    wave_model = find_model("*9B*Q4*.gguf") or find_model("*Qwen*9B*.gguf")
    eddy_model = find_model("*2B*Q4*.gguf") or find_model("*Qwen*2B*.gguf")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    import urllib.request

    def download_model(url, dest):
        name = Path(dest).name
        if Path(dest).exists():
            return
        print(f"  → Downloading {name}...")
        print(f"    One-time download. Please wait.")
        urllib.request.urlretrieve(url, dest)
        print(f"  ✓ {name}")

    # Always need 2B (used as eddy in full mode, or as the brain in lite mode)
    if not eddy_model:
        dest = str(MODELS_DIR / "Qwen3.5-2B-Q4_K_M.gguf")
        download_model("https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf", dest)
        eddy_model = dest

    # Only download 9B if we have enough RAM
    if mode == "full" and not wave_model:
        dest = str(MODELS_DIR / "Qwen3.5-9B-Q4_K_M.gguf")
        download_model("https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf", dest)
        wave_model = dest

    # Start servers based on mode
    if mode == "full" and wave_model:
        start_server("wave (9B)", 8090, wave_model, ctx_size=32768)
        start_server("eddy (2B)", 8092, eddy_model, ctx_size=16384, parallel=4)
    else:
        # Lite: 2B does everything
        start_server("wave (2B lite)", 8090, eddy_model, ctx_size=16384)
        print("  ⚠ Lite mode: 2B only. Results will be simpler.")

    # Wait for servers to start
    print("  → Waiting for servers...")
    time.sleep(5)

    # Start WS bridge
    start_ws_bridge()
    time.sleep(1)

    print("  ✓ Ready")
    print()

    # Register cleanup
    import atexit
    atexit.register(cleanup)
    signal.signal(signal.SIGTERM, lambda s, f: (cleanup(), sys.exit(0)))
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, lambda s, f: (cleanup(), sys.exit(0)))

    # Open UI
    open_ui()

    cleanup()


if __name__ == "__main__":
    main()
