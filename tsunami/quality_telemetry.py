"""Per-delivery quality telemetry (sigma audit §17 quality-axis addendum).

Closes the gap the post-mortem surfaced: routing_telemetry + doctrine_history
answer "what did the router pick?" but NOT "did the delivery come out well?"
This module logs a rich per-deliverable row covering:

  - Loop density:   iter_count, retry_count, time_to_deliver_s,
                    tool_sequence_hash, tool_distribution
  - Artifact size:  App.tsx bytes/lines, build pass/fail counts
  - Aesthetic QA:   direction_set names fired + pass/fail verdicts,
                    vision_gate issues, optional screenshot pHash
  - Generation arc: generate_image_count (SURGE-style "11 turns of images
                    before a file_write" failure mode detection)
  - Cost:           tokens in/out, wall-clock (when available)

OPT-IN. Set TSUNAMI_QUALITY_TELEMETRY=1 or call enable() at process start.
Non-blocking — swallows I/O errors so telemetry never blocks delivery.

Output: ~/.tsunami/telemetry/deliverable_quality.jsonl — append-only,
one row per successful message_result. The morning consolidator (sigma
§17.6) reads this + routing.jsonl + doctrine_history.jsonl to produce
the refinement vs coverage split.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_PATH = Path.home() / ".tsunami" / "telemetry" / "deliverable_quality.jsonl"

_ENABLED_AT_RUNTIME = False


def enable(path: str | Path | None = None) -> None:
    global _ENABLED_AT_RUNTIME, _DEFAULT_PATH
    _ENABLED_AT_RUNTIME = True
    if path:
        _DEFAULT_PATH = Path(path)


def disable() -> None:
    global _ENABLED_AT_RUNTIME
    _ENABLED_AT_RUNTIME = False


def _enabled() -> bool:
    return _ENABLED_AT_RUNTIME or os.environ.get("TSUNAMI_QUALITY_TELEMETRY") == "1"


def _path() -> Path:
    override = os.environ.get("TSUNAMI_TELEMETRY_DIR")
    if override:
        return Path(override) / "deliverable_quality.jsonl"
    return _DEFAULT_PATH


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def tool_sequence_hash(tool_history: list[str]) -> str:
    """Stable 8-char hash over the sequence of tool calls. Two runs
    with identical arcs collide; different arcs don't. Used to detect
    repeat failure modes across runs."""
    blob = "|".join(tool_history or []).encode()
    return hashlib.sha256(blob).hexdigest()[:8]


def measure_app_tsx(project_dir: Path) -> dict:
    """Return (bytes, lines) for src/App.tsx if present; {} otherwise."""
    try:
        app = Path(project_dir) / "src" / "App.tsx"
        if app.is_file():
            body = app.read_text(errors="ignore")
            return {"bytes": len(body), "lines": body.count("\n") + 1}
    except Exception:
        pass
    return {}


def screenshot_phash(dist_html: Path) -> str:
    """Perceptual hash of the delivered dist/index.html's screenshot,
    IF the imagehash library is installed AND a screenshot can be
    taken. Returns "" on any failure — the caller treats empty as
    "skip this column."

    pHash lets us detect near-identical deliveries across runs — if
    every "pomodoro" scaffolds to a visually-identical screenshot,
    either the scaffold dominates or the wave isn't differentiating.
    """
    try:
        import imagehash  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError:
        return ""
    # Re-use the vision_gate screenshot helper if available
    try:
        from .vision_gate import _screenshot_html
        import asyncio
        png = asyncio.run(_screenshot_html(dist_html))
        if not png:
            return ""
        import io
        img = Image.open(io.BytesIO(png))
        return str(imagehash.phash(img))
    except Exception:
        return ""


def parse_direction_set_verdict(vlm_raw: str) -> dict:
    """Extract a compact verdict from a vision_gate raw response.

    The art_direction / web_polish / bug_finding rubrics expect
    PASS/FAIL outputs. This parser is forgiving — it looks for:
      - "PASS" / "FAIL" token
      - "X/10" score pattern
      - any q1..q10 "no" listings
    Returns {passed: bool, score: str, flagged: [q#, ...]}.
    Missing signal returns {passed: None}.
    """
    if not vlm_raw:
        return {"passed": None}
    import re
    passed: bool | None = None
    upper = vlm_raw.upper()
    if "FAIL" in upper and "PASS" not in upper:
        passed = False
    elif "PASS" in upper and "FAIL" not in upper:
        passed = True
    score_m = re.search(r"\b(\d+)\s*/\s*10\b", vlm_raw)
    score = score_m.group(0) if score_m else ""
    flagged = re.findall(r"\bq(\d+)\b.*?\b(?:no|fail)", vlm_raw.lower())
    return {"passed": passed, "score": score, "flagged_questions": flagged[:10]}


def log_delivery(
    *,
    run_id: str = "",
    project_dir: Path | str = "",
    prompt: str = "",
    scaffold: str = "",
    style: str = "",
    genre: str = "",
    content_essence: str = "",
    tool_history: list[str] | None = None,
    iter_count: int | None = None,
    retry_count: int | None = None,
    time_to_deliver_s: float | None = None,
    build_pass_count: int | None = None,
    build_fail_count: int | None = None,
    vision_pass: bool | None = None,
    vision_issues: str = "",
    direction_set: str = "",
    direction_set_raw: str = "",
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    phash: bool = False,
    extra: dict | None = None,
) -> None:
    """Append one delivery row. Non-blocking. No-op unless enabled.

    Only project_dir, tool_history are structurally required to be
    useful; the rest are optional. The caller should pass what it has
    and leave the rest empty — the aggregator tolerates missing fields.

    `phash=True` attempts a perceptual hash of the delivered screenshot
    (requires imagehash + PIL). Default False because the first
    delivery often doesn't have a live renderer.
    """
    if not _enabled():
        return
    try:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        th = list(tool_history or [])
        tc = Counter(th)
        pdir = Path(project_dir) if project_dir else None

        # Derive a run_id from prompt + timestamp if caller didn't set one.
        if not run_id:
            rh = hashlib.sha256((prompt + _iso_now()).encode()).hexdigest()[:10]
            run_id = f"auto-{rh}"

        app_stats = measure_app_tsx(pdir) if pdir else {}

        phash_str = ""
        if phash and pdir:
            dist_html = pdir / "dist" / "index.html"
            if dist_html.is_file():
                phash_str = screenshot_phash(dist_html)

        direction_verdict = (
            parse_direction_set_verdict(direction_set_raw)
            if direction_set_raw else {"passed": None}
        )

        row = {
            "ts": _iso_now(),
            "run_id": run_id,
            "project_dir": str(pdir) if pdir else "",
            "prompt": prompt[:300],
            "prompt_hash": hashlib.sha256(
                (prompt or "").strip().lower().encode()
            ).hexdigest()[:12],

            # Directives / routing snapshot
            "scaffold": scaffold,
            "style": style,
            "genre": genre,
            "content_essence": content_essence,

            # Loop density
            "iter_count": iter_count,
            "retry_count": retry_count,
            "time_to_deliver_s": time_to_deliver_s,
            "tool_sequence_hash": tool_sequence_hash(th),
            "tool_distribution": dict(tc),
            "tool_count": len(th),
            "generate_image_count": tc.get("generate_image", 0),
            "file_write_count": tc.get("file_write", 0),
            "file_edit_count": tc.get("file_edit", 0),
            "shell_exec_count": tc.get("shell_exec", 0),

            # Artifact size
            "app_tsx_bytes": app_stats.get("bytes"),
            "app_tsx_lines": app_stats.get("lines"),

            # Build health
            "build_pass_count": build_pass_count,
            "build_fail_count": build_fail_count,

            # Aesthetic QA
            "vision_pass": vision_pass,
            "vision_issues": (vision_issues or "")[:500],
            "direction_set": direction_set,
            "direction_verdict": direction_verdict,
            "screenshot_phash": phash_str,

            # Cost
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }
        if extra:
            row["extra"] = extra

        with path.open("a") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        # Never block delivery on telemetry failure.
        pass


def _iter_rows(path: Path | None = None):
    p = path or _path()
    if not p.is_file():
        return
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def quality_report(path: Path | None = None) -> dict:
    """Aggregate the quality log into a morning-report-shaped summary.

    Sections:
      - delivery_health:       n_delivered, build pass rate, vision pass rate
      - loop_density:          median iter_count, median time_to_deliver,
                               top tool_sequence_hashes (repeat failure modes)
      - artifact_spread:       app_tsx_bytes percentiles
      - aesthetic_spread:      per direction_set pass rate
      - generation_arc:        median generate_image_count,
                               n_runs_with_image_heavy_arcs (>=4 images before first file_write)
      - screenshot_clusters:   phash collisions (identical-looking deliveries)
    """
    rows = list(_iter_rows(path))
    out: dict = {"total_deliveries": len(rows)}
    if not rows:
        return out

    import statistics
    n = len(rows)
    build_ok = sum(1 for r in rows if (r.get("build_pass_count") or 0) > 0
                                   and (r.get("build_fail_count") or 0) == 0)
    vision_ok = sum(1 for r in rows if r.get("vision_pass") is True)
    out["delivery_health"] = {
        "build_pass_rate": build_ok / n,
        "vision_pass_rate": vision_ok / n,
    }

    iters = [r["iter_count"] for r in rows if r.get("iter_count")]
    times = [r["time_to_deliver_s"] for r in rows if r.get("time_to_deliver_s")]
    out["loop_density"] = {
        "median_iter_count": statistics.median(iters) if iters else None,
        "median_time_to_deliver_s": statistics.median(times) if times else None,
        "top_tool_seq_hashes": Counter(
            r.get("tool_sequence_hash") for r in rows
        ).most_common(5),
    }

    sizes = [r["app_tsx_bytes"] for r in rows if r.get("app_tsx_bytes")]
    if sizes:
        sizes.sort()
        out["artifact_spread"] = {
            "p50_bytes": sizes[len(sizes)//2],
            "p90_bytes": sizes[int(len(sizes)*0.9)],
            "max_bytes": sizes[-1],
            "count": len(sizes),
        }

    per_rubric = {}
    for r in rows:
        ds = r.get("direction_set")
        v = r.get("direction_verdict") or {}
        p = v.get("passed")
        if not ds or p is None:
            continue
        cell = per_rubric.setdefault(ds, {"pass": 0, "fail": 0})
        cell["pass" if p else "fail"] += 1
    out["aesthetic_spread"] = per_rubric

    img_counts = [r.get("generate_image_count", 0) for r in rows]
    image_heavy = sum(1 for c in img_counts if c >= 4)
    out["generation_arc"] = {
        "median_generate_image_count": statistics.median(img_counts) if img_counts else None,
        "image_heavy_runs": image_heavy,
        "image_heavy_rate": image_heavy / n if n else 0.0,
    }

    phashes = [r.get("screenshot_phash") for r in rows if r.get("screenshot_phash")]
    if phashes:
        dupe = Counter(phashes).most_common(3)
        out["screenshot_clusters"] = {
            "total_with_phash": len(phashes),
            "top_collisions": dupe,
        }

    return out


__all__ = [
    "enable", "disable",
    "log_delivery", "quality_report",
    "tool_sequence_hash", "parse_direction_set_verdict",
]
