"""Auto-adapter selection — chat → build → gamedev transitions.

Matches the Manus-style criteria: stay in base chat until the user's intent
crystallizes as "build X", then transition to the specialized adapter. Game
prompts go to `gamedev`; general web-dev goes to `build-v89`. Iteration on
an existing specialized project holds the current adapter (don't flip back
to chat on an "add dark mode" follow-up).

Pure function — returns (adapter_name, reason). Caller mutates
`self.model.adapter` and, on transition, may log / surface the reason.
"""

from __future__ import annotations

# ---- Signal vocabularies ---------------------------------------------------

# Cancel / revert — user pulls back, go to chat.
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

# Game signals — strongest match wins (checked before build).
# Include artifact nouns that are specifically game-shaped.
_GAME_WORDS = (
    # explicit category
    "game", "gamedev", "game dev",
    # engines / runtimes
    "webgpu", "three.js", "three js", "tsunami engine",
    # genres
    "platformer", "shooter", " rpg ", "roguelike", "bullet hell",
    "idle game", "incremental game", "tower defense",
    # mechanics / rendering
    "sprite", "tilemap", "tile map", "physics simulation",
    "3d scene", "3d game", "2d game", "canvas game",
    "bouncing ball", "particle system",
    # input / control
    "wasd ", "keyboard controls", "gamepad",
)

# Build verb + noun pair — classic web/app scaffolding.
_BUILD_VERBS = (
    "build", "create", "make", "develop", "design", "scaffold",
    "implement", "code up", "whip up",
)
_BUILD_NOUNS = (
    # apps / utilities
    "app", "application", "website", "webapp", "web app",
    "dashboard", "tool", "utility", "tracker", "manager",
    "editor", "viewer", "player", "calculator", "converter",
    # content
    "landing page", "portfolio", "blog", "homepage",
    "form", "survey",
    # data
    "todo", "to-do", "todo list", "to-do list",
    "kanban", "board", "list", "catalog",
    # pages / UI
    " page", "page.", " ui", " interface",
)

# Iteration verbs — when current adapter is specialized, these hold it.
_ITERATION_VERBS = (
    "add ", "change ", "fix ", "update ", "modify ", "improve ", "extend ",
    "make it ", "refactor ", "clean up ", "rename ", "rewrite ",
    "instead", "also add",
)


# ---- Router ----------------------------------------------------------------

def pick_adapter(user_message: str, current: str = "") -> tuple[str, str]:
    """Pick the best adapter for the given user message.

    Args:
        user_message: the user's turn text.
        current: the adapter currently in use (from prior turn); drives
            iteration-hold behavior.

    Returns:
        (adapter, reason) — adapter is "none" for chat mode, "build-v89"
        for general web-dev, or "gamedev" for game scaffolds. `reason` is a
        short human-readable tag for logging.
    """
    msg = (user_message or "").lower()

    # 1. User pulls back → chat, regardless of current state.
    for phrase in _REVERT_PHRASES:
        if phrase in msg:
            return "none", f"revert signal: {phrase!r}"

    # 2. Game signals beat build signals (game is a specialization, not a
    #    fallback — if the user says "game" we go to gamedev even if the
    #    sentence also contains "build").
    for word in _GAME_WORDS:
        if word in msg:
            return "gamedev", f"game signal: {word!r}"

    # 3. Build verb + noun pair.
    matched_verb = next((v for v in _BUILD_VERBS if v + " " in msg or msg.startswith(v + " ")), None)
    matched_noun = next((n for n in _BUILD_NOUNS if n in msg), None)
    if matched_verb and matched_noun:
        return "build-v89", f"build pair: {matched_verb!r} + {matched_noun.strip()!r}"

    # 4. Iteration hold — if already specialized, an "add X" / "fix Y" / etc.
    #    turn should KEEP the current adapter, not drop back to chat.
    if current in ("gamedev", "build-v89"):
        for verb in _ITERATION_VERBS:
            if verb in msg:
                return current, f"iteration-hold: matched {verb.strip()!r}"

    # 5. No specialization signal. If we were already specialized and the
    #    user's turn is short/conversational, still hold (don't flip-flop
    #    on marginal signals like "looks good, thanks").
    if current in ("gamedev", "build-v89") and len(msg.split()) < 20:
        return current, "short conversational turn — hold specialized adapter"

    # 6. Default: chat.
    return "none", "chat mode (no specialization signal)"
