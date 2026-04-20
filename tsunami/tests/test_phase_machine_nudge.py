"""Phase-machine WRITE-phase nudge thresholds.

Regression target: SURGE v1 spent 8+ iterations without writing files;
the old nudge only fired at iter 8 with soft "call file_write NOW" text
that the drone ignored. We lowered the threshold to 5 and strengthened
the copy to explicitly say "STOP generating images, missing images fine".

These tests verify:
  - no nudge at iters 0-4 (let the model work)
  - write-stall nudge fires at iter 5+ with files_written == 0
  - compile nudge fires after any write, once iters_in_phase >= 6
  - nudge text includes the key behavior instructions
"""

import pytest

from tsunami.phase_machine import PhaseMachine, Phase


def _in_write(iters: int, files_written: int) -> PhaseMachine:
    pm = PhaseMachine()
    pm.phase = Phase.WRITE
    pm.iters_in_phase = iters
    pm.files_written = files_written
    return pm


class TestWriteStallNudge:
    @pytest.mark.parametrize("iters", [0, 1, 2, 3, 4])
    def test_below_threshold_silent(self, iters: int):
        pm = _in_write(iters=iters, files_written=0)
        assert pm.context_note() is None, f"fired too early at iter {iters}"

    def test_fires_at_five(self):
        pm = _in_write(iters=5, files_written=0)
        note = pm.context_note()
        assert note is not None
        assert "5 iterations" in note
        assert "STOP generating images" in note, "nudge must be hard, not advisory"
        assert "file_write" in note

    def test_fires_above_five(self):
        pm = _in_write(iters=9, files_written=0)
        note = pm.context_note()
        assert note is not None
        assert "STOP generating images" in note

    def test_not_fired_if_file_written(self):
        """If the drone already wrote something, the WRITE-stall branch doesn't
        fire — instead the compile-reminder branch can (once iters are enough)."""
        pm = _in_write(iters=5, files_written=1)
        note = pm.context_note()
        # Fewer than 6 iters, so even compile branch silent.
        assert note is None

    def test_compile_reminder_after_write(self):
        pm = _in_write(iters=7, files_written=1)
        note = pm.context_note()
        assert note is not None
        assert "compile" in note.lower() or "vite build" in note


class TestWriteStallMessage:
    """The copy itself — make sure the critical directives didn't regress."""

    def test_mentions_broken_img_is_fine(self):
        pm = _in_write(iters=5, files_written=0)
        note = pm.context_note() or ""
        # "broken" or "missing" phrasing that tells the drone shipping wins.
        assert ("broken" in note.lower()) or ("missing" in note.lower())

    def test_does_not_claim_unlimited_iters(self):
        """The fix must not accidentally encourage further image generation."""
        pm = _in_write(iters=5, files_written=0)
        note = pm.context_note() or ""
        assert "generate more images" not in note.lower()
