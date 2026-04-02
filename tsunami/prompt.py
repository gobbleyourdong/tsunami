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
   - Call project_init at most ONCE per run unless the user explicitly asks for a second separate project.
   - After project_init succeeds, do not call project_init or webdev_scaffold again for that same project.
2. Write todo.md in the project dir — one checkbox per file you'll write
3. Work through todo.md top to bottom. After writing each file, check it off.
4. Read todo.md each iteration to see what's next.
5. Start App.tsx early with `import "./index.css"` and wire it to the components you plan to build.
6. For 3+ components: use swell to write them in parallel (each gets a prompt + target file path).
   For 1-2 components: write them directly with file_write.
7. Keep App.tsx wired as components land. Do not leave a stub at delivery time.
8. shell_exec "cd ./workspace/deliverables/<project> && npx vite build" — must compile clean
9. If errors: fix, rebuild. Deliver only when clean.
CSS: .container .card .grid .grid-2/3/4 .flex .gap-2/4/6 .text-center .text-muted .mt-4 .mb-4 .p-4

# Paths
- This repo uses repo-relative paths like ./workspace/deliverables/<project>.
- NEVER invent absolute repo paths like /workspace/... or /skills/...
- For shell commands, prefer cd ./workspace/deliverables/<project> from the repo root.
- Once a project is active, python_exec runs from that project's root.
- Inside python_exec, use project-local paths like src/App.tsx or src/components/Hero.tsx.
- Inside python_exec, do NOT use ./workspace/deliverables/<project>/... paths.
- For webdev_screenshot, use an image output path like screenshot.png, hero.png, or qa/homepage.png.

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
