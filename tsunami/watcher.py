"""The Watcher — self-evaluation loop.

A lighter model that reviews the primary model's work.
Catches stalls, hallucinations, and quality issues.
Optional — the agent works without it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .model import LLMModel, create_model
from .state import AgentState

log = logging.getLogger("tsunami.watcher")


@dataclass
class WatcherReview:
    should_revise: bool
    concern: str | None = None
    suggestion: str | None = None


class Watcher:
    """Secondary model that evaluates the primary model's decisions."""

    def __init__(self, model: LLMModel, interval: int = 5):
        self.model = model
        self.interval = interval

    async def review(self, state: AgentState, proposed_tool: str,
                     proposed_args: dict) -> WatcherReview:
        """Review a proposed tool call before execution."""

        # Build a condensed context for the watcher
        recent = state.conversation[-10:]  # last 10 messages
        context_lines = []
        for m in recent:
            prefix = m.role.upper()
            content = m.content[:300]
            context_lines.append(f"[{prefix}] {content}")

        plan_summary = state.plan.summary() if state.plan else "No plan."
        user_request = state.conversation[1].content if len(state.conversation) > 1 else "Unknown"
        history_text = "\n".join(context_lines)

        prompt = f"""You are a quality reviewer for an autonomous agent. Review this proposed action.

## User's Original Request
{user_request}

## Current Plan
{plan_summary}

## Recent History (last 10 messages)
{history_text}

## Proposed Action
Tool: {proposed_tool}
Arguments: {proposed_args}

## Iteration Count: {state.iteration}

## Review Criteria
1. Is this action making meaningful progress toward the goal?
2. Is the tool choice appropriate? (Would a different tool be better?)
3. Are we stuck in a loop? (Same or similar actions repeated?)
4. Is there a risk of error or harmful action?
5. TRIANGULATION: If message_result is being called with factual claims, were those claims verified via search? If no search_web or browser_navigate appeared in recent history, REVISE with "verify claims before delivering".

Respond with EXACTLY one of:
APPROVE — if the action is reasonable
REVISE: <suggestion> — if the action should be changed

Your response must start with either APPROVE or REVISE:"""

        try:
            response = await self.model.generate(
                messages=[
                    {"role": "system", "content": "You are a concise quality reviewer. One word or one sentence."},
                    {"role": "user", "content": prompt},
                ],
            )

            text = response.content.strip()
            if text.startswith("APPROVE"):
                return WatcherReview(should_revise=False)
            elif text.startswith("REVISE:"):
                suggestion = text[7:].strip()
                return WatcherReview(should_revise=True, concern="Watcher flagged", suggestion=suggestion)
            else:
                # Ambiguous response — default to approve
                return WatcherReview(should_revise=False)

        except Exception as e:
            log.warning(f"Watcher error: {e}")
            return WatcherReview(should_revise=False)  # fail open

    def should_activate(self, iteration: int) -> bool:
        """Check if the watcher should run on this iteration."""
        return iteration > 0 and iteration % self.interval == 0
