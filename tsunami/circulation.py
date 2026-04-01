"""Circulation — tension-aware routing.

Takes a current reading (tension score) and decides what to do:
- Grounded → deliver directly
- Capability gap → force tool call (search, calculate)
- Truth gap → explain the contradiction
- Drifting → refuse and say "I don't know"

Also validates tool results: if a search result INCREASES tension,
reject it and try a different source.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

log = logging.getLogger("tsunami.circulation")


class FlowType(Enum):
    """What kind of intervention is needed."""
    NONE = "none"                      # Deliver directly
    CAPABILITY_GAP = "capability"      # Need a tool (search, calculate)
    TRUTH_GAP = "truth"                # Statement contradicts known facts
    UNCERTAINTY = "uncertainty"         # Genuinely unknown
    MIXED = "mixed"                    # Both capability and truth issues


class ValidationStatus(Enum):
    """Status of a tool result after tension check."""
    VERIFIED = "verified"              # Tension dropped — safe to use
    UNVERIFIED = "unverified"          # Tension unchanged — use with caveat
    REJECTED = "rejected"              # Tension increased — don't use
    TANGENTIAL = "tangential"          # Doesn't answer the question


@dataclass
class Route:
    """Where circulation sends the flow."""
    flow_type: FlowType
    tension: float
    action: str        # "deliver", "search", "calculate", "refuse", "caveat"
    tools: List[str]   # suggested tools if capability gap
    explanation: str


@dataclass
class Validation:
    """Result of validating a tool's output."""
    status: ValidationStatus
    pre_tension: float
    post_tension: float
    delta: float
    result: Optional[str]
    caveat: Optional[str]
    action: str  # "use", "use_with_caveat", "retry", "reject"


# Capability gap markers — suggest tool usage
CAPABILITY_MARKERS = [
    r'\b(current|today|now|latest|recent|live)\b',
    r'\b(stock price|weather|news|score)\b',
    r'\b(calculate|compute|solve|how much)\b',
    r'\b(search|find|look up|who is|what is the)\b',
    r'\b(when did|where is|how do i)\b',
    r'\d+\s*[\+\-\*\/]\s*\d+',
]

# Truth gap markers
TRUTH_MARKERS = [
    r'\b(is it true|verify|fact check|prove|disprove)\b',
    r'\b(impossible|violates|breaks|against the laws)\b',
    r'\b(contradict|inconsistent|wrong)\b',
]


class Circulation:
    """Routes flow based on current (tension) readings."""

    # Thresholds
    LOW = 0.15
    MEDIUM = 0.30
    HIGH = 0.50
    CRITICAL = 0.70

    def route(self, query: str, tension: float) -> Route:
        """Decide what to do based on tension."""

        # Low tension — deliver directly
        if tension < self.LOW:
            return Route(
                flow_type=FlowType.NONE,
                tension=tension,
                action="deliver",
                tools=[],
                explanation="Low tension — response is grounded",
            )

        # Check what kind of gap
        cap_score = sum(1 for p in CAPABILITY_MARKERS if re.search(p, query, re.I))
        truth_score = sum(1 for p in TRUTH_MARKERS if re.search(p, query, re.I))

        if tension >= self.CRITICAL:
            return Route(
                flow_type=FlowType.UNCERTAINTY,
                tension=tension,
                action="refuse",
                tools=[],
                explanation="Critical tension — say 'I don't know' rather than hallucinate",
            )

        if cap_score > truth_score and cap_score > 0:
            tools = self._suggest_tools(query)
            return Route(
                flow_type=FlowType.CAPABILITY_GAP,
                tension=tension,
                action="search",
                tools=tools,
                explanation="Capability gap — need external tool to answer",
            )

        if truth_score > 0:
            return Route(
                flow_type=FlowType.TRUTH_GAP,
                tension=tension,
                action="explain",
                tools=[],
                explanation="Truth gap — statement may contradict known facts",
            )

        if tension >= self.HIGH:
            return Route(
                flow_type=FlowType.UNCERTAINTY,
                tension=tension,
                action="caveat",
                tools=["search_web"],
                explanation="High uncertainty — search to verify or add caveat",
            )

        return Route(
            flow_type=FlowType.MIXED,
            tension=tension,
            action="search",
            tools=["search_web"],
            explanation="Moderate tension — verify before delivering",
        )

    def validate_result(
        self,
        query: str,
        tool_result: str,
        pre_tension: float,
        post_tension: float,
    ) -> Validation:
        """Validate a tool result by comparing tension before and after.

        If tension dropped → result helped (verified).
        If tension rose → result made it worse (reject).
        """
        delta = post_tension - pre_tension

        if post_tension < self.LOW:
            return Validation(
                status=ValidationStatus.VERIFIED,
                pre_tension=pre_tension,
                post_tension=post_tension,
                delta=delta,
                result=tool_result,
                caveat=None,
                action="use",
            )

        if delta > 0.2:
            return Validation(
                status=ValidationStatus.REJECTED,
                pre_tension=pre_tension,
                post_tension=post_tension,
                delta=delta,
                result=None,
                caveat=f"Tool result increased tension by {delta:.2f} — unreliable",
                action="retry",
            )

        if post_tension < self.MEDIUM:
            return Validation(
                status=ValidationStatus.UNVERIFIED,
                pre_tension=pre_tension,
                post_tension=post_tension,
                delta=delta,
                result=tool_result,
                caveat="This information could not be fully verified.",
                action="use_with_caveat",
            )

        if post_tension > self.HIGH:
            return Validation(
                status=ValidationStatus.REJECTED,
                pre_tension=pre_tension,
                post_tension=post_tension,
                delta=delta,
                result=None,
                caveat=f"Result contradicts established knowledge (tension={post_tension:.2f})",
                action="reject",
            )

        return Validation(
            status=ValidationStatus.TANGENTIAL,
            pre_tension=pre_tension,
            post_tension=post_tension,
            delta=delta,
            result=tool_result,
            caveat="This result may not directly answer the question.",
            action="use_with_caveat",
        )

    def _suggest_tools(self, query: str) -> List[str]:
        q = query.lower()
        tools = []
        if any(w in q for w in ["current", "today", "news", "price", "weather"]):
            tools.append("search_web")
        if any(w in q for w in ["calculate", "compute", "solve"]):
            tools.append("python_exec")
        if any(w in q for w in ["search", "find", "who", "what", "where", "when"]):
            tools.append("search_web")
        return list(dict.fromkeys(tools))  # dedupe preserving order
