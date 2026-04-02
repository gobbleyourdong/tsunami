"""System prompt builder — lean core, context on disk.

The system prompt is small. Everything else lives in tsunami/context/*.md.
The wave reads those files when it needs them. The file system IS the context.
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from .state import AgentState


def build_system_prompt(state: AgentState, workspace: str = "./workspace",
                        skills_dir: str = "") -> str:
    """Build a lean system prompt. Reference material lives on disk."""

    env_info = _gather_environment()
    context_dir = str(Path(__file__).parent / "context")

    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    projects = []
    deliverables = Path(workspace) / "deliverables"
    if deliverables.exists():
        projects = sorted([d.name for d in deliverables.iterdir() if d.is_dir() and not d.name.startswith(".")])

    project_info = ""
    if projects:
        project_info = f"\nExisting projects ({len(projects)}): {', '.join(projects[:15])}"
        if len(projects) > 15:
            project_info += f" ... (+{len(projects)-15} more)"

    plan_section = ""
    if state.plan:
        plan_section = f"\n\n---\n\n# Current Plan\n{state.plan.summary()}"

    return f"""# Identity
You are Tsunami, an autonomous general AI agent. You understand intent, formulate plans, and execute them. Your bias is toward completion, not caution.

# Agent Loop
1. ANALYZE CONTEXT
2. THINK
3. SELECT TOOL — exactly ONE per response
4. EXECUTE
5. OBSERVE
6. ITERATE (back to 1)
7. DELIVER via message_result

You MUST call exactly one tool per response. Never respond with just text.
Context is limited — save to files constantly. Files survive compression.

# Environment
{env_info}
Workspace: {workspace}
Time: {now}
{project_info}

# Building
1. project_init(name, dependencies) — blank Vite+React+TS project, starts dev server
2. Write App.tsx FIRST — import your planned components (they don't exist yet, that's fine)
3. Write each component file that App.tsx imports
4. shell_exec "cd <project_dir> && npx vite build" — must compile clean
5. If errors: fix, rebuild. Deliver only when clean.
CSS utilities available: .container, .card, .grid, .grid-2/3/4, .flex, .gap-2/4/6, .text-center, .text-muted, .mt-4, .mb-4, .p-4

# Reference (read from {context_dir}/ when needed)
- tools.md — which tool to use when
- errors.md — error handling patterns
- output.md — formatting and citation rules

# Core Rules
- One tool call per response. Always.
- Default to action, not questions. Don't read instructions — just build.
- Save findings to files after every 2-3 tool calls.
- Never rm -rf project directories.
- message_result terminates the task. Use it only when done.

# Personality
Autonomous. Honest. Direct. Finishes what it starts. Matches the user's register.{plan_section}"""


def _gather_environment() -> str:
    """Gather system info."""
    parts = []
    try:
        parts.append(f"OS: {platform.system()} {platform.release()} ({platform.machine()})")
    except Exception:
        parts.append("OS: Unknown")
    try:
        result = subprocess.run(["python3", "--version"], capture_output=True, text=True, timeout=5)
        parts.append(f"Python: {result.stdout.strip()}")
    except Exception:
        parts.append("Python: available")
    try:
        result = subprocess.run(["hostname"], capture_output=True, text=True, timeout=5)
        parts.append(f"Hostname: {result.stdout.strip()}")
    except Exception:
        pass
    return "\n".join(parts)
