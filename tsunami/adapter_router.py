"""Auto-adapter selection — 3-way: chat → build → gamedev.

The previous router handled 13 adapters (electron, chrome-ext, realtime,
auth-app, fullstack, dataviz, landing, dashboard, api-only, ai-app,
form-app, gamedev, build-v89). Most of those adapters never trained,
and the keyword-surface was brittle. Cut down to the actual target
distribution:

  none      — chat mode (no build intent)
  build-v89 — general web/desktop/data app scaffolding
  gamedev   — game-shaped prompts (engine, WASD, sprite, tilemap, etc.)

Matches Manus-style criteria: stay in base chat until intent crystallizes
as "build X", then transition to the specialized adapter. Iteration
on an existing specialized project holds the current adapter.

Pure function. Caller mutates self.model.adapter.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Signal vocabularies
# ---------------------------------------------------------------------------

# User pulling back → chat, regardless of current state.
_REVERT_PHRASES = (
    "forget about",
    "cancel that",
    "actually, no",
    "scrap that",
    "scratch that",
    "nevermind",
    "never mind",
    "stop that build",
    "don't build",
)

# Game signals — checked before build (a game request is always gamedev).
_GAME_WORDS = (
    "game", "gamedev", "game dev",
    "webgpu", "three.js", "three js", "tsunami engine",
    "platformer", "shooter", " rpg ", "roguelike", "bullet hell",
    "idle game", "incremental game", "tower defense",
    "sprite", "tilemap", "tile map", "physics simulation",
    "3d scene", "3d game", "2d game", "canvas game",
    "bouncing ball", "particle system",
    "wasd ", "keyboard controls", "gamepad",
)

# Build verbs + nouns — the "build X" pair that triggers general build.
_BUILD_VERBS = ("build", "create", "make", "develop", "design", "write")
_BUILD_NOUNS = (
    "app", "website", "site", "webapp", "web app",
    "page", "landing page", "dashboard", "tool",
    "tracker", "form", "calculator", "timer", "todo",
    "editor", "viewer", "list", "kanban", "blog",
    "portfolio", "resume", "wiki", "cms", "shop",
    "store", "cart", "chat", "calendar", "planner",
    "notes app", "note taking", "reminder", "habit tracker",
    "clone of", "clone for",
)

# Iteration signals — on specialized adapter, these keep current state
# ("add dark mode" on a build shouldn't flip back to chat).
_ITERATION_VERBS = (
    "add ", "fix ", "change ", "update ", "remove ", "delete ",
    "refactor ", "rename ", "style ", "restyle ", "tweak ",
    "adjust ", "modify ", "improve ", "polish ",
)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def pick_adapter(user_message: str, current: str = "") -> tuple[str, str]:
    """Pick the best adapter for the given user message.

    Returns:
        (adapter, reason) where adapter is:
          "none"      — chat mode
          "build-v89" — general scaffolding
          "gamedev"   — game-shaped
    """
    msg = (user_message or "").lower()

    # 1. Revert signal → drop to chat, regardless of current state.
    for phrase in _REVERT_PHRASES:
        if phrase in msg:
            return "none", f"revert signal: {phrase!r}"

    # 2. Game signals beat build signals (specialization, not fallback).
    for word in _GAME_WORDS:
        if word in msg:
            return "gamedev", f"game signal: {word!r}"

    # 3. Build verb + noun pair → general scaffolding.
    matched_verb = next(
        (v for v in _BUILD_VERBS if v + " " in msg or msg.startswith(v + " ")),
        None,
    )
    matched_noun = next((n for n in _BUILD_NOUNS if n in msg), None)
    if matched_verb and matched_noun:
        return "build-v89", f"build pair: {matched_verb!r} + {matched_noun.strip()!r}"

    # 4. Iteration hold — already on specialized adapter? "Add X" keeps it.
    if current in ("gamedev", "build-v89"):
        for verb in _ITERATION_VERBS:
            if verb in msg:
                return current, f"iteration-hold: {verb.strip()!r}"

    # 5. Short conversational turn on specialized adapter → still hold.
    if current in ("gamedev", "build-v89") and len(msg.split()) < 20:
        return current, "short conversational turn — hold specialized adapter"

    # 6. Default: chat mode.
    return "none", "chat mode (no specialization signal)"
