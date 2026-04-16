"""WilsonLoop — semantic drift detection as the high-level orchestration layer.

Sits ABOVE Circulation. Where Circulation is local (per-event count-based
circuit breaker for read_spiral / ctx_overflow), WilsonLoop is global
(trajectory-shape based, semantic, samples every K iterations).

Concept (v1, telemetry-only):
    1. Anchor: snapshot the user's original task statement at iter 0.
    2. Probe: every ``probe_every`` iters, snapshot what the agent looks like
       it's doing now (synthesized from recent tool_args + assistant text).
    3. Loop trace: cosine similarity between the current probe and the anchor;
       and between successive probes (segment angles).
    4. Holonomy: 1 - cos(probe_now, anchor) is the simplest scalar — how far
       the agent's apparent goal has rotated away from the user's stated goal.
       More-faithful Wilson-loop integral comes in v2 when we plug in a real
       embedding source; v1 uses dependency-free token-set cosine.
    5. on_drift: callback fired when holonomy exceeds threshold for ≥N
       consecutive probes. v1 is telemetry-only (callback is no-op + log).
       v2 will graduate to actual interventions (force replan / clarify).

Why two layers (Circulation + WilsonLoop):
    - Circulation catches LOCAL pathologies fast (3 stalls = trip).
    - WilsonLoop catches MACRO drift the count-based view can't see
      (e.g., agent stays "productive" — file_writes succeed, no stalls — but
      the writes have rotated away from the user's actual goal).

Wired into agent.py via:
    - Construct in Agent.__init__ with goal_anchor=user_message
    - Call ``probe(state)`` once per K iters in the main loop
    - on_drift logged at WARNING for now; downstream consumes the log

This is a MEASUREMENT module. Behavior changes belong in a separate commit
once telemetry shows the metric correlates with downstream failures.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger("tsunami.wilson_loop")


# Tokenization: lowercase word characters, length ≥ 3 (drop noise).
_WORD = re.compile(r"[a-z][a-z0-9_]{2,}")
# Stopwords that don't carry semantic intent. Keep this list minimal —
# we want to compare on content words. Add to it if telemetry shows
# spurious drift caused by common tokens.
_STOP = frozenset({
    "the", "and", "for", "with", "this", "that", "from", "into", "onto",
    "you", "your", "our", "any", "all", "but", "not", "are", "was", "were",
    "has", "have", "had", "can", "will", "would", "should", "could", "must",
    "use", "using", "make", "made", "build", "built", "create", "created",
    "get", "got", "set", "put", "tool", "function", "argument", "result",
    "response", "request", "message", "iteration", "iter", "step", "agent",
})


def _tokens(text: str) -> set[str]:
    """Tokenize to a set of content words. Pure / no allocations on small inputs."""
    return {t for t in _WORD.findall(text.lower()) if t not in _STOP}


def _cosine(a: set[str], b: set[str]) -> float:
    """Set-based cosine similarity (Otsuka-Ochiai). 0 → orthogonal, 1 → identical.

    Cheaper-but-faithful proxy for embedding cosine when both inputs are short.
    Replace with real cosine(embed(a), embed(b)) in v2.
    """
    if not a or not b:
        return 0.0
    inter = len(a & b)
    denom = (len(a) * len(b)) ** 0.5
    return inter / denom if denom else 0.0


@dataclass
class Probe:
    """One snapshot of the agent's apparent intent at iter_n."""
    iter_n: int
    text: str                       # synthesized intent string
    tokens: set[str] = field(default_factory=set)
    holonomy: float = 0.0           # 1 - cos(probe.tokens, anchor.tokens)


