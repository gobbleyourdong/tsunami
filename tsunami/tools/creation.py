"""Creation tools — the artist, the bridge, the clock.

These tools build things, expose services, and schedule actions.
An agent produces deliverables, not just text.
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import shutil
import subprocess
import sys
from pathlib import Path

from .base import BaseTool, ToolResult


class FileView(BaseTool):
    name = "file_view"
    description = (
        "View non-text files: images (dimensions, format), PDFs (page count, text extract), "
        "binary files (type, size). The deeper eye: see what text cannot capture."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to view"},
            },
            "required": ["path"],
        }

    async def execute(self, path: str, **kw) -> ToolResult:
        try:
            p = Path(path).expanduser().resolve()
            if not p.exists():
                return ToolResult(f"File not found: {path}", is_error=True)

            size = p.stat().st_size
            mime, _ = mimetypes.guess_type(str(p))
            mime = mime or "application/octet-stream"

            info = [f"File: {p.name}", f"Size: {_human_size(size)}", f"Type: {mime}"]

            # Image info via Python
            if mime.startswith("image/"):
                try:
                    result = subprocess.run(
                        [sys.executable, "-c", f"from PIL import Image; im=Image.open('{p}'); print(im.size, im.mode)"],
                        capture_output=True, text=True, timeout=10,
                    )
                    if result.returncode == 0:
                        info.append(f"Image details: {result.stdout.strip()}")
                    else:
                        # Fallback: file command
                        result = subprocess.run(["file", str(p)], capture_output=True, text=True, timeout=5)
                        info.append(f"Details: {result.stdout.strip()}")
                except Exception:
                    pass

            # PDF info + text extraction
            elif mime == "application/pdf":
                try:
                    result = subprocess.run(
                        ["pdfinfo", str(p)],
                        capture_output=True, text=True, timeout=10,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        info.append(f"PDF info:\n{result.stdout.strip()}")
                except Exception:
                    pass

                # Extract first ~2000 chars of text content
                try:
                    result = subprocess.run(
                        ["pdftotext", "-l", "3", str(p), "-"],
                        capture_output=True, text=True, timeout=15,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        text = result.stdout.strip()[:2000]
                        info.append(f"Text content (first 3 pages):\n{text}")
                except Exception:
                    pass

            # Text-like files: show first few lines
            elif any(mime.startswith(t) for t in ("text/", "application/json", "application/xml")):
                try:
                    text = p.read_text(errors="replace")[:2000]
                    info.append(f"Content preview:\n{text}")
                except Exception:
                    pass
            else:
                # Binary: show hex header
                try:
                    with open(p, "rb") as f:
                        header = f.read(64)
                    hex_str = " ".join(f"{b:02x}" for b in header)
                    info.append(f"Hex header: {hex_str}")
                except Exception:
                    pass

            return ToolResult("\n".join(info))
        except Exception as e:
            return ToolResult(f"Error viewing {path}: {e}", is_error=True)


class ExposeTool(BaseTool):
    name = "expose"
    description = (
        "Make a local service publicly accessible via a tunnel. "
        "The bridge: connect the sandbox to the world."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "port": {"type": "integer", "description": "Local port to expose"},
                "protocol": {"type": "string", "enum": ["http", "tcp"], "default": "http"},
            },
            "required": ["port"],
        }

    async def execute(self, port: int, protocol: str = "http", **kw) -> ToolResult:
        # Try multiple tunnel services in order of preference
        for method in [self._try_ssh_tunnel, self._try_ngrok, self._try_cloudflared]:
            result = await method(port, protocol)
            if not result.is_error:
                return result

        return ToolResult(
            f"No tunnel service available. Install one of: ngrok, cloudflared, or configure SSH. "
            f"Alternatively, use: ssh -R 80:localhost:{port} serveo.net",
            is_error=True,
        )

    async def _try_ssh_tunnel(self, port: int, protocol: str) -> ToolResult:
        try:
            # serveo.net — free, no install needed
            proc = await asyncio.create_subprocess_exec(
                "ssh", "-o", "StrictHostKeyChecking=no", "-R", f"80:localhost:{port}", "serveo.net",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
                output = stdout.decode()
                if "https://" in output:
                    url = [line for line in output.splitlines() if "https://" in line][0].strip()
                    return ToolResult(f"Exposed localhost:{port} at {url}")
            except asyncio.TimeoutError:
                proc.kill()
            return ToolResult("SSH tunnel failed", is_error=True)
        except Exception as e:
            return ToolResult(f"SSH tunnel error: {e}", is_error=True)

    async def _try_ngrok(self, port: int, protocol: str) -> ToolResult:
        try:
            if not shutil.which("ngrok"):
                return ToolResult("ngrok not found", is_error=True)

            proc = await asyncio.create_subprocess_exec(
                "ngrok", protocol, str(port), "--log=stdout",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
                output = stdout.decode()
                for line in output.splitlines():
                    if "url=" in line:
                        url = line.split("url=")[1].strip()
                        return ToolResult(f"Exposed localhost:{port} at {url}")
            except asyncio.TimeoutError:
                proc.kill()
            return ToolResult("ngrok failed to start", is_error=True)
        except Exception as e:
            return ToolResult(f"ngrok error: {e}", is_error=True)

    async def _try_cloudflared(self, port: int, protocol: str) -> ToolResult:
        try:
            if not shutil.which("cloudflared"):
                return ToolResult("cloudflared not found", is_error=True)

            proc = await asyncio.create_subprocess_exec(
                "cloudflared", "tunnel", "--url", f"http://localhost:{port}",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
                output = stderr.decode()
                for line in output.splitlines():
                    if ".trycloudflare.com" in line:
                        url = line.split("https://")[1].split()[0] if "https://" in line else line
                        return ToolResult(f"Exposed localhost:{port} at https://{url}")
            except asyncio.TimeoutError:
                proc.kill()
            return ToolResult("cloudflared failed", is_error=True)
        except Exception as e:
            return ToolResult(f"cloudflared error: {e}", is_error=True)


class ScheduleTool(BaseTool):
    name = "schedule"
    description = "Schedule a shell command for future or recurring execution. The clock: act when the time is right."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to schedule"},
                "delay_seconds": {
                    "type": "integer",
                    "description": "Seconds to wait before executing (for one-shot)",
                    "default": 0,
                },
                "cron": {
                    "type": "string",
                    "description": "Cron expression for recurring execution (e.g. '*/5 * * * *')",
                    "default": "",
                },
            },
            "required": ["command"],
        }

    async def execute(self, command: str, delay_seconds: int = 0, cron: str = "", **kw) -> ToolResult:
        if cron:
            if sys.platform == "win32":
                # Windows Task Scheduler does not natively support cron expressions.
                # Return an informative error rather than silently creating a wrong schedule.
                return ToolResult(
                    "Cron scheduling is not supported on Windows. "
                    "Use Windows Task Scheduler (taskschd.msc) manually, or run this on Linux/macOS.",
                    is_error=True,
                )
            else:
                # Add to user's crontab (Unix)
                try:
                    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
                    existing = result.stdout if result.returncode == 0 else ""

                    new_entry = f"{cron} {command}"
                    if new_entry in existing:
                        return ToolResult(f"Cron job already exists: {new_entry}")

                    new_crontab = existing.rstrip() + f"\n{new_entry}\n"
                    proc = subprocess.run(
                        ["crontab", "-"], input=new_crontab, capture_output=True, text=True
                    )
                    if proc.returncode == 0:
                        return ToolResult(f"Scheduled recurring: {cron} → {command}")
                    else:
                        return ToolResult(f"Failed to set crontab: {proc.stderr}", is_error=True)
                except Exception as e:
                    return ToolResult(f"Cron error: {e}", is_error=True)

        elif delay_seconds > 0:
            # One-shot with delay using asyncio (cross-platform)
            try:
                async def _run_delayed():
                    await asyncio.sleep(delay_seconds)
                    proc = await asyncio.create_subprocess_shell(command)
                    await proc.wait()

                asyncio.create_task(_run_delayed())
                return ToolResult(f"Scheduled: '{command}' will run in {delay_seconds}s")
            except Exception as e:
                return ToolResult(f"Schedule error: {e}", is_error=True)

        else:
            return ToolResult(
                "Provide either delay_seconds (one-shot) or cron (recurring).",
                is_error=True,
            )


def _human_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
