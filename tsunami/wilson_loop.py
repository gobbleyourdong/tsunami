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

import json
import logging
import math
import os
import re
import urllib.error
import urllib.request
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


def _embed(endpoint: str, text: str, timeout: float = 2.0) -> list[float] | None:
    """POST {endpoint}/v1/embeddings with a short timeout. Return None on any failure.

    Designed to be a non-breaking upgrade path for WilsonLoop v2: when the
    eddy/coder llama-server is launched with ``--embeddings``, this returns
    a real dense vector and ``probe()`` uses it for cosine. Otherwise returns
    None and ``probe()`` transparently falls back to token-set cosine.

    Failure modes folded into None return (all non-fatal):
        - endpoint empty / unset
        - connection refused / DNS failure
        - HTTP 501 "This server does not support embeddings"
        - malformed JSON / missing ``data[0].embedding`` key
        - timeout
    """
    if not endpoint or not text:
        return None
    url = endpoint.rstrip("/") + "/v1/embeddings"
    payload = json.dumps({"input": text[:2048]}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return None
    try:
        vec = body["data"][0]["embedding"]
    except (KeyError, IndexError, TypeError):
        return None
    if not isinstance(vec, list) or not vec:
        return None
    return [float(x) for x in vec]


def _vec_cosine(a: list[float], b: list[float]) -> float:
    """Dense-vector cosine. Returns 0.0 on zero-norm or length mismatch."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    denom = math.sqrt(na) * math.sqrt(nb)
    return dot / denom if denom else 0.0


@dataclass
class Probe:
    """One snapshot of the agent's apparent intent at iter_n."""
    iter_n: int
    text: str                       # synthesized intent string
    tokens: set[str] = field(default_factory=set)
    holonomy: float = 0.0           # 1 - cos(probe.tokens, anchor.tokens)
    src: str = "tokens"             # "tokens" (set-cosine) or "embed" (vector-cosine)


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
    # Tuned 2026-04-16 (post-telemetry calibration): K=10/threshold=2 was
    # firing at iter 20 — too early, before agent had emitted enough
    # goal-related content for the cosine to stabilize. K=15/threshold=3
    # means drift must persist for 45 iters before on_drift fires.
    probe_every: int = 15
    drift_threshold: float = 0.7
    consecutive_drift_to_fire: int = 3
    on_drift: Callable[["WilsonLoop", "Probe"], None] | None = None
    # v2 embedding swap (debt entry 0c34e8c). When set to a reachable
    # llama-server endpoint that was launched with ``--embeddings``, probe()
    # uses real vector cosine. When None/empty/unreachable/501, probe()
    # transparently falls back to token-set cosine — byte-identical to v1.
    # Default None means: read ``TSUNAMI_EMBED_ENDPOINT`` env var in
    # __post_init__; if that's also unset, stay on the token-cosine path.
    embedding_endpoint: str | None = None
    # Anchor embed (one-shot at construction) gets a generous timeout because
    # the same llama-server is also serving /v1/chat/completions — those
    # requests block embedding slots. Per-probe embeds reuse this same value
    # (probes are infrequent enough that 10s headroom is fine).
    embed_timeout_sec: float = 10.0

    _anchor_tokens: set[str] = field(init=False, repr=False)
    _anchor_text: str = field(init=False, repr=False, default="")
    _anchor_embed: list[float] | None = field(init=False, repr=False, default=None)
    _probes: list[Probe] = field(default_factory=list, init=False, repr=False)
    _consecutive_drift: int = field(default=0, init=False, repr=False)
    _fired: bool = field(default=False, init=False, repr=False)

    def __post_init__(self):
        self._anchor_tokens = _tokens(self.goal_anchor)
        self._anchor_text = self.goal_anchor
        # Resolve endpoint from env if caller didn't pass one. Empty string
        # is treated as "off" (no-op). Live agent.py constructs WilsonLoop
        # without this kwarg, so today's default path is env-driven only.
        if self.embedding_endpoint is None:
            self.embedding_endpoint = os.environ.get("TSUNAMI_EMBED_ENDPOINT", "") or None
        # Warm the anchor embedding ONCE at construction. If the server
        # doesn't support embeddings, _anchor_embed stays None and every
        # probe takes the token-cosine path without retrying the server.
        if self.embedding_endpoint:
            self._anchor_embed = _embed(
                self.embedding_endpoint, self._anchor_text, self.embed_timeout_sec
            )
            if self._anchor_embed is None:
                log.warning(
                    f"wilson_loop: embedding_endpoint={self.embedding_endpoint} "
                    f"unreachable or lacks /v1/embeddings; falling back to token cosine"
                )
                # Null out so probe() skips embed attempts entirely — avoids
                # repeated 2s timeouts per probe when the server is down.
                self.embedding_endpoint = None
        log.warning(
            f"wilson_loop: anchored on {len(self._anchor_tokens)} content tokens "
            f"(probe_every={self.probe_every}, drift_threshold={self.drift_threshold}, "
            f"embed={'on' if self._anchor_embed is not None else 'off'})"
        )

    def should_probe(self, iter_n: int) -> bool:
        """True if iter_n is a probe iteration. Cheap predicate for the hot loop."""
        return iter_n > 0 and iter_n % self.probe_every == 0

    def probe(self, iter_n: int, intent_text: str) -> Probe:
        """Take a probe at iter_n. Caller synthesizes intent_text from state.

        Returns the Probe (caller may inspect ``probe.holonomy``). Side effect:
        appends to internal trajectory and may fire ``on_drift``.

        Path selection:
            - If ``embedding_endpoint`` was set and the anchor embedding
              succeeded at construction, try real vector cosine. On any
              per-probe failure (timeout, 501, malformed response), fall
              through to token cosine WITHOUT disabling future attempts —
              transient failures shouldn't lose telemetry for the session.
            - Otherwise (default), token cosine. Byte-identical to v1.
        """
        toks = _tokens(intent_text)
        sim: float | None = None
        src = "tokens"
        if self.embedding_endpoint is not None and self._anchor_embed is not None:
            vec = _embed(self.embedding_endpoint, intent_text, self.embed_timeout_sec)
            if vec is not None:
                sim = _vec_cosine(vec, self._anchor_embed)
                src = "embed"
        if sim is None:
            sim = _cosine(toks, self._anchor_tokens)
        holonomy = 1.0 - sim
        p = Probe(
            iter_n=iter_n,
            text=intent_text[:200],
            tokens=toks,
            holonomy=holonomy,
            src=src,
        )
        self._probes.append(p)
        # log.warning during v1 telemetry window — default Python log level
        # filters INFO; this is what makes the metric visible. Demote to .info
        # once the metric graduates to interventions and we don't need the
        # raw signal in eval logs anymore.
        log.warning(
            f"wilson_loop: probe iter={iter_n} src={src} sim={sim:.3f} "
            f"holonomy={holonomy:.3f} (consec_drift={self._consecutive_drift}, "
            f"anchor_overlap={len(toks & self._anchor_tokens)})"
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
