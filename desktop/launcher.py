"""Tsunami Desktop Launcher — starts servers, opens UI.

For Windows: PyInstaller bundles this into a .exe
For Mac/Linux: python3 launcher.py

Starts:
1. llama-server (9B wave or 2B lite on :8090)
2. llama-server (2B eddy on :8092, full mode only)
3. SD-Turbo image gen (always, if available)
4. WebSocket bridge (agent on :3002)
5. Opens native window with the terminal UI
"""

import os
import sys
import json
import time
import signal
import subprocess
import threading
import shutil
import platform
from pathlib import Path

# Find tsunami root
SCRIPT_DIR = Path(__file__).parent.resolve()
TSUNAMI_DIR = SCRIPT_DIR.parent
MODELS_DIR = TSUNAMI_DIR / "models"
UI_PATH = SCRIPT_DIR / "index.html"

# Pinned release — matches the battle-tested setup.bat
LLAMA_TAG = "b8628"
LLAMA_ORG = "ggml-org"  # NOT ggerganov — releases moved

processes = []


def find_model(pattern):
    """Find a model file matching the pattern."""
    for f in MODELS_DIR.glob(pattern):
        return str(f)
    return None


def find_llama_server():
    """Find llama-server binary. Downloads pre-built if missing."""
    llama_dir = TSUNAMI_DIR / "llama-server"
    candidates = [
        llama_dir / "llama-server.exe",
        llama_dir / "llama-server",
        TSUNAMI_DIR / "llama.cpp" / "build" / "bin" / "llama-server",
        TSUNAMI_DIR / "llama.cpp" / "build" / "bin" / "llama-server.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)

    found = shutil.which("llama-server")
    if found:
        return found

    print("  → llama-server not found, downloading...")
    return download_llama_server()


def detect_cuda_version():
    """Detect CUDA version from nvidia-smi. Returns '12.4', '13.1', or None."""
    try:
        out = subprocess.check_output(["nvidia-smi"], text=True, timeout=5)
        for line in out.splitlines():
            if "CUDA Version:" in line:
                parts = line.split("CUDA Version:")[1].strip().split()
                ver = parts[0] if parts else ""
                major = ver.split(".")[0]
                if major == "12":
                    return "12.4"
                elif int(major) >= 13:
                    return "13.1"
    except Exception:
        pass
    return None


def download_llama_server():
    """Download pre-built llama-server from GitHub releases."""
    import urllib.request
    import zipfile
    import tarfile

    llama_dir = TSUNAMI_DIR / "llama-server"
    llama_dir.mkdir(parents=True, exist_ok=True)

    system = platform.system()
    machine = platform.machine().lower()
    tag = LLAMA_TAG
    cuda_dll_url = None

    if system == "Windows":
        cuda_ver = detect_cuda_version()
        if cuda_ver:
            asset = f"llama-{tag}-bin-win-cuda-{cuda_ver}-x64.zip"
            cuda_dll_url = f"https://github.com/{LLAMA_ORG}/llama.cpp/releases/download/{tag}/cudart-llama-bin-win-cuda-{cuda_ver}-x64.zip"
            print(f"  CUDA {cuda_ver} detected")
        else:
            asset = f"llama-{tag}-bin-win-cpu-x64.zip"
            print("  No CUDA — CPU mode")
        ext = ".zip"
        binary_name = "llama-server.exe"
    elif system == "Darwin":
        arch = "arm64" if ("arm" in machine or "aarch" in machine) else "x64"
        asset = f"llama-{tag}-bin-macos-{arch}.tar.gz"
        ext = ".tar.gz"
        binary_name = "llama-server"
    else:
        asset = f"llama-{tag}-bin-ubuntu-x64.tar.gz"
        ext = ".tar.gz"
        binary_name = "llama-server"

    url = f"https://github.com/{LLAMA_ORG}/llama.cpp/releases/download/{tag}/{asset}"
    archive_path = llama_dir / f"llama{ext}"

    print(f"  Downloading {asset}...")
    try:
        urllib.request.urlretrieve(url, str(archive_path))
    except Exception as e:
        if "cuda" in asset:
            print(f"  CUDA failed, trying CPU...")
            cpu_asset = f"llama-{tag}-bin-win-cpu-x64.zip"
            cpu_url = f"https://github.com/{LLAMA_ORG}/llama.cpp/releases/download/{tag}/{cpu_asset}"
            try:
                urllib.request.urlretrieve(cpu_url, str(archive_path))
                cuda_dll_url = None  # no DLLs needed for CPU
            except Exception:
                print(f"  ✗ Download failed")
                return None
        else:
            print(f"  ✗ Download failed: {e}")
            return None

    # Extract main package
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

    # Download CUDA runtime DLLs (Windows only)
    if cuda_dll_url:
        print("  Downloading CUDA runtime DLLs...")
        dll_path = llama_dir / "cudart.zip"
        try:
            urllib.request.urlretrieve(cuda_dll_url, str(dll_path))
            with zipfile.ZipFile(str(dll_path), 'r') as z:
                z.extractall(str(llama_dir))
            dll_path.unlink(missing_ok=True)
            print("  ✓ CUDA DLLs")
        except Exception:
            print("  ⚠ CUDA DLLs failed — may still work if CUDA toolkit installed")

    # Find the binary
    for f in llama_dir.rglob(binary_name):
        if f.parent != llama_dir:
            dest = llama_dir / binary_name
            f.rename(dest)
            f = dest
        if system != "Windows":
            f.chmod(0o755)
        print(f"  ✓ {binary_name} ready")
        return str(f)

    print(f"  ✗ {binary_name} not found in archive")
    return None


def start_server(name, port, model, ctx_size=16384, parallel=1):
    """Start a llama-server instance."""
    binary = find_llama_server()
    if not binary or not model:
        print(f"  ✗ Cannot start {name}")
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

    print(f"  → Starting {name} on :{port}...")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    processes.append(proc)
    return proc


def start_image_gen():
    """Start SD-Turbo image generation server if available."""
    serve_path = TSUNAMI_DIR / "serve_diffusion.py"
    if not serve_path.exists():
        return None

    # Check if diffusers is installed
    try:
        subprocess.check_output([sys.executable, "-c", "import diffusers"], timeout=5, stderr=subprocess.DEVNULL)
    except Exception:
        print("  ⚠ Image gen: install diffusers for SD-Turbo (pip install diffusers torch)")
        return None

    print("  → Starting SD-Turbo image gen...")
    proc = subprocess.Popen(
        [sys.executable, str(serve_path)],
        cwd=str(TSUNAMI_DIR),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    processes.append(proc)
    return proc


def start_ws_bridge():
    """Start the WebSocket bridge."""
    bridge_path = SCRIPT_DIR / "ws_bridge.py"
    if not bridge_path.exists():
        return None

    proc = subprocess.Popen(
        [sys.executable, str(bridge_path)],
        cwd=str(TSUNAMI_DIR),
    )
    processes.append(proc)
    return proc


def get_available_memory_gb():
    """Get GPU VRAM (preferred) or system RAM in GB."""
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


def open_ui():
    """Open the UI."""
    url = f"file://{UI_PATH}"
    try:
        import webview
        webview.create_window("Tsunami", str(UI_PATH), width=1200, height=800, background_color="#0a0a14")
        webview.start()
        return
    except ImportError:
        pass

    import webbrowser
    webbrowser.open(url)
    print(f"  UI: {url}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def cleanup():
    for proc in processes:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except:
            try:
                proc.kill()
            except:
                pass


def main():
    print("  ╔══════════════════════════╗")
    print("  ║   TSUNAMI DESKTOP        ║")
    print("  ╚══════════════════════════╝")
    print()

    mem_gb, mem_source = get_available_memory_gb()
    print(f"  {mem_source}: {mem_gb}GB")

    if mem_gb < 10:
        mode = "lite"
        print("  → Lite mode (2B + image gen)")
    else:
        mode = "full"
        print("  → Full mode (9B wave + 2B eddies + image gen)")

    # Find or download models
    wave_model = find_model("*9B*Q4*.gguf")
    eddy_model = find_model("*2B*Q4*.gguf")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    import urllib.request

    def dl(url, dest):
        if Path(dest).exists():
            return
        name = Path(dest).name
        print(f"  → Downloading {name}...")
        urllib.request.urlretrieve(url, dest)
        print(f"  ✓ {name}")

    # Always need 2B
    if not eddy_model:
        dest = str(MODELS_DIR / "Qwen3.5-2B-Q4_K_M.gguf")
        dl("https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf", dest)
        eddy_model = dest

    # 9B only in full mode
    if mode == "full" and not wave_model:
        dest = str(MODELS_DIR / "Qwen3.5-9B-Q4_K_M.gguf")
        dl("https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf", dest)
        wave_model = dest

    # Start servers
    if mode == "full" and wave_model:
        start_server("wave (9B)", 8090, wave_model, ctx_size=32768)
        start_server("eddy (2B)", 8092, eddy_model, ctx_size=16384, parallel=4)
    else:
        # Lite: 2B plays both roles — wave AND eddy
        # Start on both ports so swell/eddies still work
        start_server("wave (2B)", 8090, eddy_model, ctx_size=16384)
        start_server("eddy (2B)", 8092, eddy_model, ctx_size=8192, parallel=2)

    # Always try image gen — even lite mode gets it
    start_image_gen()

    print("  → Waiting for servers...")
    time.sleep(5)

    start_ws_bridge()
    time.sleep(1)

    print("  ✓ Ready")
    print()

    import atexit
    atexit.register(cleanup)
    signal.signal(signal.SIGTERM, lambda s, f: (cleanup(), sys.exit(0)))
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, lambda s, f: (cleanup(), sys.exit(0)))

    open_ui()
    cleanup()


if __name__ == "__main__":
    main()
