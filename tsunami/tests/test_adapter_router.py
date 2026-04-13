"""Auto-adapter router — 2-way chat ↔ tsunami-adapter transition.

Build verb + noun → tsunami-adapter. Iteration on adapter state holds.
Revert signals drop back to chat. Everything else stays in chat.
"""

from __future__ import annotations

from tsunami.adapter_router import pick_adapter


def test_empty_message_stays_chat():
    adapter, reason = pick_adapter("", current="")
    assert adapter == "none"
    assert "chat" in reason.lower() or "no build" in reason.lower()


def test_conversational_greeting_stays_chat():
    adapter, _ = pick_adapter("hey what's up", current="")
    assert adapter == "none"


def test_build_verb_plus_noun_triggers_adapter():
    adapter, reason = pick_adapter("build me a counter app", current="")
    assert adapter == "tsunami-adapter"
    assert "build" in reason.lower()


def test_build_variants_match():
    for prompt in (
        "make a calculator",
        "create a todo app",
        "generate a landing page",
        "scaffold a dashboard",
        "bootstrap a form",
    ):
        adapter, _ = pick_adapter(prompt, current="")
        assert adapter == "tsunami-adapter", f"failed on: {prompt!r}"


def test_game_prompt_also_routes_to_adapter():
    """One adapter handles games too — 'build me a game' still fires."""
    adapter, _ = pick_adapter("build me a snake game", current="")
    assert adapter == "tsunami-adapter"


def test_iteration_verbs_hold_adapter():
    adapter, reason = pick_adapter("add dark mode", current="tsunami-adapter")
    assert adapter == "tsunami-adapter"
    assert "iteration" in reason.lower() or "hold" in reason.lower()


def test_short_conversation_on_adapter_holds():
    adapter, reason = pick_adapter("looks good thanks", current="tsunami-adapter")
    assert adapter == "tsunami-adapter"
    assert "hold" in reason.lower()


def test_revert_phrase_drops_to_chat():
    for phrase in ("forget about that", "nevermind", "scrap that", "stop building"):
        adapter, _ = pick_adapter(phrase, current="tsunami-adapter")
        assert adapter == "none", f"failed on: {phrase!r}"
