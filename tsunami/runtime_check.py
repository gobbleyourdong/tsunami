"""Proactive runtime-availability check (QA-3 Fire 99).

When a user prompt explicitly requires a runtime tsunami doesn't have
(Deno, Bun, Rust, PHP, Go, Ruby, Java...), the current behavior is
silent spec-drop: agent scaffolds the default react-app, runs `npm
install`, writes React code, and delivers — never mentioning the
runtime mismatch. Cosmetic compliance only.

This helper runs at agent.run() entry and returns a system-note string
to inject when an unsupported-or-missing runtime is requested. The note
tells the model to surface the limitation in its message_chat output
instead of silently substituting.

Pure function, shutil-only probe — no torch/httpx deps so it's test-fast.
"""

from __future__ import annotations

import re
import shutil


# Runtime keywords mapped to their CLI check-binary.
# Only trigger when the prompt clearly IS asking for that runtime —
# `\b(name)\b` near a usage hint. Avoid generic mentions ("Python script
# that generates HTML" is fine; "build with Deno" is a runtime request).
_RUNTIME_PROBES = {
    "deno": "deno",
    "bun": "bun",
    "rust": "cargo",
    "wasm": None,        # WASM is a target, no single binary probe
    "php": "php",
    "ruby": "ruby",
    "go": "go",
    "java": "java",
    "jekyll": "jekyll",
    "hugo": "hugo",
}

# Usage-intent signals — the runtime name must co-occur with at least
# one of these to count as a real request (not an incidental mention).
_USAGE_HINTS = (
    "use ", "using ", "with ", "via ", "require", "must use",
    "built with", "build with", "build using", "serve via",
    "runtime",
)


def detect_unsupported_runtime(user_message: str) -> str | None:
    """Return a system-note warning, or None if no unsupported runtime requested.

    Args:
        user_message: the user's turn text.

    Returns:
        None if: (a) no runtime keyword, or (b) keyword present without
        usage-hint co-occurrence, or (c) runtime IS available on PATH.
        Otherwise a short system-note explaining the mismatch.
    """
    if not user_message:
        return None
    msg = user_message.lower()

    # Fast path: if no usage-hint word appears, skip entirely.
    if not any(hint in msg for hint in _USAGE_HINTS):
        return None

    missing: list[str] = []
    for runtime, binary in _RUNTIME_PROBES.items():
        # Word-boundary match on the runtime name
        if not re.search(rf"\b{re.escape(runtime)}\b", msg):
            continue
        # Must co-occur with a usage hint in a reasonable distance
        # (same prompt). We already know at least one hint exists
        # because of the fast-path check above.
        if binary is None:
            # No binary probe possible (e.g. WASM) — treat as unsupported
            # unless the prompt also mentions a compiler that emits it.
            if "emscripten" in msg or "wasm-pack" in msg or "wasm-bindgen" in msg:
                continue
            missing.append(runtime)
            continue
        if shutil.which(binary) is None:
            missing.append(runtime)

    if not missing:
        return None

    names = ", ".join(missing)
    return (
        f"USER REQUESTED UNAVAILABLE RUNTIME ({names}). The requested "
        f"runtime is NOT installed on this sandbox. Do NOT silently "
        f"substitute React/Node. Before writing any code, use message_chat "
        f"to tell the user: '{names} is not available; I can build with "
        f"React+TypeScript+Vite instead, or you can install {names} first.' "
        f"Only proceed after the user responds."
    )
