"""Tests for WilsonLoop telemetry + v2 embedding fallback.

Covers the debt entry for `0c34e8c` (REVIEW NEEDED): the embedding swap
must be a *non-breaking* upgrade path. When no embeddings endpoint is
reachable, every probe still emits the v1 token-set cosine telemetry.
"""

from __future__ import annotations

from tsunami.wilson_loop import (
    WilsonLoop,
    _cosine,
    _embed,
    _tokens,
    _vec_cosine,
    synthesize_intent,
)


class TestTokenCosineFallback:
    """v1 behavior must be preserved when embedding endpoint is absent."""

    def test_default_construction_uses_tokens(self):
        """agent.py's call site — WilsonLoop(goal_anchor=...) — stays on tokens."""
        w = WilsonLoop(goal_anchor="build a pomodoro timer")
        p = w.probe(15, "file_write App.tsx pomodoro timer")
        assert p.src == "tokens"
        assert 0.0 <= p.holonomy <= 1.0

    def test_empty_endpoint_uses_tokens(self):
        """Explicit empty string is treated as off."""
        w = WilsonLoop(goal_anchor="counter app", embedding_endpoint="")
        # Empty is falsy; post_init should read env var (absent in test env).
        assert w.embedding_endpoint is None or w.embedding_endpoint == ""
        p = w.probe(15, "counter increment")
        assert p.src == "tokens"

    def test_unreachable_endpoint_falls_back(self):
        """Bad endpoint nulls at construction; probes never retry."""
        w = WilsonLoop(
            goal_anchor="clock display",
            embedding_endpoint="http://127.0.0.1:1",  # port 1, always refused
            embed_timeout_sec=0.5,
        )
        assert w.embedding_endpoint is None
        assert w._anchor_embed is None
        p = w.probe(15, "clock tick")
        assert p.src == "tokens"


class TestVecCosine:
    """Pure-function correctness for the dense-vector cosine."""

    def test_identical_vectors(self):
        assert _vec_cosine([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0

    def test_orthogonal(self):
        assert _vec_cosine([1.0, 0.0], [0.0, 1.0]) == 0.0

    def test_empty_inputs(self):
        assert _vec_cosine([], []) == 0.0
        assert _vec_cosine([1.0], []) == 0.0

    def test_length_mismatch(self):
        assert _vec_cosine([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0

    def test_zero_norm(self):
        assert _vec_cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


class TestEmbedHelper:
    """_embed must swallow all network/parse failures into None."""

    def test_empty_endpoint(self):
        assert _embed("", "hello") is None

    def test_empty_text(self):
        assert _embed("http://127.0.0.1:1", "") is None

    def test_connection_refused(self):
        # Port 1 is reliably closed on Linux.
        assert _embed("http://127.0.0.1:1", "hello", timeout=0.5) is None


class TestProbeTrajectory:
    """Trajectory, holonomy accumulation, and drift firing stay v1-correct."""

    def test_trajectory_appends(self):
        w = WilsonLoop(goal_anchor="pomodoro timer")
        for i in range(1, 4):
            w.probe(i * 15, f"iter {i}")
        assert len(w.trajectory()) == 3

    def test_drift_fires_after_consecutive(self):
        fired = []
        w = WilsonLoop(
            goal_anchor="pomodoro timer countdown",
            drift_threshold=0.1,
            consecutive_drift_to_fire=2,
            on_drift=lambda wl, pr: fired.append(pr.iter_n),
        )
        # Both probes are orthogonal content → holonomy ~1.0 > 0.1.
        w.probe(15, "unrelated database query language")
        w.probe(30, "unrelated cryptography elliptic curve")
        assert fired == [30]

    def test_drift_streak_resets_on_clean_probe(self):
        fired = []
        w = WilsonLoop(
            goal_anchor="counter app increment button display",
            drift_threshold=0.5,
            consecutive_drift_to_fire=2,
            on_drift=lambda wl, pr: fired.append(pr.iter_n),
        )
        # Probe 1: off-topic → drift counter 1
        w.probe(15, "unrelated alpha beta gamma delta")
        # Probe 2: full anchor echo → holonomy 0 (cos=1), resets streak
        w.probe(30, "counter app increment button display")
        # Probe 3: off-topic again → drift counter 1 (not 2), no fire
        w.probe(45, "unrelated epsilon zeta eta theta")
        assert fired == [], f"should not fire after reset, got {fired}"


class TestSynthesizeIntent:
    """String-args-only synthesis is preserved."""

    def test_concatenates_tool_calls(self):
        calls = [
            ("file_write", {"path": "App.tsx", "content": "export default"}),
            ("shell_exec", {"cmd": "npm run build"}),
        ]
        s = synthesize_intent(calls, "Ready to deliver")
        assert "file_write" in s
        assert "shell_exec" in s
        assert "Ready to deliver" in s

    def test_skips_non_string_args(self):
        calls = [("tool_x", {"n": 42, "path": "x.ts"})]
        s = synthesize_intent(calls)
        assert "path=x.ts" in s
        assert "n=" not in s  # numeric arg skipped


class TestLogFormat:
    """Log line must include src= tag so eval logs are greppable."""

    def test_src_in_log(self, caplog):
        import logging

        caplog.set_level(logging.INFO, logger="tsunami.wilson_loop")
        w = WilsonLoop(goal_anchor="counter")
        w.probe(15, "counter increment")
        assert any("src=tokens" in rec.message for rec in caplog.records), (
            f"expected src=tokens marker; got {[r.message for r in caplog.records]}"
        )


class TestCosine:
    """v1 token-set cosine regression guards."""

    def test_identity(self):
        assert _cosine({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint(self):
        assert _cosine({"a"}, {"b"}) == 0.0

    def test_empty(self):
        assert _cosine(set(), {"a"}) == 0.0

    def test_tokens_drops_stopwords(self):
        toks = _tokens("The agent and the tool built a counter")
        assert "counter" in toks
        assert "the" not in toks
        assert "agent" not in toks  # in _STOP per wilson_loop.py
