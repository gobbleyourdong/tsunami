"""Auto-adapter router — chat → build → gamedev transition criteria.

Matches the Manus-style decision matrix: explicit build intent flips to
build-v89, game signals flip to gamedev, iteration on specialized state
holds, revert signals drop back to chat.
"""

from __future__ import annotations

from tsunami.adapter_router import pick_adapter


def test_empty_message_stays_chat():
    adapter, reason = pick_adapter("", current="")
    assert adapter == "none"
    assert "chat" in reason.lower() or "no specialization" in reason.lower()


def test_conversational_greeting_stays_chat():
    adapter, _ = pick_adapter("hey what's up", current="")
    assert adapter == "none"


def test_build_verb_plus_noun_triggers_build_v89():
    adapter, reason = pick_adapter("build me a counter app", current="")
    assert adapter == "build-v89"
    assert "build" in reason.lower()


def test_build_variants_match():
    for prompt in [
        "create a todo list",
        "make a landing page",
        "develop a dashboard",
        "design a portfolio website",
        "scaffold an editor",
    ]:
        adapter, _ = pick_adapter(prompt, current="")
        assert adapter == "build-v89", f"failed on: {prompt!r}"


def test_game_signal_overrides_build():
    """Game is a specialization: `build me a game` → gamedev, not build-v89."""
    adapter, reason = pick_adapter("build me a game with WASD controls", current="")
    assert adapter == "gamedev"
    assert "game" in reason.lower()


def test_game_keywords_fire_gamedev():
    for prompt in [
        "make a platformer",
        "build a tilemap editor",
        "create a 2D game with gravity",
        "physics simulation with 20 bouncing balls",
        "use the Tsunami Engine to render 3D scene",
    ]:
        adapter, _ = pick_adapter(prompt, current="")
        assert adapter == "gamedev", f"failed on: {prompt!r}"


def test_iteration_holds_specialized_adapter():
    """'add dark mode' while currently on gamedev should HOLD gamedev."""
    adapter, reason = pick_adapter("add dark mode", current="gamedev")
    assert adapter == "gamedev"
    assert "iteration" in reason.lower() or "hold" in reason.lower()


def test_iteration_on_build_adapter_holds():
    adapter, _ = pick_adapter("fix the button styling", current="build-v89")
    assert adapter == "build-v89"


def test_short_conversational_on_specialized_holds():
    """Short 'looks good thanks' turn while specialized doesn't drop back to chat."""
    adapter, _ = pick_adapter("looks good, thanks", current="build-v89")
    assert adapter == "build-v89"


def test_revert_signal_drops_back_to_chat():
    for prompt in [
        "actually, no, forget about that",
        "scrap that build",
        "never mind, let's just talk",
    ]:
        adapter, reason = pick_adapter(prompt, current="build-v89")
        assert adapter == "none", f"failed on: {prompt!r}"
        assert "revert" in reason.lower()


def test_revert_overrides_build_signal():
    """If message has both 'forget about' and 'build', revert wins."""
    adapter, _ = pick_adapter("scratch that, let's just chat — actually nevermind building anything", current="build-v89")
    assert adapter == "none"


def test_game_signal_overrides_iteration_hold():
    """On build-v89, 'now add a game mode' should transition to gamedev."""
    adapter, _ = pick_adapter("now add a bullet-hell game mode", current="build-v89")
    assert adapter == "gamedev"


def test_new_build_from_chat():
    """chat → first real build turn flips to build-v89."""
    adapter, _ = pick_adapter("okay let's build a kanban board", current="none")
    assert adapter == "build-v89"


def test_multi_turn_flow_chat_build_gamedev():
    """End-to-end flow: chat → build → gamedev transitions."""
    current = "none"
    # Turn 1: conversational
    current, _ = pick_adapter("hi can you help me with something?", current=current)
    assert current == "none"
    # Turn 2: build intent
    current, _ = pick_adapter("build me a task tracker app", current=current)
    assert current == "build-v89"
    # Turn 3: iteration
    current, _ = pick_adapter("add localStorage persistence", current=current)
    assert current == "build-v89"
    # Turn 4: pivot to game
    current, _ = pick_adapter("actually let me instead build a 2D game", current=current)
    assert current == "gamedev"
    # Turn 5: iteration on game
    current, _ = pick_adapter("add collision detection", current=current)
    assert current == "gamedev"
    # Turn 6: revert
    current, _ = pick_adapter("forget about all that, just help me with something", current=current)
    assert current == "none"


def test_verb_without_noun_stays_chat():
    """'build' alone (no target noun) is ambiguous — don't fire build-v89."""
    adapter, _ = pick_adapter("i'm not sure what to build yet", current="")
    assert adapter == "none"


def test_noun_without_verb_stays_chat():
    adapter, _ = pick_adapter("dashboards are really hard", current="")
    assert adapter == "none"
