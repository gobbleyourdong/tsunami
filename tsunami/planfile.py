"""PlanFileManager — the wave's persistent blackboard.

The wave (orchestrator) writes a structured plan.md. Drones (per-iter
workers) read its TOC for context and index into specific sections
when they need detail. Status flags on TOC entries let the wave track
progress across iters without replaying conversation history.

Philosophy: single inference has hit its ceiling; efficiency wins
come from orchestration. Externalize long-lived planning to disk so
drone contexts stay tiny. Same plan survives across parallel eddies.

File format (workspace/plans/current.md):

    # Plan: <goal one-liner>

    ## TOC
    - [x] [Setup](#setup) — deps + scaffold ready
    - [>] [Components](#components) — writing TimerDisplay
    - [ ] [Build](#build)
    - [ ] [Deliver](#deliver)

    ## Setup
    scaffold at /tmp/.../pomodoro
    deps: none beyond default

    ## Components
    ### TimerDisplay
    - src/components/TimerDisplay.tsx
    - Props: {seconds, running}
    ### TaskList
    - src/components/TaskList.tsx
    ...

    ## Build
    shell_exec cd deliverables/pomodoro && npm run build

    ## Deliver
    message_result
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Status = Literal["pending", "active", "done", "failed"]

_STATUS_MARKER = {
    "pending": "[ ]",
    "active": "[>]",
    "done": "[x]",
    "failed": "[!]",
}
_MARKER_STATUS = {v: k for k, v in _STATUS_MARKER.items()}


@dataclass
class Section:
    name: str
    body: str = ""
    status: Status = "pending"


def _slugify(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", name.strip().lower())
    s = re.sub(r"[\s_]+", "-", s)
    return s


def _parse_sections_from_markdown(text: str) -> list[Section]:
    """Pull `## Name` H2s + their TOC status markers out of a plan.md
    template. Ignores the `## TOC` block itself. Status comes from the
    TOC line; body comes from the H2 section that matches by name.
    """
    # First pass: extract status markers from the TOC.
    toc_status: dict[str, Status] = {}
    toc_match = re.search(r"## TOC\n(.+?)(?=\n## |\Z)", text, re.DOTALL)
    if toc_match:
        for line in toc_match.group(1).splitlines():
            m = re.match(r"- (\[.\]) \[(.+?)\]\(#.+?\)", line.strip())
            if m:
                toc_status[m.group(2)] = _MARKER_STATUS.get(m.group(1), "pending")

    # Second pass: pull each H2 body, skipping TOC.
    sections: list[Section] = []
    for m in re.finditer(r"## (.+?)\n(.*?)(?=\n## |\Z)", text, re.DOTALL):
        name = m.group(1).strip()
        if name == "TOC":
            continue
        body = m.group(2).strip()
        sections.append(Section(
            name=name,
            body=body,
            status=toc_status.get(name, "pending"),
        ))
    return sections


# Domain keywords → scaffold name. First match wins — more specific
# domains listed before the generic build family.
#
# Ordering rule: dashboard / data-viz / form-app / landing all sit
# BEFORE the implicit react-build fallback so their plan_scaffolds fire
# on the right prompts. The dashboard / data-viz split mirrors
# project_init's `_pick_scaffold` cascade — "dashboard" matches the
# admin/console family first, "chart"/"plot"/"analytics" routes to the
# data-viz plan with its chart-type catalog. Order matters: if "chart"
# matched before "dashboard", admin dashboards would route to data-viz.
_DOMAIN_SIGNALS: list[tuple[tuple[str, ...], str]] = [
    (("replica", "replicate", "mimic", "clone",
      "styled as", "apple watch", "iphone ui", "watch face",
      "inside of a game", "inside a game", "mini-game", "minigame",
      "inside of", "embedded in"), "replicator"),
    # Gamedev before the generic react-build keywords — "game" matches
    # here first, routing to the engine-only game scaffold instead of
    # the react-dom one. Keywords chosen to catch playable verbs without
    # catching website-with-game-theme phrases.
    (("frogger", "snake", "pong", "asteroids", "platformer",
      "shooter", "rhythm game", "tower defense", "playable game",
      "arcade game", "video game",
      # Expanded 2026-04-19 after telemetry caught "zelda-like top-down"
      # falling to react-build on a live run (timed out 1500s writing no
      # App.tsx because the scaffold template was for a web app, not a
      # game). Canonical pre-2003 genre-clone keywords here:
      "zelda-like", "zelda like", "legend of zelda",
      "top-down action", "top-down adventure",
      "top down action", "top down adventure",
      "action-adventure", "action adventure",
      "metroidvania", "metroid-like", "metroid like",
      "roguelike", "rogue-like", "dungeon crawler",
      "jrpg", "turn-based rpg", "turn based rpg", "party rpg",
      "fps", "first-person shooter", "first person shooter",
      "doom-like", "doom like", "quake-like",
      "kart racer", "mario kart", "arcade racer",
      "bullet hell", "shoot em up", "shoot-em-up", "shmup",
      "2d fighter", "3d fighter", "fighting game",
      "beat em up", "beat-em-up",
      "side-scroller", "side scroller", "run and jump",
      "stealth game", "sneak game",
      "survival horror",
      "open world game", "sandbox game",
      "rts", "real-time strategy", "real time strategy",
      "turn-based strategy", "4x game", "4x strategy",
      "puzzle platformer", "puzzle game",
      "simulation game", "life sim",
      "immersive sim",
      "2d game", "3d game", "indie game",
      "adventure game", "retro game",
      # Bare-genre fallbacks — "racing game", "fighting game" etc.
      # already match above as multi-word phrases, but the single-word
      # "racing" / "race" / "stealth" prompts missed. Telemetry note:
      # "Build a racing game called Neon Drift" misrouted to refactor
      # because no keyword fired. Add the bare genre nouns.
      "racing game", "race game",
      "platformer game", "platformer called",
      "rpg game", "rpg called",
      "jrpg called", "jrpg game",
      "fighting called", "platformer called",
      "game called",
      # Cross-genre canaries — explicit scaffold names as keywords
      # so prompts like "magic_hoops canary" route to gamedev instead
      # of misclassifying as refactor.
      "magic_hoops", "magic-hoops", "ninja_garden", "ninja-garden",
      "rhythm_fighter", "rhythm-fighter", "action_rpg_atb",
      "action-rpg-atb", "metroid_runs", "metroid-runs",
      "cross-genre canary", "cross genre canary"), "gamedev"),
    (("research", "investigate", "what is", "find out", "how does",
      "look up", "survey"), "research"),
    (("refactor", "rename", "extract", "cleanup", "split", "merge"),
     "refactor"),
    # AI app first among the new app-shape plans — "ai chat" must NOT
    # route to realtime (which catches "chat" too). Mirrors
    # project_init's _pick_scaffold priority: ai-app → auth-app →
    # realtime → fullstack.
    (("ai chat", "ai chatbot", "chatbot app", "llm app", "llm chat",
      "ai assistant", "openai api", "anthropic api", "claude api",
      "gpt api", "streaming chat", "chat with gpt", "chat with claude",
      "ai powered app", "build a chatbot"),
     "ai-app"),
    # Auth app — login/register/JWT/protected-route specific. Sits
    # before form-app's "signup form / signup flow" so "signup with
    # JWT" routes to auth-app, not the wizard plan, and before
    # dashboard so "admin dashboard with login" picks the auth plan.
    (("with login", "with auth", "user accounts", "user login",
      "login page", "register page", "jwt auth", "jwt token",
      "protected route", "auth flow", "saas app", "per-user data",
      "user registration"),
     "auth-app"),
    # Realtime — collaborative / live-cursor / multiplayer. Avoid bare
    # "chat" (collides with ai-app, dashboards, etc.); use phrases
    # specific to multi-client sync.
    (("live cursors", "live cursor", "shared whiteboard", "presence",
      "multiplayer", "websocket", "real-time collab", "realtime collab",
      "live update", "collaborative editor", "shared canvas",
      "live whiteboard"),
     "realtime"),
    # Fullstack — generic CRUD app with persistence. "Fullstack",
    # "with backend", "with sqlite", "todo with backend" land here.
    # Less specific than auth/realtime/ai but more specific than
    # dashboard / data-viz / landing.
    (("fullstack", "full stack", "with backend", "with sqlite",
      "with database", "crud app", "with persistence",
      "todo with backend", "with express", "saves to database"),
     "fullstack"),
    # Dashboard sits before data-viz so "admin dashboard with charts"
    # routes to the dashboard plan (sidebar + KPI grid) and not the
    # plotting-focused data-viz plan.
    (("admin dashboard", "metrics dashboard", "analytics panel",
      "ops console", "admin panel", "monitoring board",
      "dashboard", "sidebar nav", "console ui"),
     "dashboard"),
    # Data-viz: chart-heavy / exploration prompts. Avoid the bare word
    # "data" — it false-positives every CRUD spec. Recharts API hints
    # live in the data-viz plan body.
    (("data exploration", "data visualization", "data viz",
      "scatter plot", "heatmap", "bar chart", "line chart",
      "pie chart", "time series", "histogram", "recharts", "d3",
      "visualize", "plot", "graph"),
     "data-viz"),
    # Form-app: multi-step wizards / signup flows / surveys.
    (("signup flow", "signup form", "wizard", "multi-step form",
      "multi step form", "onboarding form", "onboarding flow",
      "survey form", "questionnaire", "intake form", "registration form"),
     "form-app"),
    # Landing: marketing / waitlist / launch pages. Listed last among
    # the new plans because some prompts ("admin dashboard for a
    # landing page builder") should still hit dashboard first.
    (("landing page", "marketing page", "waitlist", "product launch",
      "coming soon", "splash page", "marketing site", "promo page",
      "homepage for", "hero section"),
     "landing"),
    # Chrome extension: MV3 popup / content-script / background-worker.
    # Before electron so "browser extension" wins over "desktop app"
    # when a prompt mentions both (rare, but possible).
    (("chrome extension", "browser extension", "firefox extension",
      "addon", "web extension", "manifest v3", "mv3 extension",
      "content script", "service worker extension", "popup.html"),
     "chrome-extension"),
    # Electron desktop app. Keep "desktop app" + "native app"
    # multi-word to avoid matching "desktop layout" in a web plan.
    (("electron app", "desktop app", "native app", "menubar app",
      "system tray app", "tauri", "offline desktop"),
     "electron-app"),
    # API-only: headless REST / webhook / microservice. No UI.
    (("rest api", "webhook receiver", "webhook service", "microservice",
      "api server", "api only", "backend only", "no frontend",
      "headless api", "openapi", "swagger spec"),
     "api-only"),
]


def pick_scaffold(task: str) -> str:
    """Pick the plan_scaffolds/*.md that best matches the task.
    Falls back to react-build if nothing matches — it's the most
    common case for this agent.

    Matching delegated to tsunami.routing.match_first so word-boundary
    (single-word keys) and substring (multi-word keys) rules live in
    one place. Ordering in _DOMAIN_SIGNALS encodes specificity — the
    first matching rule wins.
    """
    from .routing import match_first
    result = match_first(task, _DOMAIN_SIGNALS, default="react-build")
    # F-C1 telemetry — no-op unless TSUNAMI_ROUTING_TELEMETRY=1
    try:
        from .routing_telemetry import log_pick
        log_pick("scaffold", task, result, default="react-build",
                 match_source="default" if result == "react-build" else "keyword")
    except Exception:
        pass
    return result


class PlanFileManager:
    """Owns workspace/plans/current.md. Thread-unsafe; the wave is
    single-threaded. Drones only read via to_toc() / section()."""

    def __init__(self, workspace: Path | str):
        self.workspace = Path(workspace)
        self.plan_dir = self.workspace / "plans"
        self.path = self.plan_dir / "current.md"
        self.goal: str = ""
        self.sections: list[Section] = []

    # --- creation / mutation (wave-side) ---

    def create(self, goal: str, sections: list[Section | str]) -> None:
        """Initialize the plan. Later calls overwrite."""
        self.goal = goal
        self.sections = [
            Section(name=s) if isinstance(s, str) else s
            for s in sections
        ]
        if self.sections:
            self.sections[0].status = "active"
        self._flush()

    def mark_status(self, section_name: str, status: Status) -> bool:
        """Flip a section's status. Returns True if found."""
        for s in self.sections:
            if s.name == section_name:
                s.status = status
                self._flush()
                return True
        return False

    def advance(self) -> str | None:
        """Mark the active section done, activate the next pending one.
        Returns the newly-activated section name, or None if the plan
        is complete.
        """
        activated = None
        for i, s in enumerate(self.sections):
            if s.status == "active":
                s.status = "done"
            elif s.status == "pending" and activated is None:
                s.status = "active"
                activated = s.name
        self._flush()
        return activated

    def set_body(self, section_name: str, body: str) -> bool:
        for s in self.sections:
            if s.name == section_name:
                s.body = body
                self._flush()
                return True
        return False

    def append_note(self, section_name: str, note: str) -> bool:
        for s in self.sections:
            if s.name == section_name:
                s.body = (s.body + "\n" + note).strip() if s.body else note
                self._flush()
                return True
        return False

    # --- read (drone-side) ---

    def current_section(self) -> Section | None:
        for s in self.sections:
            if s.status == "active":
                return s
        return None

    def section(self, name: str) -> str | None:
        """Return a section's full markdown body. None if missing."""
        for s in self.sections:
            if s.name == name:
                return s.body
        return None

    def to_toc(self) -> str:
        """Compact TOC for drone prompt injection. One line per section."""
        if not self.sections:
            return ""
        lines = [f"Plan: {self.goal}"] if self.goal else []
        for s in self.sections:
            marker = _STATUS_MARKER.get(s.status, "[ ]")
            lines.append(f"  {marker} {s.name}")
        return "\n".join(lines)

    def exists(self) -> bool:
        return self.path.is_file()

    # --- internals ---

    def _flush(self) -> None:
        self.plan_dir.mkdir(parents=True, exist_ok=True)
        out = [f"# Plan: {self.goal}\n" if self.goal else "# Plan\n"]
        out.append("\n## TOC")
        for s in self.sections:
            marker = _STATUS_MARKER.get(s.status, "[ ]")
            slug = _slugify(s.name)
            out.append(f"- {marker} [{s.name}](#{slug})")
        for s in self.sections:
            out.append(f"\n## {s.name}")
            if s.body:
                out.append(s.body.rstrip())
        self.path.write_text("\n".join(out) + "\n")

    def from_scaffold(self, scaffold_name: str, goal: str,
                      scaffold_dir: Path | None = None) -> bool:
        """Instantiate the plan from a `plan_scaffolds/<name>.md` template.
        The scaffold defines the default sections for a given domain
        (react-build, research, refactor, triage, data-pipeline, …).
        Drones then consume the TOC; the wave fills section bodies
        as it learns more. Returns True if the scaffold was loaded.
        """
        root = scaffold_dir or (Path(__file__).parent / "plan_scaffolds")
        path = root / f"{scaffold_name}.md"
        if not path.is_file():
            return False
        template = path.read_text()
        # Substitute {goal} placeholder; everything else stays literal
        # so the drone/wave can fill it as they go.
        template = template.replace("{goal}", goal)
        self.goal = goal
        self.sections = _parse_sections_from_markdown(template)
        self._flush()
        return True

    def load(self) -> bool:
        """Rehydrate from disk. Returns True if a plan was loaded."""
        if not self.exists():
            return False
        text = self.path.read_text()
        goal_m = re.match(r"#\s*Plan:\s*(.+?)\s*\n", text)
        self.goal = goal_m.group(1).strip() if goal_m else ""

        toc_match = re.search(r"## TOC\n(.+?)(?=\n## |\Z)", text, re.DOTALL)
        self.sections = []
        if toc_match:
            for line in toc_match.group(1).splitlines():
                m = re.match(r"- (\[.\]) \[(.+?)\]\(#.+?\)", line.strip())
                if m:
                    status = _MARKER_STATUS.get(m.group(1), "pending")
                    self.sections.append(Section(name=m.group(2), status=status))

        for s in self.sections:
            body_m = re.search(
                rf"## {re.escape(s.name)}\n(.*?)(?=\n## |\Z)",
                text,
                re.DOTALL,
            )
            if body_m:
                s.body = body_m.group(1).strip()
        return True
