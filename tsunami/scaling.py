"""Auto-scaling bee slots based on available memory.

Detects available RAM/VRAM, calculates how many bee slots to run,
leaves a safety gap for the queen and OS. Two modes:

- Full: 9B queen + as many 2B bees as memory allows (up to 32)
- Lite: 2B only, single model, 2 bee slots (runs on 4GB)

The user never thinks about this. It just works.
"""

from __future__ import annotations

import logging
import os
import subprocess

log = logging.getLogger("tsunami.scaling")

# Memory requirements (approximate, in GB)
QUEEN_9B_MEM = 5.5   # 9B Q4_K_M + mmproj (tight)
QUEEN_27B_MEM = 28.0  # 27B Q8_0 + mmproj
BEE_2B_MEM = 1.5      # 2B Q4_K_M + mmproj
OS_RESERVE = 1.0       # leave for OS
PER_BEE_SLOT = 0.3     # additional memory per parallel bee slot (KV cache)

MAX_BEES = 32
MIN_BEES = 1


def get_total_memory_gb() -> float:
    """Get total system memory in GB. Works on Linux and macOS."""
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

    # Fall back to system RAM
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
    """Detect which queen model is available."""
    from pathlib import Path
    models = Path(models_dir)
    if (models / "Qwen3.5-27B-Q8_0.gguf").exists():
        return "27b"
    if (models / "Qwen3.5-9B-Q4_K_M.gguf").exists():
        return "9b"
    if (models / "Qwen3.5-2B-Q4_K_M.gguf").exists():
        return "2b"
    # Check for any GGUF
    ggufs = sorted(models.glob("*.gguf"), key=lambda f: f.stat().st_size, reverse=True)
    if ggufs:
        size_gb = ggufs[0].stat().st_size / (1024 ** 3)
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
    """Calculate optimal bee configuration based on available memory.

    Returns dict with:
    - mode: "full" or "lite"
    - queen_model: which model to use
    - bee_slots: number of parallel bee slots
    - queen_mem: memory reserved for queen
    - bee_mem: memory reserved for bees
    - total_mem: total detected memory
    """
    if total_mem_gb is None:
        total_mem_gb = get_total_memory_gb()

    queen_mem = {
        "27b": QUEEN_27B_MEM,
        "9b": QUEEN_9B_MEM,
        "2b": BEE_2B_MEM,
    }.get(queen_model, QUEEN_9B_MEM)

    # Calculate available memory for bees
    available = total_mem_gb - queen_mem - OS_RESERVE - BEE_2B_MEM  # base bee model

    if available < 0:
        # Not enough for queen + bees — lite mode
        return {
            "mode": "lite",
            "queen_model": "2b",
            "bee_slots": MIN_BEES,
            "queen_mem": BEE_2B_MEM,
            "bee_mem": BEE_2B_MEM,
            "total_mem": total_mem_gb,
        }

    # Each additional bee slot needs KV cache memory
    bee_slots = int(available / PER_BEE_SLOT)
    bee_slots = max(MIN_BEES, min(bee_slots, MAX_BEES))

    return {
        "mode": "full",
        "queen_model": queen_model,
        "bee_slots": bee_slots,
        "queen_mem": queen_mem,
        "bee_mem": BEE_2B_MEM + bee_slots * PER_BEE_SLOT,
        "total_mem": total_mem_gb,
    }


def format_scaling_info(config: dict) -> str:
    """Human-readable scaling summary."""
    if config["mode"] == "lite":
        return (
            f"Lite mode: 2B model only, {config['bee_slots']} bee slot "
            f"({config['total_mem']:.0f}GB detected)"
        )
    return (
        f"Full mode: {config['queen_model'].upper()} queen + "
        f"{config['bee_slots']} bee slots "
        f"({config['total_mem']:.0f}GB detected, "
        f"{config['queen_mem']:.1f}GB queen + {config['bee_mem']:.1f}GB bees)"
    )


# Quick reference for README/docs
SCALING_TABLE = """
| Memory | Mode | Queen | Bees | Total models |
|--------|------|-------|------|-------------|
| 4GB    | Lite | 2B    | 1    | 2B only     |
| 8GB    | Full | 9B    | 1    | 9B + 2B     |
| 12GB   | Full | 9B    | 4    | 9B + 2B     |
| 16GB   | Full | 9B    | 8    | 9B + 2B     |
| 24GB   | Full | 9B    | 16   | 9B + 2B     |
| 32GB   | Full | 27B   | 4    | 27B + 2B    |
| 64GB   | Full | 27B   | 32   | 27B + 2B    |
| 128GB  | Full | 27B   | 32   | 27B + 2B    |
"""
