"""Pressure — tension monitoring over time.

Tracks tension readings across the session. Escalates when
pressure builds (sustained high tension = the model is
consistently uncertain or hallucinating).

Pressure increases with depth. The deeper the session goes,
the more we've accumulated, the more likely context is stale.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger("tsunami.pressure")


class AlertLevel(Enum):
    """How much pressure has built up."""
    CALM = "calm"           # Average tension < 0.2
    MODERATE = "moderate"   # Average tension 0.2-0.4
    HEAVY = "heavy"         # Average tension 0.4-0.6
    CRUSHING = "crushing"   # Average tension > 0.6 or 3+ consecutive high readings


@dataclass
class Reading:
    """A single pressure reading."""
    tension: float
    timestamp: float = field(default_factory=time.time)
    tool_name: str = ""
    classification: str = ""


class Pressure:
    """Tracks tension over time and escalates alerts."""

    def __init__(self, window_size: int = 20):
        self.readings: list[Reading] = []
        self.window_size = window_size
        self.alert_level = AlertLevel.CALM
        self._consecutive_high = 0

    def record(self, tension: float, tool_name: str = "", classification: str = ""):
        """Record a tension reading."""
        self.readings.append(Reading(
            tension=tension,
            tool_name=tool_name,
            classification=classification,
        ))
        # Trim to window
        if len(self.readings) > self.window_size * 2:
            self.readings = self.readings[-self.window_size:]

        # Track consecutive high readings
        if tension > 0.5:
            self._consecutive_high += 1
        else:
            self._consecutive_high = 0

        # Update alert level
        self._update_alert()

    def _update_alert(self):
        """Recalculate alert level from recent readings."""
        if not self.readings:
            self.alert_level = AlertLevel.CALM
            return

        recent = self.readings[-self.window_size:]
        avg = sum(r.tension for r in recent) / len(recent)

        if self._consecutive_high >= 3 or avg > 0.6:
            self.alert_level = AlertLevel.CRUSHING
        elif avg > 0.4:
            self.alert_level = AlertLevel.HEAVY
        elif avg > 0.2:
            self.alert_level = AlertLevel.MODERATE
        else:
            self.alert_level = AlertLevel.CALM

    @property
    def average_tension(self) -> float:
        if not self.readings:
            return 0.0
        recent = self.readings[-self.window_size:]
        return sum(r.tension for r in recent) / len(recent)

    @property
    def max_tension(self) -> float:
        if not self.readings:
            return 0.0
        return max(r.tension for r in self.readings[-self.window_size:])

    @property
    def is_escalated(self) -> bool:
        return self.alert_level in (AlertLevel.HEAVY, AlertLevel.CRUSHING)

    @property
    def consecutive_high(self) -> int:
        return self._consecutive_high

    def should_force_search(self) -> bool:
        """Should we force a search to ground the agent?"""
        return self._consecutive_high >= 2 or self.alert_level == AlertLevel.CRUSHING

    def should_refuse(self) -> bool:
        """Should the agent refuse to answer rather than hallucinate?"""
        return self._consecutive_high >= 4

    def format_status(self) -> str:
        """Human-readable pressure status."""
        n = len(self.readings)
        return (
            f"Pressure: {self.alert_level.value} "
            f"(avg={self.average_tension:.2f}, max={self.max_tension:.2f}, "
            f"readings={n}, consecutive_high={self._consecutive_high})"
        )

    def reset(self):
        """Reset after a successful grounded delivery."""
        self._consecutive_high = 0
        # Don't clear readings — keep history for monitoring
