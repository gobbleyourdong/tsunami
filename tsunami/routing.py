"""Unified keyword routing — one matcher, one registry.

Six modules today each carry their own keyword dictionary and substring-
or word-boundary-match logic to route a task to a downstream context:

  project_init._pick_scaffold     →  directory scaffold  (react-app / dashboard / game / ...)
  planfile.pick_scaffold          →  plan.md template    (react-build / landing / dashboard / ...)
  task_decomposer.detect_domains  →  phase list          (data_viz / realtime / forms / ...)
  behavior_infer.infer_behaviors  →  seeded tests        (counter / pomodoro / todo / calculator)
  style_scaffolds._KEYWORD_MAP    →  visual doctrine     (editorial_dark / shadcn_startup / ...)
  brand_scaffold._INDUSTRY_BRIEFS →  per-asset prompts   (hypercar / city-ev / watch / ...)

Each layer has its own collision surface: today alone 9+ bugs came from
substring matches hitting unintended words ("counter" in "AnimatedCounter",
"live" in "deliverables", "badge" in a UI component name, "stats" in
"Stats row", "graph" in "paragraphs", "car brand" in "compact city-car
brand"). Each fix is a local patch — word-boundary regex here, keyword
removal there — without shared discipline.

This module is the first step toward one registry + one matcher. Each
classifier still owns its own routing DATA (what keywords map to what
target), but shares the matching LOGIC and the keyword-normalization
rules. Later passes can consolidate the data itself into a single
declarative structure (yaml / py dict with `{route: {keywords, target}}`
shape) once the shared matcher is proven across callers.

Design principles:

1. **Word-boundary by default for single-word keys.** `"live"` matches
   `"live chat"` but not `"deliverables/foo"`. Multi-word keys stay
   substring — they're specific enough ("live chat", "data viz").
2. **Priority cascade is explicit.** `match_first()` returns on first hit
   so ordering encodes specificity. Callers pass an ordered list of
   (keywords, target) tuples; most-specific first.
3. **All matches lowercase the task once.** No per-keyword toLowerCase()
   racing itself.
4. **Escape-hatch with `keyword_match_multiword`** — allows explicit
   multi-word matching where callers want to bypass word-boundary.
5. **Collision detection helper** — callers can run
   `matches(task, keywords)` to check which keys would hit, useful
   for diagnostics / tests.
"""

from __future__ import annotations

import re
from typing import Iterable


__all__ = [
    "normalize",
    "match_keyword",
    "match_first",
    "matches",
    "contains_any_multiword",
]


def normalize(task: str) -> str:
    """Lowercase + strip. Every matcher should call this ONCE up top."""
    return task.lower().strip()


def match_keyword(task_lower: str, keyword: str, *, plural_s: bool = False) -> bool:
    """Match a single keyword against a (pre-lowered) task.

    Single-word keywords use word-boundary regex. Multi-word or
    hyphenated keywords fall through to substring match — they are
    specific enough (e.g. "live chat", "bar chart", "art deco").

    When plural_s is True (project_init's convention), single-word keys
    also match the simple plural (e.g. "extension" matches "extensions").

    Examples:
        match_keyword("build a live chat app", "live chat")           → True
        match_keyword("save in the deliverables dir", "live")         → False  (boundary)
        match_keyword("an extensions pack", "extension", plural_s=True) → True
        match_keyword("my-data-viz stack", "data viz")                → True  (substring)
    """
    if not keyword:
        return False
    # Multi-word (contains space or hyphen): substring match is safe.
    if " " in keyword or "-" in keyword:
        return keyword in task_lower
    pattern = rf"\b{re.escape(keyword)}{'s?' if plural_s else ''}\b"
    return re.search(pattern, task_lower) is not None


def match_first(
    task: str,
    rules: Iterable[tuple[Iterable[str], object]],
    *,
    plural_s: bool = False,
    default: object = "",
) -> object:
    """Return the target from the FIRST rule whose keyword set hits.

    `rules` is an ordered iterable of (keywords, target) pairs. The
    first pair with ANY keyword matching `task` wins. Ordering encodes
    priority — put most-specific rules first.

    Returns `default` when no rule matches.

    This consolidates the identical cascade pattern found in
    project_init._pick_scaffold, planfile.pick_scaffold,
    style_scaffolds._KEYWORD_MAP, and brand_scaffold._match_industry.
    """
    low = normalize(task)
    for keywords, target in rules:
        for k in keywords:
            if match_keyword(low, k, plural_s=plural_s):
                return target
    return default


def matches(task: str, keywords: Iterable[str], *, plural_s: bool = False) -> set[str]:
    """Return the SET of keywords that hit the task. Diagnostic helper.

    Useful for collision detection — e.g., testing that the AURUM brief
    doesn't hit more than one realtime keyword, or flagging when a
    task text satisfies rules that should be mutually exclusive.
    """
    low = normalize(task)
    return {k for k in keywords if match_keyword(low, k, plural_s=plural_s)}


def contains_any_multiword(task: str, keywords: Iterable[str]) -> bool:
    """Substring-only check for multi-word keywords.

    Some callers (behavior_infer, task_decomposer domains) explicitly
    want substring matching even on single words. This helper makes
    the intent explicit at the call site rather than silently skipping
    the word-boundary guard.
    """
    low = normalize(task)
    return any(k in low for k in keywords)
