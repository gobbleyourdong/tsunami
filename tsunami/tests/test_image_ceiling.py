"""Image-ceiling nudge — tsunami/agent.py fires a hard "STOP generating images"
system-note when the drone has issued 5+ `generate_image` calls without any
intervening `file_write` / `file_edit`. Regression target: SURGE v1 spent 11
turns on images before writing App.tsx; the 3-in-a-row nudge fired but was
advisory and got ignored.

These tests cover the pure counting logic in isolation — they don't spin up
a real agent, they just replicate the inline loop in agent.py (scan
_tool_history in reverse, stop at a write, count generate_image on the way).
"""

import pytest


def _count_images_since_write(tool_history: list[str]) -> int:
    """Mirror of the counter in agent.py. Returns how many generate_image
    calls sit at the tail of the history before the most recent write."""
    count = 0
    for t in reversed(tool_history):
        if t in ("file_write", "file_edit"):
            break
        if t == "generate_image":
            count += 1
    return count


class TestImageCeilingCounter:
    def test_no_history_no_count(self):
        assert _count_images_since_write([]) == 0

    def test_only_non_image_tools(self):
        assert _count_images_since_write(["search_web", "file_read", "shell_exec"]) == 0

    def test_single_image(self):
        assert _count_images_since_write(["generate_image"]) == 1

    def test_five_images_in_a_row(self):
        h = ["generate_image"] * 5
        assert _count_images_since_write(h) == 5

    def test_eleven_images_surge_pattern(self):
        """The SURGE regression case — 11 images before ever writing."""
        h = ["generate_image"] * 11
        assert _count_images_since_write(h) == 11

    def test_write_resets_count(self):
        """After file_write, the counter starts fresh from the tail."""
        h = ["generate_image", "generate_image", "file_write", "generate_image"]
        assert _count_images_since_write(h) == 1

    def test_file_edit_also_resets(self):
        h = ["generate_image", "generate_image", "file_edit", "generate_image", "generate_image"]
        assert _count_images_since_write(h) == 2

    def test_interleaved_tools_still_counted(self):
        """file_read, shell_exec between images don't reset — only writes do."""
        h = ["generate_image", "file_read", "generate_image", "shell_exec", "generate_image"]
        assert _count_images_since_write(h) == 3

    def test_write_at_tail_zero_count(self):
        """If the very last tool was a write, nothing has happened since."""
        h = ["generate_image", "generate_image", "file_write"]
        assert _count_images_since_write(h) == 0

    def test_many_writes_then_images(self):
        """Multiple writes — counter only looks back to the most recent one."""
        h = ["generate_image", "file_write", "generate_image", "generate_image", "file_write", "generate_image"]
        assert _count_images_since_write(h) == 1


class TestImageCeilingThreshold:
    """The threshold itself — at 5+ images-since-write, the nudge should fire."""

    THRESHOLD = 5

    @pytest.mark.parametrize("count", [0, 1, 2, 3, 4])
    def test_below_threshold_no_fire(self, count: int):
        h = ["generate_image"] * count
        assert _count_images_since_write(h) < self.THRESHOLD

    @pytest.mark.parametrize("count", [5, 6, 7, 11])
    def test_at_or_above_threshold_fires(self, count: int):
        h = ["generate_image"] * count
        assert _count_images_since_write(h) >= self.THRESHOLD

    def test_threshold_crossed_only_after_write_stale(self):
        """After the nudge has fired and the drone still loops (shouldn't), the
        counter is cumulative until a write arrives. A further generate_image
        keeps the count above threshold."""
        h = ["generate_image"] * 5 + ["generate_image"]
        assert _count_images_since_write(h) == 6

    def test_recovery_after_write(self):
        """Post-write, the drone is allowed a fresh burst before the ceiling
        re-arms. Verifies the design (latch reset on file_write)."""
        h = ["generate_image"] * 5 + ["file_write"] + ["generate_image"] * 2
        assert _count_images_since_write(h) == 2


def _latch_should_reset(tool_history: list[str]) -> bool:
    """Mirror of the recent-window check in agent.py after MIRA v6 fix."""
    if not tool_history:
        return False
    recent = tool_history[-3:]
    return any(t in ("file_write", "file_edit") for t in recent)


class TestLatchResetMasking:
    """Regression: MIRA audit v6 showed that auto-build appends a synthetic
    'shell_exec' after each drone file_write. If the latch reset only looked
    at tool_history[-1], it missed the file_write signal and the image
    ceiling stayed stuck. Fix scans the last 3 entries."""

    def test_reset_on_immediate_file_write(self):
        assert _latch_should_reset(["file_write"])

    def test_reset_when_autobuild_appended_shell_exec(self):
        """file_write followed by synthetic shell_exec must still reset."""
        assert _latch_should_reset(["file_write", "shell_exec"])

    def test_reset_when_file_edit_at_tail(self):
        assert _latch_should_reset(["shell_exec", "file_edit"])

    def test_no_reset_when_writes_are_stale(self):
        """Writes older than the 3-entry window must not trigger reset."""
        h = ["file_write", "generate_image", "generate_image", "generate_image"]
        assert not _latch_should_reset(h)

    def test_no_reset_when_only_reads(self):
        assert not _latch_should_reset(["file_read", "shell_exec", "generate_image"])

    def test_no_reset_on_empty_history(self):
        assert not _latch_should_reset([])

    def test_autobuild_plus_another_tool_still_resets(self):
        """file_write then auto-build shell_exec then generate_image attempt:
        at the attempt's turn-start, last 3 include file_write so reset."""
        h = ["file_write", "shell_exec", "generate_image"]
        assert _latch_should_reset(h)
