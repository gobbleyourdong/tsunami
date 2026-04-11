"""Tsunami Desktop Launcher — starts servers, opens UI.

For Windows: PyInstaller bundles this into a .exe
For Mac/Linux: python3 launcher.py

Starts:
1. serve_transformers.py (model on :8090)
2. SD-Turbo image gen (if available)
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
import shutil
import platform
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
TSUNAMI_DIR = SCRIPT_DIR.parent
MODELS_DIR = TSUNAMI_DIR / "models"
UI_PATH = SCRIPT_DIR / "index.html"

processes = []


def find_model_dir():
    """Find a merged model directory (HuggingFace format)."""
    if not MODELS_DIR.exists():
        return None
    # Look for directories with config.json (HF model format)
    for d in sorted(MODELS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if d.is_dir() and (d / "config.json").exists():
            return str(d)
    return None


def start_model_server(model_dir: str, port: int = 8090):
    """Start serve_transformers.py."""
    serve_script = TSUNAMI_DIR / "serve_transformers.py"
    if not serve_script.exists():
        print(f"  ✗ serve_transformers.py not found")
        return None

    cmd = [
        sys.executable, str(serve_script),
        "--model", model_dir,
        "--port", str(port),
    ]

    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        kwargs["startupinfo"] = si
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen(cmd, **kwargs)
    processes.append(proc)
    return proc


def start_image_gen():
    """Start SD-Turbo image generation server if available."""
    serve_path = TSUNAMI_DIR / "serve_diffusion.py"
    if not serve_path.exists():
        return None

    try:
        subprocess.check_output([sys.executable, "-c", "import diffusers"], timeout=5, stderr=subprocess.DEVNULL)
    except Exception:
        print("  ⚠ Image gen: install diffusers for SD-Turbo (pip install diffusers torch)")
        return None

    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "cwd": str(TSUNAMI_DIR)}
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        kwargs["startupinfo"] = si
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen([sys.executable, str(serve_path)], **kwargs)
    processes.append(proc)
    return proc


def start_ws_bridge():
    """Start the WebSocket bridge."""
    bridge_path = SCRIPT_DIR / "ws_bridge.py"
    if not bridge_path.exists():
        return None

    kwargs = {"cwd": str(TSUNAMI_DIR), "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        kwargs["startupinfo"] = si
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen([sys.executable, str(bridge_path)], **kwargs)
    processes.append(proc)
    return proc


def open_ui():
    """Open the UI — serve via HTTP, not file://."""
    import webbrowser

    for url in ["http://localhost:3000", "http://localhost:9876"]:
        try:
            import httpx
            r = httpx.get(url, timeout=2)
            if r.status_code == 200:
                webbrowser.open(url)
                return
        except Exception:
            continue

    import subprocess
    html_dir = str(Path(__file__).parent)
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        kwargs["startupinfo"] = si
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", "9876", "--directory", html_dir],
        **kwargs,
    )
    processes.append(proc)
    time.sleep(1)
    webbrowser.open("http://localhost:9876")
    print("  UI: http://localhost:9876")


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

    model_dir = find_model_dir()
    if not model_dir:
        print("  ✗ No model found in models/")
        print("    Place merged HuggingFace weights in models/<name>/")
        sys.exit(1)

    print(f"  Model: {Path(model_dir).name}")

    # Start model server
    start_model_server(model_dir)

    # SD-Turbo image gen
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
    import multiprocessing
    multiprocessing.freeze_support()
    main()
