"""Task decomposer — break complex prompts into a dependency DAG.

Complex multi-domain prompts ("weather + stocks dashboard") stall because the
9B can't decide what to do first. The decomposer detects multi-part prompts
and splits them into sequential sub-tasks that the agent executes one at a time.

This is the coordinator pattern from open-multi-agent, adapted for Tsunami's
single-agent loop: instead of dispatching to multiple agents, we rewrite the
prompt into a phased plan that the agent follows step by step.

Detection heuristics:
- Multiple nouns connected by "and", "+", "with", commas
- Feature lists (3+ features in one prompt)
- Multi-domain keywords (charts AND forms AND search)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger("tsunami.task_decomposer")

# Domain keywords that indicate distinct subsystems
DOMAIN_KEYWORDS = {
    "chart": "data_viz",
    "graph": "data_viz",
    "analytics": "data_viz",
    "recharts": "data_viz",
    "d3": "data_viz",
    "plot": "data_viz",
    "dashboard": "data_viz",
    "form": "forms",
    "input": "forms",
    "upload": "forms",
    "crud": "persistence",
    "database": "persistence",
    "save": "persistence",
    "login": "persistence",
    "auth": "persistence",
    "search": "search",
    "filter": "search",
    "sort": "search",
    "chat": "realtime",
    "websocket": "realtime",
    "live": "realtime",
    "realtime": "realtime",
    "calendar": "calendar",
    "date": "calendar",
    "schedule": "calendar",
    "drag": "interactive",
    "drop": "interactive",
    "kanban": "interactive",
    "board": "interactive",
    "weather": "api_external",
    "stock": "api_external",
    "currency": "api_external",
    "api": "api_external",
    "3d": "3d",
    "three": "3d",
    "orbit": "3d",
    "physics": "physics",
    "collision": "physics",
    "matter": "physics",
}


@dataclass
class SubTask:
    """A single step in the decomposed plan."""
    id: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    domain: str = ""


@dataclass
class TaskDAG:
    """Directed acyclic graph of sub-tasks."""
    original_prompt: str
    tasks: list[SubTask]
    is_complex: bool = False

    def to_phased_prompt(self) -> str:
        """Convert the DAG into a phased prompt for the agent.

        Instead of dispatching to multiple agents, we rewrite the prompt
        so the agent builds one section at a time.
        """
        if not self.is_complex:
            return self.original_prompt

        lines = [
            "Build this project in phases. Complete each phase before moving to the next.",
            f"Final goal: {self.original_prompt}",
            "",
        ]

        for i, task in enumerate(self.tasks):
            phase_num = i + 1
            lines.append(f"Phase {phase_num}: {task.description}")

        lines.append("")
        lines.append("Start with Phase 1 NOW. Call project_init first, then write code for Phase 1.")
        lines.append("Do NOT research or plan further. BUILD.")

        return "\n".join(lines)


def detect_domains(prompt: str) -> set[str]:
    """Detect which domains a prompt touches."""
    prompt_lower = prompt.lower()
    domains = set()
    for keyword, domain in DOMAIN_KEYWORDS.items():
        if keyword in prompt_lower:
            domains.add(domain)
    return domains


def is_complex_prompt(prompt: str) -> bool:
    """Detect if a prompt is complex enough to need decomposition.

    Complex = touches 3+ domains, or has 4+ distinct features listed.
    """
    domains = detect_domains(prompt)
    if len(domains) >= 3:
        return True

    # Count feature-like phrases (separated by commas, "and", periods, or list markers)
    features = re.split(r',\s*|\band\b|\.\s+|\n-\s*|\n\d+\.\s*', prompt)
    features = [f.strip() for f in features if len(f.strip()) > 10]
    if len(features) >= 4:
        return True

    # Long prompts with 2+ domains are also complex
    if len(domains) >= 2 and len(prompt) > 150:
        return True

    return False


def decompose(prompt: str) -> TaskDAG:
    """Decompose a prompt into a task DAG.

    For simple prompts, returns a single-task DAG (no decomposition).
    For complex prompts, splits into phases with dependencies.
    """
    if not is_complex_prompt(prompt):
        return TaskDAG(
            original_prompt=prompt,
            tasks=[SubTask(id="t1", description=prompt)],
            is_complex=False,
        )

    domains = detect_domains(prompt)
    tasks = []

    # Phase 1 is always scaffold + basic structure
    tasks.append(SubTask(
        id="scaffold",
        description="Scaffold the project and create the basic layout (header, navigation, main content area). Get it compiling.",
        domain="structure",
    ))

    # Generate phases from detected domains
    phase_descriptions = {
        "data_viz": "Add charts and data visualization (use recharts or canvas). Mock data is fine.",
        "forms": "Add form inputs, validation, and data entry UI.",
        "persistence": "Add data persistence (localStorage or in-memory state management).",
        "search": "Add search and filtering functionality.",
        "realtime": "Add real-time features (WebSocket or polling simulation).",
        "calendar": "Add calendar/date components and scheduling UI.",
        "interactive": "Add drag-and-drop, sortable, or interactive board features.",
        "api_external": "Add external data display (use mock/simulated data, not real APIs).",
        "3d": "Add 3D scene setup with Three.js (camera, lighting, objects).",
        "physics": "Add physics simulation (collision, gravity, forces).",
    }

    for domain in sorted(domains):
        desc = phase_descriptions.get(domain, f"Add {domain} features.")
        tasks.append(SubTask(
            id=f"phase_{domain}",
            description=desc,
            depends_on=["scaffold"],
            domain=domain,
        ))

    # Final phase: wire everything together
    tasks.append(SubTask(
        id="integrate",
        description="Wire all sections together. Verify it compiles. Fix any import errors. Deliver.",
        depends_on=[t.id for t in tasks[1:]],  # depends on all feature phases
        domain="integration",
    ))

    log.info(f"Decomposed prompt into {len(tasks)} phases ({len(domains)} domains: {domains})")

    return TaskDAG(
        original_prompt=prompt,
        tasks=tasks,
        is_complex=True,
    )
