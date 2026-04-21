"""Unit tests for scripts/asset/pixelize_sheet.py.

Covers the pure path: given a synthetic bake dir (sheet.png + metadata.json
built on the fly via PIL), running pixelize_sheet produces the right
output dimensions, right per-cell geometry in the derived metadata,
and preserves row-level provenance (kind, primitive, Σstrength).

No server dependency — all state is built from scratch in tmp_path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from PIL import Image


_REPO = Path(__file__).resolve().parent.parent.parent
_PIXELIZE_PATH = _REPO / "scripts" / "asset" / "pixelize_sheet.py"


def _load_pixelize_module():
    """Load scripts/asset/pixelize_sheet.py as a module. scripts/asset/
    isn't a python package (by design — it's CLI-first), so importlib
    loads the file directly."""
    spec = importlib.util.spec_from_file_location("pixelize_sheet", _PIXELIZE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pixelize_sheet"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def pixelize():
    return _load_pixelize_module()


@pytest.fixture
def bake_dir(tmp_path: Path) -> Path:
    """Build a minimal-but-realistic bake dir: 2 rows × 3 cols of 64px
    cells. Each cell is a distinct solid color so per-cell composition
    is verifiable. Metadata matches the shape the real bake tool emits,
    including kind / primitive / total_strength / per-cell delta."""
    frame_size = 64
    cols, rows = 3, 2
    sheet = Image.new("RGBA", (cols * frame_size, rows * frame_size), (0, 0, 0, 0))
    row_colors = [
        [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)],
        [(255, 255, 0, 255), (0, 255, 255, 255), (255, 0, 255, 255)],
    ]
    for r in range(rows):
        for c in range(cols):
            cell = Image.new("RGBA", (frame_size, frame_size), row_colors[r][c])
            sheet.paste(cell, (c * frame_size, r * frame_size))
    sheet.save(tmp_path / "sheet.png")

    meta = {
        "entity": "test_entity",
        "base": "synthetic",
        "frame_size": {"w": frame_size, "h": frame_size},
        "rows": [
            {
                "row_index": 0, "name": "a->b", "kind": "transition",
                "from_state": "a", "to_state": "b", "primitive": "demo",
                "frame_count": 3,
                "cells": [
                    {"col_index": c, "x": c * frame_size, "y": 0,
                     "w": frame_size, "h": frame_size,
                     "delta": f"delta-{c}", "strength": 0.3}
                    for c in range(3)
                ],
                "total_strength": 0.9,
            },
            {
                "row_index": 1, "name": "loop_x", "kind": "loop",
                "from_state": "x", "to_state": "x", "primitive": "loop_demo",
                "frame_count": 3,
                "cells": [
                    {"col_index": c, "x": c * frame_size, "y": frame_size,
                     "w": frame_size, "h": frame_size,
                     "delta": f"wiggle-{c}", "strength": 0.25}
                    for c in range(3)
                ],
                "total_strength": 0.75,
            },
        ],
        "generated_at": 0,
        "pixelization": "none — canonical full-res; quantize as a separate pass",
    }
    (tmp_path / "metadata.json").write_text(json.dumps(meta, indent=2))
    return tmp_path


def test_pixelize_produces_expected_dimensions(pixelize, bake_dir: Path):
    sheet_path, meta_path = pixelize.pixelize_sheet(bake_dir, target_size=16)
    out = Image.open(sheet_path)
    # 3 cols × 16 px, 2 rows × 16 px.
    assert out.size == (48, 32)


def test_pixelize_writes_sized_metadata_file(pixelize, bake_dir: Path):
    _, meta_path = pixelize.pixelize_sheet(bake_dir, target_size=16)
    assert meta_path.name == "metadata_16.json"
    meta = json.loads(meta_path.read_text())
    assert meta["frame_size"] == {"w": 16, "h": 16}
    assert "pixelized 64→16 via lanczos" in meta["pixelization"]
    assert meta["source_sheet"] == "sheet.png"


def test_pixelize_preserves_row_provenance(pixelize, bake_dir: Path):
    _, meta_path = pixelize.pixelize_sheet(bake_dir, target_size=16)
    meta = json.loads(meta_path.read_text())
    # The downstream consumer must still see which animation produced
    # which row. Only geometry changes; kind / primitive / total_strength
    # must survive intact.
    assert meta["rows"][0]["kind"] == "transition"
    assert meta["rows"][0]["primitive"] == "demo"
    assert meta["rows"][0]["total_strength"] == 0.9
    assert meta["rows"][1]["kind"] == "loop"
    assert meta["rows"][1]["primitive"] == "loop_demo"
    assert meta["rows"][1]["total_strength"] == 0.75


def test_pixelize_rewrites_per_cell_geometry(pixelize, bake_dir: Path):
    _, meta_path = pixelize.pixelize_sheet(bake_dir, target_size=16)
    meta = json.loads(meta_path.read_text())
    # Row 0 cells at y=0, row 1 cells at y=16. Each cell 16 wide.
    r0_cells = meta["rows"][0]["cells"]
    assert [c["x"] for c in r0_cells] == [0, 16, 32]
    assert all(c["y"] == 0 and c["w"] == 16 and c["h"] == 16 for c in r0_cells)
    r1_cells = meta["rows"][1]["cells"]
    assert [c["x"] for c in r1_cells] == [0, 16, 32]
    assert all(c["y"] == 16 for c in r1_cells)
    # Delta/strength must round-trip unchanged — pixelization must never
    # silently lose semantic info about what each frame represents.
    assert [c["delta"] for c in r0_cells] == ["delta-0", "delta-1", "delta-2"]
    assert all(c["strength"] == 0.3 for c in r0_cells)


def test_pixelize_rejects_bad_filter(pixelize, bake_dir: Path):
    with pytest.raises(ValueError, match="unknown filter"):
        pixelize.pixelize_sheet(bake_dir, target_size=16, filter_name="bogus")


def test_pixelize_nearest_vs_lanczos_differ(pixelize, bake_dir: Path):
    """Different filters must produce different pixels — otherwise the
    --filter flag is a lie."""
    # Build a sheet with a gradient inside each cell so the filter
    # choice is forced to matter (flat colors would collapse to the
    # same RGB under any filter).
    frame_size = 64
    cols, rows = 3, 2
    sheet = Image.new("RGBA", (cols * frame_size, rows * frame_size), (0, 0, 0, 0))
    for r in range(rows):
        for c in range(cols):
            cell = Image.new("RGBA", (frame_size, frame_size))
            pixels = cell.load()
            for y in range(frame_size):
                for x in range(frame_size):
                    pixels[x, y] = ((x * 4) % 256, (y * 4) % 256,
                                    ((x + y) * 2) % 256, 255)
            sheet.paste(cell, (c * frame_size, r * frame_size))
    sheet.save(bake_dir / "sheet.png")

    # Both filters write to the same sheet_16.png path, so snapshot bytes
    # between runs rather than keeping both Image handles open.
    pixelize.pixelize_sheet(bake_dir, 16, "lanczos")
    lanczos_bytes = Image.open(bake_dir / "sheet_16.png").tobytes()
    pixelize.pixelize_sheet(bake_dir, 16, "nearest")
    nearest_bytes = Image.open(bake_dir / "sheet_16.png").tobytes()
    assert lanczos_bytes != nearest_bytes, \
        "lanczos and nearest must produce different pixels"


def test_pixelize_rejects_missing_sheet(pixelize, tmp_path: Path):
    (tmp_path / "metadata.json").write_text("{}")
    with pytest.raises(FileNotFoundError):
        pixelize.pixelize_sheet(tmp_path, 16)


def test_pixelize_rejects_missing_metadata(pixelize, tmp_path: Path):
    Image.new("RGBA", (16, 16)).save(tmp_path / "sheet.png")
    with pytest.raises(FileNotFoundError):
        pixelize.pixelize_sheet(tmp_path, 16)
