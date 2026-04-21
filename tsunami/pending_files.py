"""FIX-A pending-file checklist — scaffold-first gamedev drone aid.

Parses the user's task prompt for ``data/*.json`` filename mentions and
cross-checks them against files actually present in the provisioned
scaffold's ``data/`` dir. Feeds a per-iter system-note that reminds
the drone which files still need a ``file_write``, preventing the
read-after-write cascade (JOB-INT-4 RC-1).

Scope: gamedev scaffold-first only. Pure regex parsing — no LLM calls.
"""
from __future__ import annotations

import re
from pathlib import Path


_DATA_JSON_RE = re.compile(r"\bdata/([\w.-]+\.json)\b", re.IGNORECASE)


def decompose_pending_files(
    user_message: str,
    project_data_dir: Path,
) -> tuple[list[str], list[str]]:
    """Return ``(pending_existing, mentioned_but_missing)``.

    ``pending_existing`` are filenames the user named that exist in the
    scaffold's ``data/`` dir (ordered by first mention, deduped,
    lowercased). ``mentioned_but_missing`` are filenames the user named
    that do NOT exist — typos or new-file requests.

    Empty lists for empty message or missing scaffold.
    """
    if not user_message or not project_data_dir.is_dir():
        return [], []

    seen: set[str] = set()
    mentioned_ordered: list[str] = []
    for m in _DATA_JSON_RE.finditer(user_message):
        name = m.group(1).lower()
        if name not in seen:
            seen.add(name)
            mentioned_ordered.append(name)

    existing_names = {p.name.lower() for p in project_data_dir.glob("*.json")}
    pending = [n for n in mentioned_ordered if n in existing_names]
    missing = [n for n in mentioned_ordered if n not in existing_names]
    return pending, missing


def format_iter1_checklist(pending: list[str], missing: list[str]) -> str:
    """Long-form checklist injected at iter-1 with scaffold-first discipline."""
    lines = ["## Task checklist (scaffold-first gamedev build)", ""]
    lines.append("User asked to customize these data files (in order):")
    for f in pending:
        lines.append(f"  [ ] data/{f}")
    lines.extend([
        "",
        "Scaffold-first discipline:",
        "1. Write each file in order via file_write. You MAY file_read a file",
        "   ONCE to see its current shape, but most scaffold data files are",
        "   pre-populated with schema-valid seed data you can customize in-",
        "   place without reading.",
        "2. After writing ALL pending files, run a build-check.",
        "3. Do NOT enter a read-loop. If uncertain what to write, base your",
        "   write on the pending-list item name + the user's prompt text +",
        "   (optionally) one file_read. Do NOT re-read a file you already",
        "   wrote.",
    ])
    if missing:
        lines.extend(_missing_warning_block(missing))
    return "\n".join(lines)


def format_checklist_update(
    pending: list[str],
    written: list[str],
    missing: list[str],
) -> str:
    """Per-iter reminder after a write lands. Returns empty string when
    there's nothing left to do (caller suppresses the note)."""
    remaining = [p for p in pending if p not in written]
    if not remaining:
        return ""
    lines = ["## Pending file-edit checklist", "", "Still pending (in order):"]
    for f in remaining:
        lines.append(f"  [ ] data/{f}")
    if written:
        lines.extend(["", "Already written (done):"])
        for f in written:
            lines.append(f"  [x] data/{f}")
    lines.extend([
        "",
        "Your next action should be a file_write on the FIRST unchecked file.",
        "Do NOT re-read files you've already written. Do NOT file_read a",
        "pending file more than once per write-cycle — you've already seen",
        "its shape. After ALL files are checked, run a build-check, then",
        "deliver via message_result.",
    ])
    if missing:
        lines.extend(_missing_warning_block(missing))
    return "\n".join(lines)


def _missing_warning_block(missing: list[str]) -> list[str]:
    out = ["", "WARN: User mentioned these files, but they do NOT exist in"
                " this scaffold:"]
    for f in missing:
        out.append(f"  ! data/{f}  (typo or new-file request)")
    out.extend([
        "  If create: write it anyway — the scaffold compiler accepts new",
        "  JSON if valid. If typo: skip and advance the pending list.",
    ])
    return out
