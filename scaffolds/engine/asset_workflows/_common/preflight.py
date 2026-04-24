"""Pre-flight: verify ERNIE + Qwen-Image-Edit are up + ready.

Run this ONCE before firing a big batch. Checks:
  - ERNIE /healthz reachable + model_kind + VRAM
  - Qwen-Image-Edit /healthz reachable + model + LoRA
  - Output directory writable
  - Disk space (warns at <5 GB free)
  - Python requests library available

Exit codes:
  0 — everything ready
  1 — any check failed; details printed

Usage:
    python3 scaffolds/engine/asset_workflows/_common/preflight.py
    ERNIE_URL=http://host:8092 python3 preflight.py
    python3 preflight.py --out ./my-out-dir
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ERNIE_URL = os.environ.get("ERNIE_URL", "http://localhost:8092")
QWEN_EDIT_URL = os.environ.get("QWEN_EDIT_URL", "http://localhost:8094")


def _check_requests() -> tuple[bool, str]:
    try:
        import requests  # noqa: F401
        return True, "requests OK"
    except ImportError:
        return False, "requests not installed — pip install requests"


def _check_ernie() -> tuple[bool, str]:
    try:
        import requests
    except ImportError:
        return False, "requests not installed"
    try:
        r = requests.get(f"{ERNIE_URL}/healthz", timeout=5)
        r.raise_for_status()
        data = r.json()
        model_kind = data.get("loaded_kind") or data.get("model_kind") or "unknown"
        vram = data.get("vram_gb") or data.get("resident_vram_gb") or data.get("peak_vram_gb") or "?"
        return True, f"ERNIE OK: kind={model_kind}, vram={vram}"
    except requests.exceptions.ConnectionError:
        return False, f"ERNIE unreachable at {ERNIE_URL}"
    except Exception as e:
        return False, f"ERNIE healthz error: {e}"


def _check_qwen_edit() -> tuple[bool, str]:
    try:
        import requests
    except ImportError:
        return False, "requests not installed"
    try:
        r = requests.get(f"{QWEN_EDIT_URL}/healthz", timeout=5)
        r.raise_for_status()
        data = r.json()
        model = data.get("loaded_model") or "unknown"
        loras = data.get("loaded_loras") or []
        vram = data.get("vram_gb") or "?"
        return True, f"Qwen-Image-Edit OK: model={model.split('/')[-1]}, loras={loras}, vram={vram}"
    except Exception:
        try:
            # Some builds don't have healthz — ping /v1/models
            r = requests.get(f"{QWEN_EDIT_URL}/v1/models", timeout=5)
            if r.ok:
                return True, f"Qwen-Image-Edit reachable at {QWEN_EDIT_URL} (no /healthz)"
        except Exception:
            pass
        return False, f"Qwen-Image-Edit unreachable at {QWEN_EDIT_URL}"


def _check_out_dir(out_dir: Path) -> tuple[bool, str]:
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        probe = out_dir / ".preflight_write_probe"
        probe.write_text("ok")
        probe.unlink()
        return True, f"out dir writable: {out_dir}"
    except Exception as e:
        return False, f"out dir {out_dir} not writable: {e}"


def _check_disk(out_dir: Path) -> tuple[bool, str]:
    try:
        total, used, free = shutil.disk_usage(out_dir if out_dir.exists() else out_dir.parent)
        free_gb = free / (1024**3)
        status = free_gb > 5
        msg = f"disk free: {free_gb:.1f} GB"
        if not status:
            msg += "  ⚠️  LOW — large runs may fill the disk"
        return status, msg
    except Exception as e:
        return False, f"disk check failed: {e}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("./out"),
                    help="output directory to probe (default ./out)")
    args = ap.parse_args()

    checks = [
        ("requests library", _check_requests()),
        ("ERNIE server",     _check_ernie()),
        ("Qwen-Image-Edit",  _check_qwen_edit()),
        ("output dir",       _check_out_dir(args.out)),
        ("disk space",       _check_disk(args.out)),
    ]

    print(f"=== pre-flight check ===")
    all_ok = True
    for name, (ok, msg) in checks:
        marker = "✅" if ok else "❌"
        print(f"  {marker} {name:20s} {msg}")
        if not ok:
            all_ok = False

    print(f"\n{'READY TO FIRE' if all_ok else 'NOT READY — fix the ❌ items above'}")
    if not all_ok:
        print("\nCommon fixes:")
        print("  ERNIE:            python -m tsunami.serving.ernie_server --model Turbo --port 8092")
        print("  Qwen-Image-Edit:  python -m tsunami.serving.qwen_image_server --port 8094 --lora multiple_angles")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
