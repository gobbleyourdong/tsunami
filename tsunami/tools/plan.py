"""Plan tools — the architect.

Plan before acting. Plans are living documents.
Phases are sequential. The final phase is always delivery.
"""

from __future__ import annotations

from ..state import Plan, Phase
from .base import BaseTool, ToolResult


# The agent state is injected at runtime by the agent loop
_agent_state = None


def set_agent_state(state):
    global _agent_state
    _agent_state = state


class PlanUpdate(BaseTool):
    name = "plan_update"
    description = "Create or revise the task plan."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "Single sentence describing the desired end state"},
                "phases": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "capabilities": {
                                "type": "array",
                                "items": {"type": "string"},
                                "default": [],
                            },
                        },
                        "required": ["title"],
                    },
                    "description": "Ordered list of phases to accomplish the goal",
                },
            },
            "required": ["goal", "phases"],
        }

    async def execute(self, goal: str, phases: list = None, **kw) -> ToolResult:
        if _agent_state is None:
            return ToolResult("No agent state available", is_error=True)
        if not phases:
            return ToolResult("phases is required", is_error=True)

        plan_phases = []
        for i, p in enumerate(phases, 1):
            # Accept both {"title": "..."} objects and plain strings
            if isinstance(p, str):
                title = p
                capabilities = []
            else:
                title = p.get("title", str(p))
                capabilities = p.get("capabilities", [])
            plan_phases.append(Phase(
                id=i,
                title=title,
                capabilities=capabilities,
                status="active" if i == 1 else "pending",
            ))

        _agent_state.plan = Plan(goal=goal, phases=plan_phases, current_phase=1)
        _agent_state.save_plan(_agent_state.workspace / "plans")

        return ToolResult(f"Plan created: {goal}\n{_agent_state.plan.summary()}")


class PlanAdvance(BaseTool):
    name = "plan_advance"
    description = "Mark current phase complete and move to the next."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Brief summary of what was accomplished in this phase"},
            },
            "required": ["summary"],
        }

    async def execute(self, summary: str = "", **kw) -> ToolResult:
        if _agent_state is None or _agent_state.plan is None:
            return ToolResult("No active plan", is_error=True)

        # ECC pattern: write structured handoff between phases
        current = _agent_state.plan.phases[_agent_state.plan.current_phase - 1] \
            if _agent_state.plan.current_phase <= len(_agent_state.plan.phases) else None
        handoff_note = ""
        if current and summary:
            handoff_note = f"\n\nHandoff from Phase {current.id} ({current.title}):\n- Completed: {summary}"

        next_phase = _agent_state.plan.advance()
        _agent_state.save_plan(_agent_state.workspace / "plans")

        if next_phase:
            return ToolResult(
                f"Phase complete: {summary}\n"
                f"Now entering: Phase {next_phase.id} — {next_phase.title}"
                f"{handoff_note}\n\n"
                f"{_agent_state.plan.summary()}"
            )
        else:
            return ToolResult(
                f"Phase complete: {summary}\n"
                f"ALL PHASES COMPLETE. Deliver results to user via message_result."
            )
