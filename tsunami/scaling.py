"""Auto-scaling eddy slots based on available memory.

Detects available RAM/VRAM, calculates how many eddy slots to run,
leaves a safety gap for the wave and OS. Two modes:

- Full: 9B wave + as many 2B eddies as memory allows (up to 32)
- Lite: 2B only, single model, 2 eddy slots (runs on 4GB)

The user never thinks about this. It just works.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys

log = logging.getLogger("tsunami.scaling")

# Memory requirements (approximate, in GB)
QUEEN_9B_MEM = 5.5    # 9B Q4_K_M + mmproj (tight)
QUEEN_27B_MEM = 27.0  # 27B Q8_0 + mmproj
EDDY_2B_MEM = 1.5     # 2B Q4_K_M + mmproj
SD_TURBO_MEM = 2.0    # SD-Turbo fp16 (image gen)
OS_RESERVE = 1.0      # leave for OS
PER_BEE_SLOT = 0.3    # additional memory per parallel eddy slot (KV cache)

MAX_BEES = 32
MIN_BEES = 1


def get_total_memory_gb() -> float:
    """Get total system memory in GB. Works on Linux, macOS, and Windows."""
    try:
        # Try GPU memory first (unified memory systems report this)
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split("\n")[0]) / 1024
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Windows
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["wmic", "computersystem", "get", "TotalPhysicalMemory", "/value"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "TotalPhysicalMemory=" in line:
                    return int(line.split("=")[1].strip()) / (1024 ** 3)
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(mem)
            if kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
                return mem.ullTotalPhys / (1024 ** 3)
        except Exception:
            pass
        return 8.0  # conservative default

    # Linux
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / (1024 * 1024)
    except FileNotFoundError:
        pass

    # macOS
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return int(result.stdout.strip()) / (1024 ** 3)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return 8.0  # conservative default


def get_available_memory_gb() -> float:
    """Get available (free) memory in GB."""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(mem)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            return mem.ullAvailPhys / (1024 ** 3)
        except Exception:
            pass
        return get_total_memory_gb() * 0.7

    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024 * 1024)
    except FileNotFoundError:
        pass

    # Fallback: assume 70% of total is available
    return get_total_memory_gb() * 0.7


def detect_queen_model(models_dir: str) -> str:
    """Detect which wave model is available (HuggingFace format)."""
    from pathlib import Path
    models = Path(models_dir)
    # Find directories with config.json (HF merged weights)
    for d in sorted(models.iterdir() if models.exists() else [], key=lambda p: p.stat().st_mtime, reverse=True):
        if d.is_dir() and (d / "config.json").exists():
            # Estimate size from directory
            size_gb = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / (1024 ** 3)
            if size_gb > 20:
                return "27b"
            elif size_gb > 3:
                return "9b"
            return "2b"
    return "none"


def calculate_bee_slots(
    total_mem_gb: float | None = None,
    queen_model: str = "9b",
) -> dict:
    """Calculate optimal eddy configuration based on available memory.

    Returns dict with:
    - mode: "full" or "lite"
    - queen_model: which model to use
    - bee_slots: number of parallel eddy slots
    - queen_mem: memory reserved for wave
    - bee_mem: memory reserved for eddies
    - total_mem: total detected memory
    """
    if total_mem_gb is None:
        total_mem_gb = get_total_memory_gb()

    queen_mem = {
        "27b": QUEEN_27B_MEM,
        "9b": QUEEN_9B_MEM,
        "2b": EDDY_2B_MEM,
    }.get(queen_model, QUEEN_9B_MEM)

    # Full mode: 9B wave + 2B eddies + SD-Turbo image gen
    # Lite mode: 2B only, no image gen
    full_base = queen_mem + EDDY_2B_MEM + SD_TURBO_MEM + OS_RESERVE
    available = total_mem_gb - full_base

    if available < 0:
        # Not enough for full stack — lite mode (2B only, no image gen)
        return {
            "mode": "lite",
            "queen_model": "2b",
            "bee_slots": MIN_BEES,
            "queen_mem": EDDY_2B_MEM,
            "bee_mem": EDDY_2B_MEM,
            "image_gen": False,
            "total_mem": total_mem_gb,
        }

    # Fill remaining memory with eddy slots
    bee_slots = int(available / PER_BEE_SLOT)
    bee_slots = max(MIN_BEES, min(bee_slots, MAX_BEES))

    return {
        "mode": "full",
        "queen_model": queen_model,
        "bee_slots": bee_slots,
        "queen_mem": queen_mem,
        "bee_mem": EDDY_2B_MEM + bee_slots * PER_BEE_SLOT,
        "image_gen": True,
        "total_mem": total_mem_gb,
    }


def format_scaling_info(config: dict) -> str:
    """Human-readable scaling summary."""
    if config["mode"] == "lite":
        return (
            f"Lite mode: 2B only, {config['bee_slots']} eddy, no image gen "
            f"({config['total_mem']:.0f}GB detected)"
        )
    img = "+ SD-Turbo" if config.get("image_gen") else ""
    return (
        f"Full mode: {config['queen_model'].upper()} wave + "
        f"{config['bee_slots']} eddies + SD-Turbo "
        f"({config['total_mem']:.0f}GB detected)"
    )


# Quick reference for README/docs
SCALING_TABLE = """
| Memory | Mode | Wave | Eddies | Image Gen | Stack |
|--------|------|------|--------|-----------|-------|
| 4GB    | Lite | 2B   | 1      | no        | 2B only |
| 8GB    | Full | 9B   | 1      | SD-Turbo  | everything |
| 12GB   | Full | 9B   | 4      | SD-Turbo  | everything |
| 16GB   | Full | 9B   | 8      | SD-Turbo  | everything |
| 24GB   | Full | 9B   | 16     | SD-Turbo  | everything |
| 32GB+  | Full | 27B  | 4+     | SD-Turbo  | everything |
| 64GB+  | Full | 27B  | 32     | SD-Turbo  | maximum |
"""
