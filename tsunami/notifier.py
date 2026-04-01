"""Notification system — alert on long operations and completions.

Sends notifications when the agent completes a task, hits an error,
or finishes a long-running operation. Supports terminal bell,
desktop notifications (notify-send on Linux), and hook extensibility.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys

log = logging.getLogger("tsunami.notifier")


# Notification types
TASK_COMPLETE = "task_complete"
TASK_ERROR = "task_error"
LONG_OPERATION = "long_operation"


def detect_terminal() -> str:
    """Detect terminal type from environment.

    
    """
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    if "iterm" in term_program:
        return "iterm"
    if "kitty" in term_program:
        return "kitty"
    if "ghostty" in term_program:
        return "ghostty"
    if "apple_terminal" in term_program:
        return "apple_terminal"
    # Linux terminals
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return "linux_desktop"
    return "basic"


def send_bell():
    """Send terminal bell character."""
    try:
        sys.stderr.write("\a")
        sys.stderr.flush()
    except Exception:
        pass


def send_desktop_notification(title: str, message: str) -> bool:
    """Send a desktop notification. Returns True if sent successfully."""
    try:
        if sys.platform == "darwin":
            subprocess.run(
                ["osascript", "-e", f'display notification "{message}" with title "{title}"'],
                capture_output=True, timeout=5,
            )
            return True
        elif sys.platform == "win32":
            # Use PowerShell toast notification (Windows 10+)
            ps_script = (
                f'[System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms") | Out-Null; '
                f'[System.Windows.Forms.MessageBox]::Show("{message}", "{title}") | Out-Null'
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True, timeout=10,
            )
            return True
        elif sys.platform.startswith("linux"):
            result = subprocess.run(
                ["notify-send", title, message],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False


def notify(
    message: str,
    title: str = "Tsunami",
    notification_type: str = TASK_COMPLETE,
    bell: bool = True,
    desktop: bool = True,
) -> dict:
    """Send a notification through available channels.

    Returns dict with which channels were used.
    """
    channels_used = []

    # Terminal bell (always available, low-friction)
    if bell:
        send_bell()
        channels_used.append("bell")

    # Desktop notification (if display available)
    terminal = detect_terminal()
    if desktop and (sys.platform == "win32" or terminal in ("iterm", "kitty", "ghostty", "linux_desktop")):
        if send_desktop_notification(title, message):
            channels_used.append("desktop")

    log.info(f"Notification [{notification_type}]: {message} (channels: {channels_used})")

    return {
        "message": message,
        "title": title,
        "type": notification_type,
        "channels": channels_used,
        "terminal": terminal,
    }


def notify_task_complete(summary: str = "Task complete"):
    """Convenience: notify on task completion."""
    return notify(summary, notification_type=TASK_COMPLETE)


def notify_error(error: str):
    """Convenience: notify on error."""
    return notify(f"Error: {error}", notification_type=TASK_ERROR)


def notify_long_operation(operation: str):
    """Convenience: notify after a long-running operation finishes."""
    return notify(f"Done: {operation}", notification_type=LONG_OPERATION, desktop=True)
