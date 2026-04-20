"""L5 HARD-enforce layer: when _image_ceiling_fired is True, subsequent
generate_image calls should be rejected at the tool exec site.

Regression target: ORBIT audit v5 (2026-04-20) observed the drone
continuing to call generate_image AFTER the L5 system-note told it to
stop. The advisory copy alone wasn't enough — drone chose to ignore it.
This tests the pure-logic decision the exec site makes.
"""

import pytest


def _should_block(tool_name: str, ceiling_fired: bool) -> bool:
    """Mirror of the inline check in agent.py line ~3055."""
    return tool_name == "generate_image" and ceiling_fired


class TestImageCeilingHardBlock:
    def test_blocks_generate_image_when_ceiling_fired(self):
        assert _should_block("generate_image", ceiling_fired=True)

    def test_allows_generate_image_when_ceiling_not_fired(self):
        assert not _should_block("generate_image", ceiling_fired=False)

    def test_never_blocks_non_image_tools(self):
        """file_write / shell_exec / etc. must always pass, even with
        ceiling latched — otherwise the drone can never recover."""
        for t in ("file_write", "file_edit", "shell_exec", "message_result", "file_read"):
            assert not _should_block(t, ceiling_fired=True)

    def test_reject_message_contains_recovery_path(self):
        """The reject message in agent.py must tell the drone HOW to clear
        the block (call file_write). Verify the contract here so if the
        copy regresses a meta-test catches it."""
        # Import the source text to assert substring presence.
        import pathlib
        agent_src = pathlib.Path(__file__).parent.parent / "agent.py"
        text = agent_src.read_text()
        assert "IMAGE CEILING ENFORCED" in text
        assert "file_write on src/App.tsx" in text
        assert "ceiling resets after any file_write" in text

    @pytest.mark.parametrize("tool,fired,expect", [
        ("generate_image", True, True),
        ("generate_image", False, False),
        ("file_write", True, False),
        ("file_write", False, False),
        ("shell_exec", True, False),
    ])
    def test_truth_table(self, tool, fired, expect):
        assert _should_block(tool, fired) is expect
