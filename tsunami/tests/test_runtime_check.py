"""QA-3 Fire 99: proactive runtime-availability check.

Agent was silently dropping `"use Deno"` / `"use Bun"` / `"must use PHP"`
requirements and scaffolding the default react-app. This gate injects a
system note telling the model to surface the mismatch via message_chat
instead of silently substituting.
"""

from __future__ import annotations

from unittest.mock import patch

from tsunami.runtime_check import detect_unsupported_runtime


def _fake_which_none(_bin):
    return None


def _fake_which_installed(_bin):
    return f"/usr/local/bin/{_bin}"


def test_empty_message_returns_none():
    assert detect_unsupported_runtime("") is None


def test_no_runtime_keyword_returns_none():
    assert detect_unsupported_runtime("build me a counter app") is None


def test_runtime_keyword_without_usage_hint_returns_none():
    """`"rust is hard"` or `"I like Go"` alone — no build intent, no warning."""
    assert detect_unsupported_runtime("rust is a hard language") is None
    assert detect_unsupported_runtime("I like Go") is None


def test_deno_request_with_usage_hint_warns():
    """Fire 99 exact repro: `"use Deno runtime (NOT Node)"` must warn."""
    with patch("shutil.which", _fake_which_none):
        note = detect_unsupported_runtime("Build a counter using Deno runtime (NOT Node)")
    assert note is not None
    assert "deno" in note.lower()
    assert "NOT installed" in note
    assert "message_chat" in note


def test_bun_with_build_hint_warns():
    with patch("shutil.which", _fake_which_none):
        note = detect_unsupported_runtime("build with bun, not npm")
    assert note is not None
    assert "bun" in note.lower()


def test_rust_cargo_requested_warns():
    with patch("shutil.which", _fake_which_none):
        note = detect_unsupported_runtime("use Rust with cargo")
    assert note is not None
    assert "rust" in note.lower()


def test_installed_runtime_does_not_warn():
    """If the binary IS on PATH, no warning — deno/bun happen to be there."""
    with patch("shutil.which", _fake_which_installed):
        assert detect_unsupported_runtime("use Deno to build a counter") is None


def test_multiple_unavailable_runtimes_all_listed():
    """Prompt asks for both Deno AND Bun — both should appear in the note."""
    with patch("shutil.which", _fake_which_none):
        note = detect_unsupported_runtime("use Deno and bun together to build")
    assert note is not None
    assert "deno" in note.lower()
    assert "bun" in note.lower()


def test_wasm_without_emscripten_warns():
    """WASM has no single binary probe — treat as unsupported unless the prompt
    mentions a toolchain (emscripten/wasm-pack/wasm-bindgen)."""
    with patch("shutil.which", _fake_which_none):
        assert detect_unsupported_runtime("build with WASM output") is not None


def test_wasm_with_emscripten_does_not_warn():
    """emscripten mention → assume user knows what they're doing."""
    with patch("shutil.which", _fake_which_none):
        assert detect_unsupported_runtime(
            "build with WASM using emscripten toolchain"
        ) is None


def test_generic_python_mention_does_not_warn():
    """`python` is not in the runtime list by default — we don't false-positive
    on scripts-that-generate-html kind of requests."""
    # python isn't in _RUNTIME_PROBES currently; confirm it stays so
    with patch("shutil.which", _fake_which_none):
        assert detect_unsupported_runtime(
            "use a python script to generate the data"
        ) is None


def test_note_tells_model_not_to_substitute():
    """Content of the note must forbid silent substitution."""
    with patch("shutil.which", _fake_which_none):
        note = detect_unsupported_runtime("use Deno please")
    assert "Do NOT silently substitute" in note
    assert "before writing any code" in note.lower() or "before proceeding" in note.lower()