@dataclass
class WilsonLoop:
    """High-level semantic drift detector.

    Parameters
    ----------
    goal_anchor
        Verbatim user task statement. Snapshotted once at construction.
    probe_every
        How many iterations between probes. Lower = finer telemetry, higher
        cost (each probe re-tokenizes recent state). Default 10 — coarse
        enough to be cheap, fine enough to catch drift mid-session.
    drift_threshold
        Holonomy threshold above which a probe is "drifted". Range (0, 1].
        0.7 is a reasonable v1 default — alignment below 0.3 = clearly off-topic.
    consecutive_drift_to_fire
        How many consecutive drifted probes trigger ``on_drift``. Single-probe
        spikes are noisy; ≥2 consecutive is real signal.
    on_drift
        Callback fired when ``consecutive_drift_to_fire`` is reached. v1 default
        is no-op + log. v2 will pass an agent reference to take action.

    Notes
    -----
    Telemetry-only by design. ``on_drift`` does NOT mutate agent state in v1.
    Once ``probe.holonomy`` correlates with downstream failures (regression
    check fails, undertow FAIL, model_chat-instead-of-message_result), the
    callback graduates to interventions in a separate commit.
    """

    goal_anchor: str
    probe_every: int = 10
    drift_threshold: float = 0.7
    consecutive_drift_to_fire: int = 2
    on_drift: Callable[["WilsonLoop", "Probe"], None] | None = None

    _anchor_tokens: set[str] = field(init=False, repr=False)
    _probes: list[Probe] = field(default_factory=list, init=False, repr=False)
    _consecutive_drift: int = field(default=0, init=False, repr=False)
    _fired: bool = field(default=False, init=False, repr=False)

    def __post_init__(self):
        self._anchor_tokens = _tokens(self.goal_anchor)
        log.warning(
            f"wilson_loop: anchored on {len(self._anchor_tokens)} content tokens "
            f"(probe_every={self.probe_every}, drift_threshold={self.drift_threshold})"
        )

    def should_probe(self, iter_n: int) -> bool:
        """True if iter_n is a probe iteration. Cheap predicate for the hot loop."""
        return iter_n > 0 and iter_n % self.probe_every == 0

    def probe(self, iter_n: int, intent_text: str) -> Probe:
        """Take a probe at iter_n. Caller synthesizes intent_text from state.

        Returns the Probe (caller may inspect ``probe.holonomy``). Side effect:
        appends to internal trajectory and may fire ``on_drift``.
        """
        toks = _tokens(intent_text)
        sim = _cosine(toks, self._anchor_tokens)
        holonomy = 1.0 - sim
        p = Probe(iter_n=iter_n, text=intent_text[:200], tokens=toks, holonomy=holonomy)
        self._probes.append(p)
        # log.warning during v1 telemetry window — default Python log level
        # filters INFO; this is what makes the metric visible. Demote to .info
        # once the metric graduates to interventions and we don't need the
        # raw signal in eval logs anymore.
        log.warning(
            f"wilson_loop: probe iter={iter_n} sim={sim:.3f} holonomy={holonomy:.3f} "
            f"(consec_drift={self._consecutive_drift}, anchor_overlap={len(toks & self._anchor_tokens)})"
        )

        # Drift accounting
        if holonomy > self.drift_threshold:
            self._consecutive_drift += 1
            if self._consecutive_drift >= self.consecutive_drift_to_fire and not self._fired:
                self._fired = True
                log.warning(
                    f"wilson_loop: DRIFT at iter={iter_n} — holonomy={holonomy:.3f} for "
                    f"{self._consecutive_drift} consecutive probes; on_drift firing"
                )
                if self.on_drift is not None:
                    try:
                        self.on_drift(self, p)
                    except Exception as e:
                        log.warning(f"wilson_loop: on_drift callback raised — swallowed: {e}")
        else:
            # Reset consecutive on a clean probe; allow re-firing later
            if self._consecutive_drift > 0:
                log.info(f"wilson_loop: drift streak reset (was {self._consecutive_drift})")
            self._consecutive_drift = 0
            self._fired = False
        return p

    def trajectory(self) -> list[Probe]:
        """Read-only view of recorded probes. For post-hoc analysis / tests."""
        return list(self._probes)

    def total_wander(self) -> float:
        """Sum of segment holonomies (rough path length in concept-space).

        Useful for retrospective analysis: high total_wander with low final
        holonomy = agent took a meandering path back to the goal. Both = lost.
        """
        return sum(p.holonomy for p in self._probes)


def synthesize_intent(recent_tool_calls: list[tuple[str, dict]], assistant_text: str = "") -> str:
    """Build the 'what is the agent doing now' string from recent state.

    Synthesis rule v1: concatenate (tool_name + key arg values) for the last
    few calls, plus any free-text assistant message. Keep it short — token
    cosine is sensitive to dilution.

    ``recent_tool_calls`` should be in chronological order; caller slices.
    """
    parts: list[str] = []
    for name, args in recent_tool_calls:
        # Surface only string-valued args (path, command, query, content[:80]).
        snippet_parts = [name]
        for k, v in args.items():
            if isinstance(v, str):
                snippet_parts.append(f"{k}={v[:80]}")
        parts.append(" ".join(snippet_parts))
    if assistant_text:
        parts.append(assistant_text[:200])
    return " | ".join(parts)
