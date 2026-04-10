"""Model fallback — switch to backup model after consecutive failures.

When the primary model hits N consecutive 529/503/overloaded errors,
automatically switch to a fallback model and retry. This keeps the
agent running during capacity issues instead of failing hard.

The fallback is conservative:
- Only triggers on server overload errors (529, 503)
- Requires N consecutive failures (not just one)
- Falls back to a specified backup model
- Logs the switch for visibility
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger("tsunami.model_fallback")

# Default: switch after 3 consecutive overload errors
DEFAULT_MAX_FAILURES = 3

# HTTP status codes that trigger fallback
OVERLOAD_CODES = frozenset({529, 503})


class FallbackTriggeredError(Exception):
    """Raised when fallback threshold is reached.

    The agent loop catches this and switches models.
    """
    def __init__(self, primary_model: str, fallback_model: str):
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        super().__init__(
            f"Fallback triggered: {primary_model} → {fallback_model}"
        )


@dataclass
class FallbackState:
    """Tracks consecutive failures for fallback decisions."""
    primary_model: str = ""
    fallback_model: str = ""
    consecutive_failures: int = 0
    max_failures: int = DEFAULT_MAX_FAILURES
    is_using_fallback: bool = False
    total_fallbacks: int = 0

    def record_failure(self, status_code: int) -> bool:
        """Record a failure. Returns True if fallback should trigger.

        Only counts overload errors (529, 503). Other errors don't
        count toward the fallback threshold.
        """
        if status_code not in OVERLOAD_CODES:
            return False

        self.consecutive_failures += 1
        log.warning(
            f"Overload error {status_code} "
            f"({self.consecutive_failures}/{self.max_failures})"
        )

        if self.consecutive_failures >= self.max_failures and self.fallback_model:
            return True
        return False

    def record_success(self):
        """Reset consecutive failure counter on success."""
        if self.consecutive_failures > 0:
            log.debug(f"Success — resetting failure counter from {self.consecutive_failures}")
        self.consecutive_failures = 0

    def trigger_fallback(self) -> str:
        """Switch to fallback model. Returns the fallback model name."""
        self.is_using_fallback = True
        self.total_fallbacks += 1
        self.consecutive_failures = 0
        log.warning(
            f"Model fallback triggered: {self.primary_model} → {self.fallback_model} "
            f"(total fallbacks: {self.total_fallbacks})"
        )
        return self.fallback_model

    def restore_primary(self):
        """Switch back to primary model (e.g., after cooldown)."""
        if self.is_using_fallback:
            log.info(f"Restoring primary model: {self.primary_model}")
            self.is_using_fallback = False
            self.consecutive_failures = 0

    @property
    def current_model(self) -> str:
        """Get the currently active model."""
        if self.is_using_fallback and self.fallback_model:
            return self.fallback_model
        return self.primary_model

    @property
    def has_fallback(self) -> bool:
        return bool(self.fallback_model)

    def format_status(self) -> str:
        if self.is_using_fallback:
            return f"Using fallback: {self.fallback_model} (primary: {self.primary_model})"
        if self.consecutive_failures > 0:
            return (
                f"Primary: {self.primary_model} "
                f"({self.consecutive_failures}/{self.max_failures} failures)"
            )
        return f"Primary: {self.primary_model}"
