"""Tests for WilsonLoop telemetry + v2 embedding fallback.

Covers the debt entry for `0c34e8c` (REVIEW NEEDED): the embedding swap
must be a *non-breaking* upgrade path. When no embeddings endpoint is
reachable, every probe still emits the v1 token-set cosine telemetry.
"""

from __future__ import annotations

from tsunami.wilson_loop import (
    WilsonLoop,
    _DEFAULT_EMBED_TIMEOUT_SEC,
    _cosine,
    _embed,
    _resolve_embed_timeout_sec,
    _tokens,
    _vec_cosine,
    synthesize_intent_from_messages,
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


class TestEmbedTimeoutEnv:
    """Pins the env-var contract for ``TSUNAMI_EMBED_TIMEOUT_SEC`` — the
    principled replacement for e5d0620's hard-coded 10.0. Kept defensive:
    this is observability infra and must never crash agent construction
    on a malformed env value."""

    def test_unset_uses_default(self, monkeypatch):
        monkeypatch.delenv("TSUNAMI_EMBED_TIMEOUT_SEC", raising=False)
        assert _resolve_embed_timeout_sec() == _DEFAULT_EMBED_TIMEOUT_SEC

    def test_empty_string_uses_default(self, monkeypatch):
        monkeypatch.setenv("TSUNAMI_EMBED_TIMEOUT_SEC", "")
        assert _resolve_embed_timeout_sec() == _DEFAULT_EMBED_TIMEOUT_SEC

    def test_valid_float_overrides(self, monkeypatch):
        monkeypatch.setenv("TSUNAMI_EMBED_TIMEOUT_SEC", "2.5")
        assert _resolve_embed_timeout_sec() == 2.5

    def test_valid_int_string_overrides(self, monkeypatch):
        monkeypatch.setenv("TSUNAMI_EMBED_TIMEOUT_SEC", "30")
        assert _resolve_embed_timeout_sec() == 30.0

    def test_whitespace_tolerated(self, monkeypatch):
        monkeypatch.setenv("TSUNAMI_EMBED_TIMEOUT_SEC", "  5.0  ")
        assert _resolve_embed_timeout_sec() == 5.0

    def test_unparseable_falls_back(self, monkeypatch):
        monkeypatch.setenv("TSUNAMI_EMBED_TIMEOUT_SEC", "fast")
        assert _resolve_embed_timeout_sec() == _DEFAULT_EMBED_TIMEOUT_SEC

    def test_zero_falls_back(self, monkeypatch):
        """Zero would disable the request entirely; reject it."""
        monkeypatch.setenv("TSUNAMI_EMBED_TIMEOUT_SEC", "0")
        assert _resolve_embed_timeout_sec() == _DEFAULT_EMBED_TIMEOUT_SEC

    def test_negative_falls_back(self, monkeypatch):
        monkeypatch.setenv("TSUNAMI_EMBED_TIMEOUT_SEC", "-3.0")
        assert _resolve_embed_timeout_sec() == _DEFAULT_EMBED_TIMEOUT_SEC

    def test_constructor_default_reads_env(self, monkeypatch):
        """The dataclass field uses default_factory=_resolve_embed_timeout_sec,
        so env changes at construction time should land on the instance."""
        monkeypatch.setenv("TSUNAMI_EMBED_TIMEOUT_SEC", "4.2")
        w = WilsonLoop(goal_anchor="x")
        assert w.embed_timeout_sec == 4.2

    def test_explicit_kwarg_wins_over_env(self, monkeypatch):
        """Explicit construction arg still takes precedence — the env var
        is a default, not a forced override."""
        monkeypatch.setenv("TSUNAMI_EMBED_TIMEOUT_SEC", "4.2")
        w = WilsonLoop(goal_anchor="x", embed_timeout_sec=0.5)
        assert w.embed_timeout_sec == 0.5


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


class TestSynthesizeIntentFromMessages:
    """Pins the post-835d238 contract: intent is built from raw message
    contents rather than reconstructed tool args. The walker takes up to
    ``limit`` recent non-system messages in chronological order."""

    class _Msg:
        """Duck-typed stand-in for the agent's Message dataclass."""

        def __init__(self, role, content):
            self.role = role
            self.content = content

    def test_concatenates_assistant_and_tool_result(self):
        conv = [
            self._Msg("system", "You are Tsunami."),
            self._Msg("user", "build a pomodoro timer"),
            self._Msg("assistant", "I will write App.tsx."),
            self._Msg("tool_result", "[file_write] Wrote 42 lines to App.tsx"),
            self._Msg("assistant", "Now run the build."),
            self._Msg("tool_result", "[shell_exec] BUILD PASSED."),
        ]
        s = synthesize_intent_from_messages(conv)
        assert "I will write App.tsx." in s
        assert "[file_write] Wrote 42 lines to App.tsx" in s
        assert "[shell_exec] BUILD PASSED." in s
        # Order preserved (chronological)
        assert s.index("App.tsx.") < s.index("BUILD PASSED.")
        # System/user messages excluded
        assert "You are Tsunami." not in s
        assert "build a pomodoro timer" not in s

    def test_skips_empty_content(self):
        conv = [
            self._Msg("assistant", ""),
            self._Msg("tool_result", "[file_read] ok"),
            self._Msg("assistant", None),
        ]
        s = synthesize_intent_from_messages(conv)
        assert s == "[file_read] ok"

    def test_limit_takes_most_recent(self):
        conv = [self._Msg("assistant", f"step{i}") for i in range(10)]
        s = synthesize_intent_from_messages(conv, limit=3)
        assert "step9" in s and "step8" in s and "step7" in s
        assert "step6" not in s
        # Chronological: step7 before step9
        assert s.index("step7") < s.index("step9")

    def test_caps_each_content(self):
        conv = [self._Msg("assistant", "x" * 1000)]
        s = synthesize_intent_from_messages(conv, content_cap=50)
        assert len(s) == 50
        assert set(s) == {"x"}

    def test_empty_conversation_returns_empty(self):
        assert synthesize_intent_from_messages([]) == ""

    def test_no_usable_messages_returns_empty(self):
        conv = [self._Msg("system", "hi"), self._Msg("user", "task")]
        assert synthesize_intent_from_messages(conv) == ""


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
