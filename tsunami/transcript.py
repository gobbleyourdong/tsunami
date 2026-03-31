"""Session transcript storage — JSONL-based persistence with lazy loading.

Stores conversation history as JSONL (one JSON object per line).
Supports batched writes, metadata entries, and resume from any point.

Key patterns:
- JSONL format: append-only, crash-safe (partial writes lose at most one line)
- Metadata entries (tags, titles, PR links) interleaved with messages
- Lazy loading for large transcripts (read from compact boundary)
- Resume by finding the last leaf message
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("tsunami.transcript")

# Write batching
FLUSH_INTERVAL_MS = 100
MAX_CHUNK_BYTES = 100 * 1024 * 1024  # 100 MB


@dataclass
class TranscriptEntry:
    """A single entry in the transcript JSONL."""
    type: str  # "message", "metadata", "compact_boundary", "custom_title"
    uuid: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    session_id: str = ""
    timestamp: float = field(default_factory=time.time)
    data: dict = field(default_factory=dict)


def write_transcript(entries: list[TranscriptEntry], path: str | Path):
    """Append entries to a transcript JSONL file.

    Batched write — all entries in a single file append for crash safety.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    for entry in entries:
        record = {
            "type": entry.type,
            "uuid": entry.uuid,
            "session_id": entry.session_id,
            "timestamp": entry.timestamp,
            **entry.data,
        }
        lines.append(json.dumps(record, separators=(",", ":")))

    with open(p, "a") as f:
        f.write("\n".join(lines) + "\n")


def read_transcript(path: str | Path, after_boundary: bool = True) -> list[dict]:
    """Read entries from a transcript JSONL file.

    If after_boundary=True, only returns entries after the last compact boundary.
    This is the lazy loading pattern  for large transcripts.
    """
    p = Path(path)
    if not p.exists():
        return []

    try:
        text = p.read_text()
    except OSError:
        return []

    entries = []
    boundary_idx = -1

    lines = text.strip().split("\n")
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            entries.append(entry)
            if entry.get("type") == "compact_boundary":
                boundary_idx = len(entries) - 1
        except json.JSONDecodeError:
            continue  # Skip malformed lines

    # Lazy load: only return post-boundary entries
    if after_boundary and boundary_idx >= 0:
        return entries[boundary_idx:]

    return entries


def find_leaf_messages(entries: list[dict]) -> list[dict]:
    """Find conversation leaf messages for resume.

    only user and assistant messages are leaves.
    Follow parent_uuid chains to find the latest branch tip.
    """
    # Build parent→children map
    children: dict[str, list[str]] = {}
    by_uuid: dict[str, dict] = {}
    message_types = {"message", "user", "assistant"}

    for entry in entries:
        if entry.get("type") not in message_types:
            continue
        uid = entry.get("uuid", "")
        parent = entry.get("parent_uuid", "")
        by_uuid[uid] = entry
        if parent:
            children.setdefault(parent, []).append(uid)

    # Leaves = messages with no children
    leaves = []
    for uid, entry in by_uuid.items():
        if uid not in children:
            leaves.append(entry)

    return leaves


def write_compact_boundary(path: str | Path, session_id: str, summary: str = ""):
    """Write a compact boundary marker.

    After this marker, only subsequent entries are loaded on resume.
    """
    entry = TranscriptEntry(
        type="compact_boundary",
        session_id=session_id,
        data={"summary": summary},
    )
    write_transcript([entry], path)


def write_metadata(path: str | Path, session_id: str,
                    key: str, value: Any):
    """Write a metadata entry (tag, title, PR link, etc.)."""
    entry = TranscriptEntry(
        type="metadata",
        session_id=session_id,
        data={"key": key, "value": value},
    )
    write_transcript([entry], path)


def message_to_entry(role: str, content: str, session_id: str,
                      tool_call: dict | None = None,
                      parent_uuid: str = "") -> TranscriptEntry:
    """Convert a conversation message to a transcript entry."""
    data = {
        "role": role,
        "content": content,
    }
    if tool_call:
        data["tool_call"] = tool_call
    if parent_uuid:
        data["parent_uuid"] = parent_uuid
    return TranscriptEntry(type="message", session_id=session_id, data=data)


def get_transcript_stats(path: str | Path) -> dict:
    """Get stats about a transcript file without loading all entries."""
    p = Path(path)
    if not p.exists():
        return {"exists": False}

    size = p.stat().st_size
    # Count lines without loading full content
    line_count = 0
    with open(p) as f:
        for _ in f:
            line_count += 1

    return {
        "exists": True,
        "size_bytes": size,
        "entries": line_count,
        "size_mb": round(size / (1024 * 1024), 2),
    }
