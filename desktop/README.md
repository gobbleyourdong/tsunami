# Tsunami Desktop

Terminal-style desktop app with split panes. No coding required.

## How it works

1. Double-click `Tsunami.exe` (or `python launcher.py`)
2. Servers start automatically (9B wave + 2B eddies)
3. Native window opens with a terminal-style prompt
4. Type what you want to build
5. Watch it happen

## Split Panes

- **Right-click** → Split Right (new pane)
- **Right-click** → Close Pane
- Each pane is an independent agent session
- Run multiple builds in parallel

## Building the .exe (Windows)

```bash
pip install pyinstaller pywebview websockets
python build_exe.py
```

Produces `dist/Tsunami.exe`. Users also need:
- `models/` folder with the .gguf model files
- `llama-server.exe` (from llama.cpp build)

## Running without .exe

```bash
# Mac/Linux
pip install pywebview websockets
python launcher.py

# Or just open index.html in a browser
# (start the servers manually first)
```

## Architecture

```
launcher.py    → starts llama-server + ws_bridge, opens UI
ws_bridge.py   → WebSocket server, connects UI to agent
index.html     → terminal-style UI with split panes
build_exe.py   → PyInstaller spec for Windows .exe
```
