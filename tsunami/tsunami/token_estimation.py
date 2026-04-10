"""File-type-aware token estimation.

Different content types have different bytes-per-token ratios:
- JSON: ~2 bytes/token (single-char tokens like {, }, :, ,)
- Code: ~4 bytes/token (typical for most languages)
- Images: ~2000 tokens flat estimate
- Tool calls: name + serialized args

This replaces the naive chars/4 estimate with content-aware counting.
"""

from __future__ import annotations

import json
import os

# Bytes-per-token ratios by file extension 
BYTES_PER_TOKEN = {
    # JSON is much denser — lots of single-char tokens
    ".json": 2,
    ".jsonl": 2,
    ".jsonc": 2,
    # XML/HTML also dense
    ".xml": 2.5,
    ".html": 2.5,
    ".svg": 2.5,
    # Minified CSS/JS
    ".min.js": 2,
    ".min.css": 2,
    # Default for code and text
    "default": 4,
}

# Flat token estimates for non-text content
IMAGE_TOKEN_ESTIMATE = 2000
DOCUMENT_TOKEN_ESTIMATE = 2000


def bytes_per_token_for_ext(ext: str) -> float:
    """Get bytes-per-token ratio for a file extension."""
    ext_lower = ext.lower()
    if not ext_lower.startswith("."):
        ext_lower = "." + ext_lower
    return BYTES_PER_TOKEN.get(ext_lower, BYTES_PER_TOKEN["default"])


def estimate_tokens_for_text(text: str, ext: str = "") -> int:
    """Estimate token count for text content with file-type awareness."""
    bpt = bytes_per_token_for_ext(ext)
    return max(1, len(text.encode("utf-8")) // int(bpt))


def estimate_tokens_for_file(path: str) -> int:
    """Estimate token count for a file on disk."""
    ext = os.path.splitext(path)[1]
    try:
        size = os.path.getsize(path)
    except OSError:
        return 0
    bpt = bytes_per_token_for_ext(ext)
    return max(1, size // int(bpt))


def estimate_tokens_for_message(role: str, content: str,
                                 tool_call: dict | None = None) -> int:
    """Estimate tokens for a single conversation message.

    
    """
    tokens = 0

    # Message content
    tokens += len(content) // 4  # default ratio

    # Tool call overhead
    if tool_call:
        func = tool_call.get("function", tool_call)
        name = func.get("name", "")
        args = func.get("arguments", {})
        # Tool name + serialized args
        tokens += len(name) // 4
        if isinstance(args, dict):
            args_str = json.dumps(args)
            # Tool args are often JSON-like, use JSON ratio
            tokens += len(args_str) // 2
        elif isinstance(args, str):
            tokens += len(args) // 2

    # Role token overhead (~4 tokens per message for role markers)
    tokens += 4

    return max(1, tokens)


def estimate_tokens_for_conversation(messages: list[dict]) -> int:
    """Estimate total tokens for a conversation.

    More accurate than sum(len(content)) // 4 because it accounts
    for tool calls (JSON-dense) and message overhead.
    """
    total = 0
    for m in messages:
        total += estimate_tokens_for_message(
            m.get("role", ""),
            m.get("content", ""),
            m.get("tool_call"),
        )
    return total
