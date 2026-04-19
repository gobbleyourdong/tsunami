"""Task → behavior list inference.

Given a free-text task description, produce a list of {trigger, expect}
behaviors that are plausible for it. The goal is to seed `App.test.tsx`
with concrete contracts BEFORE the drone writes App.tsx, so the drone
is building to a fixed target instead of producing something and then
testing it.

Heuristic for now: keyword-matched patterns per common task family
(pomodoro, todo, counter, calculator, dice, note-taker). If the task
doesn't match a known family, return an empty list — the drone can
write tests manually for novel tasks.

This is the "wave's thinking" step. Do it once per task, keep cheap.
"""

from __future__ import annotations

import re
from typing import Iterable


_Behavior = dict  # {"trigger": str, "expect": str}


def _has_any(text: str, words: Iterable[str]) -> bool:
    low = text.lower()
    return any(w in low for w in words)


def _pomodoro(task: str) -> list[_Behavior]:
    # Keep selectors achievable: role+name (ARIA convention any competent
    # button renderer satisfies) for triggers; text-content probes for
    # expects that don't require data-testid scaffolding on App.tsx.
    return [
        {"trigger": "click [role=button name=/start/i]",
         "expect": "[role=button name=/pause/i] toBeInTheDocument"},
    ]


def _todo(task: str) -> list[_Behavior]:
    return [
        {"trigger": "type 'buy milk' into [role=textbox] + press Enter",
         "expect": "[text=/buy milk/i] toBeInTheDocument"},
    ]


def _counter(task: str) -> list[_Behavior]:
    return [
        {"trigger": "click [role=button name=/\\+|increment|plus/i]",
         "expect": "[text=/^1$/] toBeInTheDocument"},
    ]


def _calculator(task: str) -> list[_Behavior]:
    return [
        {"trigger": "click [role=button name=/^2$/]",
         "expect": "[text=/2/] toBeInTheDocument"},
    ]


_FAMILIES = [
    # (keyword set, handler)
    ({"pomodoro"}, _pomodoro),
    ({"todo", "to-do", "task list", "tasks"}, _todo),
    ({"counter", "increment", "tally"}, _counter),
    ({"calculator", "arithmetic"}, _calculator),
]


def infer_behaviors(task: str) -> list[_Behavior]:
    """Return a best-guess behavior list for the task. Empty means the
    orchestrator should let the drone declare its own tests.
    """
    if not task:
        return []
    out: list[_Behavior] = []
    seen_triggers: set[str] = set()
    for keywords, handler in _FAMILIES:
        if _has_any(task, keywords):
            for b in handler(task):
                t = b["trigger"]
                if t in seen_triggers:
                    continue
                seen_triggers.add(t)
                out.append(b)
    return out


if __name__ == "__main__":
    samples = [
        "Build a Pomodoro timer with start, pause, reset buttons and a task list.",
        "Simple counter with + button",
        "Calculator with +-*/ keys",
        "Random thing that matches nothing",
    ]
    for s in samples:
        print(f"{s!r:70s} → {infer_behaviors(s)}")
