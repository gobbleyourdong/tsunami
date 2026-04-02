"""Build Tsunami desktop .exe for Windows.

Run on a Windows machine:
  pip install pyinstaller pywebview websockets
  python build_exe.py

Produces: dist/Tsunami.exe
"""

import PyInstaller.__main__
import sys

PyInstaller.__main__.run([
    "launcher.py",
    "--name=Tsunami",
    "--onefile",
    "--windowed",
    "--icon=icon.ico",
    "--add-data=index.html;.",
    "--add-data=ws_bridge.py;.",
    "--add-data=../tsunami;tsunami",
    "--add-data=../config.yaml;.",
    "--add-data=../scaffolds;scaffolds",
    "--hidden-import=websockets",
    "--hidden-import=webview",
    "--hidden-import=tsunami",
    "--hidden-import=tsunami.agent",
    "--hidden-import=tsunami.config",
    "--hidden-import=tsunami.tools",
])

print()
print("Built: dist/Tsunami.exe")
print("Users need: models/ folder with .gguf files + llama-server.exe")
