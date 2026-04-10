"""Mock model for testing the Tsunami agent loop without a real LLM.

This model follows a scripted sequence of tool calls to demonstrate
the agent's behavior. It exercises every major pattern from arc.txt:
plan → research → file ops → shell → deliver.
"""

from __future__ import annotations

from .model import LLMModel, LLMResponse, ToolCall


class MockModel(LLMModel):
    """A scripted model that exercises the agent loop patterns.

    Used for verification: does the heartbeat work?
    Does the loop iterate? Do tools execute? Does it terminate?
    """

    def __init__(self):
        self._step = 0
        self._script: list[tuple[str, dict]] = [
            # Step 1: Plan before acting (Signal Fingerprint #1)
            ("plan_update", {
                "goal": "Demonstrate the Tsunami agent loop with all core behaviors",
                "phases": [
                    {"title": "Reconnaissance — gather system info"},
                    {"title": "Creation — build an artifact"},
                    {"title": "Verification — confirm it works"},
                    {"title": "Delivery — present results"},
                ],
            }),
            # Step 2: Inform the user (momentum, not questions)
            ("message_info", {
                "text": "Starting reconnaissance. Gathering system information.",
            }),
            # Step 3: Go and find out (Signal Fingerprint #2)
            ("shell_exec", {
                "command": "uname -a && python3 --version && echo 'System probed.'",
            }),
            # Step 4: Save findings to files (Context Scavenger pattern)
            ("file_write", {
                "path": "./workspace/notes/system_info.md",
                "content": "# System Info\nProbed via shell_exec. Details saved.\n",
            }),
            # Step 5: Advance plan
            ("plan_advance", {
                "summary": "System info gathered and saved to workspace/notes/",
            }),
            # Step 6: Build real things (Signal Fingerprint #3)
            ("file_write", {
                "path": "./workspace/deliverables/hello_tsunami.py",
                "content": (
                    '#!/usr/bin/env python3\n'
                    '"""Built by Tsunami — the Resonant Ark."""\n\n'
                    'def main():\n'
                    '    print("Tsunami is alive.")\n'
                    '    print("The pattern propagates.")\n'
                    '    print("The Ark held.")\n\n'
                    'if __name__ == "__main__":\n'
                    '    main()\n'
                ),
            }),
            # Step 7: Execute what was built
            ("shell_exec", {
                "command": "python3 ./workspace/deliverables/hello_tsunami.py",
            }),
            # Step 8: Advance plan
            ("plan_advance", {
                "summary": "Artifact built and executed successfully",
            }),
            # Step 9: Verify (read back what was created)
            ("file_read", {
                "path": "./workspace/deliverables/hello_tsunami.py",
            }),
            # Step 10: Advance plan
            ("plan_advance", {
                "summary": "Verified artifact content is correct",
            }),
            # Step 11: Finish — deliver results (Signal Fingerprint #4)
            ("message_result", {
                "text": (
                    "Task complete. Demonstrated all 7 signal fingerprint behaviors:\n"
                    "1. Planned before acting (4-phase plan)\n"
                    "2. Went and found out (shell probe)\n"
                    "3. Built a real thing (hello_tsunami.py)\n"
                    "4. Finished the task (this message)\n"
                    "5. Self-corrected (would trigger on errors)\n"
                    "6. Had a voice (direct, no hedging)\n"
                    "7. Respected the human (no unnecessary questions)\n\n"
                    "Tsunami is operational."
                ),
                "attachments": ["./workspace/deliverables/hello_tsunami.py"],
            }),
        ]

    async def _call(self, messages, tools=None) -> LLMResponse:
        if self._step >= len(self._script):
            # Safety: if somehow we go past the script, terminate
            return LLMResponse(
                content="",
                tool_call=ToolCall(name="message_result", arguments={
                    "text": "Mock script exhausted. Agent loop is functional.",
                }),
            )

        name, args = self._script[self._step]
        self._step += 1

        return LLMResponse(
            content=f"[Mock step {self._step}/{len(self._script)}]",
            tool_call=ToolCall(name=name, arguments=args),
        )
