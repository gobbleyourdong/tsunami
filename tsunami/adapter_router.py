"""Auto-adapter selection — 2-way: chat ↔ tsunami-adapter.

Previously routed between build-v89 / gamedev / none. Collapsed to one
production adapter (`tsunami-adapter`) that handles both web and game
scaffolds; router's job is now just chat-vs-build gating.

  none              — base chat (no build intent)
  tsunami-adapter   — any build request (web, data, game, desktop, etc.)

Pure function. Caller mutates self.model.adapter.
"""
from __future__ import annotations

# User pulling back → drop to chat, regardless of current state.
_REVERT_PHRASES = (
    "forget about",
    "cancel that",
    "actually, no",
    "scrap that",
    "never mind",
    "nevermind",
    "nm,",
    "hold off",
    "don't build",
    "do not build",
    "stop building",
)

# Any one of these verbs + one of the nouns below means "build it".
_BUILD_VERBS = (
    "build", "make", "create", "generate", "spin up", "put together",
    "scaffold", "code", "write", "bootstrap", "start a", "start an",
    "set up", "setup", "clone",
)

# Nouns that mark something buildable — covers web, desktop, game, data.
_BUILD_NOUNS = (
    "app ", "game ", "website ", "page ", "site ", "landing", "dashboard",
    "component ", "form ", "calculator", "counter", "timer", "clock",
    "editor", "viewer", "tool ", "extension ", "plugin", "widget",
    "portal", "scraper", "bot ", "tracker", "chart", "table",
    "ui ", "api ", "server", "demo ", "clone ", "replica", "copy of",
    "version of", "engine", "simulator", "visualizer",
)

# Iteration on an existing project keeps the current adapter.
_ITERATION_VERBS = (
    "add ", "remove ", "delete ", "change ", "update ", "fix ",
    "rename ", "move ", "extract ", "refactor ", "style ",
)


def pick_adapter(user_message: str, current: str = "") -> tuple[str, str]:
    """Pick the best adapter for the given user message.

    Returns:
        (adapter, reason) where adapter is:
          "none"            — base chat mode
          "tsunami-adapter" — any build/iteration
    """
    msg = (user_message or "").lower()

    # 1. Revert signal → drop to chat, regardless of current state.
    for phrase in _REVERT_PHRASES:
        if phrase in msg:
            return "none", f"revert signal: {phrase!r}"

    # 2. Build verb + noun pair → specialized adapter.
    matched_verb = next(
        (v for v in _BUILD_VERBS if v + " " in msg or msg.startswith(v + " ")),
        None,
    )
    # Match noun as substring — also accept trailing EOL (user's prompt may
    # end on the noun without trailing space, e.g. "build me a game").
    matched_noun = next(
        (n.strip() for n in _BUILD_NOUNS
         if n in msg or msg.endswith(n.strip()) or f" {n.strip()} " in msg),
        None,
    )
    if matched_verb and matched_noun:
        return "tsunami-adapter", f"build pair: {matched_verb!r} + {matched_noun.strip()!r}"

    # 3. Iteration hold — already on the adapter? "Add X" keeps it.
    if current == "tsunami-adapter":
        for verb in _ITERATION_VERBS:
            if verb in msg:
                return current, f"iteration-hold: {verb.strip()!r}"

    # 4. Short conversational turn on adapter → still hold.
    if current == "tsunami-adapter" and len(msg.split()) < 20:
        return current, "short conversational turn — hold adapter"

    # 5. Default: chat mode.
    return "none", "chat mode (no build signal)"
