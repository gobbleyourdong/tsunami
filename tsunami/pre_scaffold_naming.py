"""Project-name derivation from a build prompt.

Extracted from `Agent._pre_scaffold` for independent testing. The
derivation order is:

  1. Explicit `save=<path>` hint (caller supplies the slug — we trust it)
  2. "called / named / titled <Name>" — 1-4 leading-Capital tokens
  3. Fallback: strip build verb + article + 2d/3d prefix, take the
     first 4 words up to the next dash/em-dash/colon/comma/period

Slot 2's regex is load-bearing and historically fragile. Two live
failures motivated the current form:

  - "Build a 2D platformer called Lava Leap" — the capture MUST
    stop at word boundaries, not swallow "3 levels" if the caller
    adds parameter detail after an em-dash.
  - "Build a 2D platformer called X — 3 levels" — single-token
    names must still land; the em-dash must not break the regex
    or the capture group.

See `tsunami/tests/test_replay_pre_scaffold_name_extraction.py` for
the full corpus of prompts this helper must handle.
"""

from __future__ import annotations

import re

_BUILD_VERB_PREFIX = re.compile(
    r"^(build|create|make|develop|design)\s+(a|an|the)?\s*",
    re.IGNORECASE,
)
_DIM_PREFIX = re.compile(r"^(2d|3d)\s+", re.IGNORECASE)
_STOP_CHARS = re.compile(r"[—–\-:,.!?]")
_CALLED_PATTERN = re.compile(
    r"(?:called|named|titled)\s+"
    r"([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})",
)
_NOISE_WORDS: frozenset[str] = frozenset({
    "called", "named", "titled", "a", "the", "an",
})
_SANITIZE_RE = re.compile(r"[^a-z0-9_-]")
_MAX_SLUG_LEN = 40


def derive_project_name(user_message: str, save_hint: str | None = None) -> str:
    """Turn a build prompt into a URL-safe project slug.

    `user_message` is the raw prompt (mixed case — the "called X"
    regex depends on leading-Capital detection). `save_hint`, if
    provided, short-circuits the derivation: that slug is returned
    verbatim (the caller already resolved the name).

    Returns a lowercased, hyphen-separated slug up to 40 chars;
    returns "game" as a fallback when no signal could be extracted.

    Designed to be idempotent: `derive_project_name(derive_project_name(x))`
    returns the same value modulo the trailing sanitize pass.
    """
    if save_hint:
        return save_hint

    if not user_message:
        return "game"

    called = _CALLED_PATTERN.search(user_message)
    if called:
        raw = called.group(1).strip()
        project_name = "-".join(raw.lower().split())[:_MAX_SLUG_LEN]
    else:
        msg = user_message.lower().strip()
        stripped = _BUILD_VERB_PREFIX.sub("", msg).strip()
        stripped = _DIM_PREFIX.sub("", stripped).strip()
        stripped = _STOP_CHARS.split(stripped, maxsplit=1)[0]
        words = stripped.split()[:4]
        words = [w for w in words if w not in _NOISE_WORDS]
        project_name = (
            "-".join(words).replace(",", "").replace(".", "")[:_MAX_SLUG_LEN]
        )

    project_name = _SANITIZE_RE.sub("", project_name) or "game"
    return project_name
