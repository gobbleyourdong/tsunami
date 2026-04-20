"""Guard against placeholder-text regression in the agent-synth deliver
bypass. 2026-04-20 ORBIT v5 + MIRA v6 both shipped with a hardcoded
'Pomodoro timer' string that was left over from testing. The synth text
should be grounded in the actual project name instead of a canned phrase.
"""

import pathlib


AGENT_SRC = (pathlib.Path(__file__).parent.parent / "agent.py").read_text()


class TestNoPlaceholderStrings:
    def test_no_pomodoro_synth_string(self):
        """The 'Pomodoro timer with start/pause/reset' placeholder must not
        appear outside of a comment. Running text of any synth_args would
        reintroduce the bug."""
        for line in AGENT_SRC.splitlines():
            stripped = line.strip()
            # Skip comments.
            if stripped.startswith("#"):
                continue
            assert "Pomodoro timer with start" not in line, (
                "Placeholder text found in non-comment line. Regression of "
                "the 2026-04-20 ORBIT v5 / MIRA v6 bug where every agent-"
                "synth delivery shipped with 'Pomodoro timer' as its text."
            )

    def test_synth_uses_deliverables_path(self):
        """The synth path must reference deliverables/<name> so eval logs
        can tell where the build landed."""
        assert "deliverables/{_proj_name}" in AGENT_SRC or \
               'f"deliverables/{_proj_name}"' in AGENT_SRC

    def test_synth_marks_itself_as_agent_synth(self):
        """The synth text should say 'agent-synthesized' so downstream
        tools and humans can distinguish it from a drone-chosen delivery."""
        assert "agent-synthesized" in AGENT_SRC
