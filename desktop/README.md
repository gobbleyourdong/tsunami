# Tsunami Desktop

Terminal-style desktop app with split panes. No coding required.

## How it works

1. Run `python launcher.py`
2. Model server starts automatically (serve_transformers.py on port 8090)
3. Native window opens with a terminal-style prompt
4. Type what you want to build
5. Watch it happen

## Split Panes

- **Right-click** → Split Right (new pane)
- **Right-click** → Close Pane
- Each pane is an independent agent session
- Run multiple builds in parallel

## Running

```bash
# Mac/Linux
pip install pywebview websockets
python launcher.py

# Or just open index.html in a browser
# (start the servers manually first)
```

## Architecture

```
launcher.py    → starts serve_transformers.py + ws_bridge, opens UI
ws_bridge.py   → WebSocket server, connects UI to agent
index.html     → terminal-style UI with split panes
```
