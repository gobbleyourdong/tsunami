"""Outbound-exfiltration gate — stub.

Originally a security gate scanning content-about-to-be-written to disk
for prompt-injection-driven data exfiltration attempts (unicode-encoded
URLs that decode post-check, base64-wrapped credentials, out-of-scope
network-side-effect strings, etc.). The real implementation was never
committed. This stub returns None (no violation) so the filesystem tools
that expect the import continue to work.

Signature contract: `check_outbound_exfil(content, filename, task_prompt)
  -> str | None`. Return a non-empty error string to block the write,
None to allow.

If you need to harden this gate later, the call sites in
`tsunami/tools/filesystem.py` already route writes through it — wire up
real heuristics here and the tools pick it up without changes.
"""
from __future__ import annotations

from typing import Optional


def check_outbound_exfil(
    content: str,
    filename: str,
    task_prompt: str = "",
) -> Optional[str]:
    """No-op pass-through. Returns None = allow the write."""
    return None
