"""Build Tsunami desktop .exe for Windows.

Run on a Windows machine (or via GitHub Actions):
  pip install pyinstaller pywebview websockets httpx pyyaml ddgs pillow rich psutil fastapi uvicorn
  cd desktop
  python build_exe.py

Produces: dist/Tsunami.exe

The .exe bundles:
  - desktop/launcher.py (starts servers, opens UI)
  - desktop/index.html (glass-box UI)
  - desktop/ws_bridge.py + file_watcher.py (streaming)
  - tsunami/ (full agent package)
  - config.yaml
  - scaffolds/ (project templates)

Users still need external:
  - models/ folder with .gguf files (downloaded by setup.ps1)
  - llama-server.exe (downloaded by setup.ps1)
"""

import PyInstaller.__main__

PyInstaller.__main__.run([
    "launcher.py",
    "--name=Tsunami",
    "--onefile",
    "--windowed",
    # Bundle the UI and agent code
    "--add-data=index.html;.",
    "--add-data=ws_bridge.py;.",
    "--add-data=file_watcher.py;.",
    "--add-data=../tsunami;tsunami",
    "--add-data=../config.yaml;.",
    "--add-data=../scaffolds;scaffolds",
    # Hidden imports — PyInstaller can't see dynamic imports
    "--hidden-import=websockets",
    "--hidden-import=webview",
    "--hidden-import=httpx",
    "--hidden-import=yaml",
    "--hidden-import=ddgs",
    "--hidden-import=PIL",
    "--hidden-import=rich",
    "--hidden-import=psutil",
    "--hidden-import=fastapi",
    "--hidden-import=uvicorn",
    "--hidden-import=tsunami",
    "--hidden-import=tsunami.agent",
    "--hidden-import=tsunami.config",
    "--hidden-import=tsunami.cli",
    "--hidden-import=tsunami.tools",
    "--hidden-import=tsunami.tools.filesystem",
    "--hidden-import=tsunami.tools.shell",
    "--hidden-import=tsunami.tools.search",
    "--hidden-import=tsunami.tools.message",
    "--hidden-import=tsunami.tools.generate",
    "--hidden-import=tsunami.tools.project_init",
    "--hidden-import=tsunami.tools.browser",
    "--hidden-import=tsunami.tools.swell",
    "--hidden-import=tsunami.tools.undertow",
    "--hidden-import=tsunami.tools.plan",
    "--hidden-import=tsunami.tools.match",
    "--hidden-import=tsunami.tools.python_exec",
    "--hidden-import=tsunami.tools.summarize",
    "--hidden-import=tsunami.tools.toolbox",
    "--hidden-import=tsunami.eddy",
    "--hidden-import=tsunami.model",
    "--hidden-import=tsunami.prompt",
    "--hidden-import=tsunami.state",
    "--hidden-import=tsunami.serve",
    "--hidden-import=tsunami.serve_daemon",
    "--hidden-import=tsunami.current",
    "--hidden-import=tsunami.pressure",
    "--hidden-import=tsunami.circulation",
    "--hidden-import=tsunami.undertow",
    "--hidden-import=tsunami.compression",
    "--hidden-import=tsunami.observer",
    "--hidden-import=tsunami.session",
    # Suppress console window (windowed mode)
    "--noconsole",
])

print()
print("Built: dist/Tsunami.exe")
print()
print("To distribute:")
print("  1. Copy dist/Tsunami.exe to the user's machine")
print("  2. Run setup.ps1 first (downloads models + llama-server)")
print("  3. Double-click Tsunami.exe")
