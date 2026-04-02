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
    """Find llama-server binary."""
    candidates = [
        TSUNAMI_DIR / "llama.cpp" / "build" / "bin" / "llama-server",
        Path.home() / "llama.cpp" / "build" / "bin" / "llama-server",
        # Windows paths
        TSUNAMI_DIR / "llama.cpp" / "build" / "bin" / "Release" / "llama-server.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    # Try PATH
    import shutil
    return shutil.which("llama-server")


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


def main():
    print("  ╔══════════════════════════╗")
    print("  ║   TSUNAMI DESKTOP        ║")
    print("  ╚══════════════════════════╝")
    print()

    # Find models
    wave_model = find_model("*9B*Q4*.gguf") or find_model("*Qwen*9B*.gguf")
    eddy_model = find_model("*2B*Q4*.gguf") or find_model("*Qwen*2B*.gguf")

    if not wave_model:
        print("  ✗ No 9B model found in models/")
        print("    Run setup.sh first to download models")
        input("  Press Enter to exit...")
        sys.exit(1)

    # Start servers
    start_server("wave (9B)", 8090, wave_model, ctx_size=32768)
    if eddy_model:
        start_server("eddy (2B)", 8092, eddy_model, ctx_size=16384, parallel=4)

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
