"""Project Init — provision from scaffold library.

Like Manus's webdev_init_project: analyzes what the project REQUIRES,
picks the right scaffold, copies it, installs deps, starts dev server.
The model writes domain logic into src/.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.tools.project_init")

# Scaffold directory — the CDN
SCAFFOLDS_DIR = Path(__file__).parent.parent.parent / "scaffolds"


# Out-of-scope game genres — each either belongs in a future hand-authored
# scaffold (per note_013) or is fundamentally not a real-time spatial game
# the engine scaffold targets. Keyed by a short genre tag; value is the
# matching keyword set (matched with word-boundary regex).
_OOS_GENRE_KEYWORDS: dict[str, list[str]] = {
    "interactive_fiction": [
        "interactive fiction", "text adventure", "choose your own adventure",
        "choose-your-own", "parser game", "text-based adventure", "twine game",
    ],
    "rts": ["rts", "real-time strategy", "real time strategy", "starcraft-like",
            "age of empires", "command and conquer"],
    "tbs": ["turn-based strategy", "turn based strategy", "xcom-like",
            "civ-style", "civilization-like", "hex strategy"],
    "card_game": ["deckbuilder", "deck-builder", "card game", "ccg", "trading card",
                  "slay the spire", "hearthstone-like", "magic the gathering"],
    "multi_unit_sim": ["simcity", "colony sim", "dwarf fortress", "rimworld",
                      "base builder", "city builder", "factorio-like",
                      "multi-unit sim"],
    "mmo": ["mmo", "mmorpg", "massively multiplayer"],
    "crpg": ["crpg", "baldur's gate", "divinity original sin", "party-based rpg",
             "pillars of eternity", "disco elysium"],
}

_OOS_REDIRECT_MESSAGES: dict[str, str] = {
    "interactive_fiction":
        "This looks like interactive fiction (text adventure / CYOA). The "
        "engine scaffold targets real-time spatial games and the action-blocks "
        "DSL doesn't cover parser state machines or long-form branching narrative "
        "at scale. A dedicated IF scaffold (Twine-style or Ink-style) is planned "
        "but not built yet — for now, either (a) reduce scope to a short "
        "narrative_adjacent game (use DialogTree + HotspotMechanic) or (b) build "
        "directly against react-app with a hand-rolled state machine.",
    "rts":
        "Real-time strategy isn't in the engine scaffold's scope (no multi-unit "
        "selection, no unit production economy, no fog-of-war primitives). "
        "A dedicated RTS scaffold is planned. For now, scope down to a "
        "single-protagonist tactical game (use WaveSpawner + archetype tags) "
        "or reject the prompt and ask the user to simplify.",
    "tbs":
        "Turn-based strategy needs a TurnManager + grid/hex playfield which were "
        "scoped out of action-blocks v1 (note_013). A dedicated TBS scaffold is "
        "planned. For now, reject the prompt or propose a real-time alternative.",
    "card_game":
        "Deckbuilders / card games need a card-pool + deck-building UI + hand "
        "management that the action-blocks DSL doesn't model. A dedicated card "
        "scaffold is planned. Build against react-app with hand-rolled state, "
        "or reject the prompt and ask for a non-card framing.",
    "multi_unit_sim":
        "Colony sims / base builders need multi-unit AI + resource-flow graphs "
        "that aren't in the v1 catalog. A dedicated sim scaffold is planned. "
        "For now, reject the prompt or scope down to a single-agent mechanic.",
    "mmo":
        "MMOs require persistent server infra + authoritative multiplayer + "
        "long-lived world state that the engine scaffold (single-client, "
        "single-session) doesn't target. No current scaffold fits; build "
        "directly against fullstack with hand-rolled networking.",
    "crpg":
        "CRPG (party-based RPG with branching dialog + inventory depth + "
        "stat systems) overlaps with IF and the action-blocks narrative subset "
        "but needs a party abstraction that isn't in v1. For now, scope down "
        "to a single-protagonist game using DialogTree + Inventory components, "
        "or build against react-app with a hand-rolled state graph.",
}


def _detect_out_of_scope_genre(all_text: str) -> str:
    """Return the genre tag if the prompt matches one of the 7 out-of-scope
    game families, else empty string. Called before the default game
    scaffold pick so out-of-scope prompts get redirected (not stretched
    into action-blocks via ad-hoc mechanic fakery)."""
    for genre, kws in _OOS_GENRE_KEYWORDS.items():
        for kw in kws:
            if " " in kw or "-" in kw or "'" in kw:
                if kw in all_text:
                    return genre
            elif re.search(rf'\b{re.escape(kw)}s?\b', all_text):
                return genre
    return ""


def _pick_scaffold(name: str, dependencies: list[str], prompt: str = "") -> str:
    """Pick scaffold by analyzing what the project REQUIRES.

    Requirement analysis, not keyword matching:
    1. Platform (3D, 2D, mobile, web)
    2. Persistence (database, save state)
    3. File handling (uploads, spreadsheets)
    4. Data visualization (charts, dashboards)
    5. Presentation (landing, portfolio)
    6. Default to minimal

    prompt: the original user message (broader context than the derived name)
    """
    deps_lower = {d.lower() for d in dependencies}
    all_text = name.lower() + " " + " ".join(deps_lower) + " " + prompt.lower()

    # Delegated to tsunami.routing.match_keyword (plural_s=True for the
    # project_init convention where "extension" should also match
    # "extensions"). Single-file source of truth for word-boundary /
    # multi-word substring semantics across all 6 routers.
    from ..routing import match_keyword as _match_kw

    def needs(*keywords):
        return any(_match_kw(all_text, k, plural_s=True) for k in keywords)

    # 0.0 CLI verticals (Python). Checked first because the "cli" /
    # "command-line" signal is explicit and non-overlapping with web
    # scaffold keywords. Returns a nested scaffold path ("cli/<name>");
    # ProjectInit.execute forks on the "cli/" prefix to use pip instead
    # of npm. Keywords are multi-word where possible to avoid the "live"
    # / "chat" class of mis-routing seen in the web branches.
    #
    # Ordering within the CLI branch matters: file-converter checked
    # first because its signal ("convert csv to jsonl") is more specific
    # than the generic "data processor" signal. A prompt like "cli that
    # converts csv to json" should land on file-converter, not
    # data-processor.
    if needs("convert csv", "convert jsonl", "convert yaml", "csv to json",
             "csv to jsonl", "jsonl to csv", "yaml to json", "json to yaml",
             "file converter", "file-converter", "format converter"):
        if (SCAFFOLDS_DIR / "cli" / "file-converter").exists():
            return "cli/file-converter"
    # config-generator: template → config rendering + validation.
    # Keywords are specific enough to avoid catching generic
    # "configuration" on a web-app task.
    if needs("config generator", "config-generator", "generate config",
             "render config", "template config", "jinja config",
             "jinja2 config", "envsubst-like", "consul-template"):
        if (SCAFFOLDS_DIR / "cli" / "config-generator").exists():
            return "cli/config-generator"
    if needs("cli tool", "command line tool", "command-line tool",
             "process jsonl", "process csv", "stdin pipeline",
             "data processor", "data-processor", "pipeline cli",
             "jq-like", "miller-like"):
        if (SCAFFOLDS_DIR / "cli" / "data-processor").exists():
            return "cli/data-processor"

    # 0a. Chrome extension
    # Dropped "badge" — it's a generic web-UI idiom (notification dots,
    # card labels, the @/components/ui Badge); it mis-routed the AURUM
    # luxury-car brief (which names the Badge component multiple times)
    # to chrome-extension. "popup" similarly can collide with modal
    # popups on web apps; keep it only paired with explicit chrome
    # signals via the multi-word "browser extension" / manifest guards.
    if needs("extension", "chrome", "browser extension", "addon", "manifest",
             "content script", "popup.html"):
        if (SCAFFOLDS_DIR / "chrome-extension").exists():
            return "chrome-extension"

    # 0b. Desktop app (Electron)
    if needs("electron", "desktop app", "native app", "desktop", "menubar",
             "tray", "system tray", "window", "offline app"):
        if (SCAFFOLDS_DIR / "electron-app").exists():
            return "electron-app"

    # 1. Game — unified scaffold with Tsunami Engine (WebGPU, 2D/3D, physics, AI)
    # The model decides 2d vs 3d via Game({ mode: '2d' | '3d' }) in main.ts.
    # No keyword matching for game subgenres — the model knows the engine.
    #
    # Step 10: out-of-scope genre redirect. note_013 / attempt_007 scope
    # the action-blocks scaffold to real-time single-protagonist spatial
    # games. Seven genre families (IF / RTS / TBS / card / multi-unit-sim
    # / MMO / CRPG) get returned as an "__oos__:<genre>" sentinel; the
    # ProjectInit.execute wrapper turns that into a redirect message
    # explaining which scaffold is (or isn't) appropriate — instead of
    # stretching the engine scaffold to fake the genre.
    if needs("game"):
        oos_genre = _detect_out_of_scope_genre(all_text)
        if oos_genre:
            return f"__oos__:{oos_genre}"
        if (SCAFFOLDS_DIR / "game").exists():
            return "game"

    # 3a. AI-powered app (chatbot, LLM interface, streaming chat proxy)
    if needs("ai chatbot", "chatbot app", "ai chat", "llm app", "llm chat",
             "openai api", "anthropic api", "claude api", "gpt api",
             "streaming chat", "usechat", "ai assistant app", "ai powered app",
             "chat with gpt", "chat with claude", "build a chatbot"):
        if (SCAFFOLDS_DIR / "ai-app").exists():
            return "ai-app"

    # 3b. Auth app (JWT login + protected routes + per-user data)
    if needs("with login", "with auth", "user accounts", "user login",
             "login page", "register page", "jwt auth", "protected route",
             "saas app", "per-user", "user registration", "sign in", "sign up"):
        if (SCAFFOLDS_DIR / "auth-app").exists():
            return "auth-app"

    # 4. Needs realtime (chat, live chat, multiplayer, websockets)
    # Removed bare "live" — it caught 'live-updating', 'live preview',
    # 'live color picker', etc. on regular react-app tasks. "live chat"
    # / "live stream" / "live feed" stay as multi-word signals.
    # Removed bare "sync" — overlaps with 'state sync'/'form sync' idioms
    # that don't imply WebSockets. Removed bare "collab" for same reason.
    if needs("chat", "realtime", "live chat", "live stream", "live feed",
             "multiplayer", "websocket", "socket.io", "notification feed",
             "live notification", "pub/sub", "server-sent events",
             "collaborative editor", "collaborative board"):
        if (SCAFFOLDS_DIR / "realtime").exists():
            return "realtime"

    # 5a. API-only — backend with no React frontend (webhook, microservice, REST API)
    if needs("webhook", "microservice", "rest api", "api server", "api only",
             "backend only", "no frontend", "headless api", "openapi", "swagger"):
        if (SCAFFOLDS_DIR / "api-only").exists():
            return "api-only"

    # 5. Needs persistence (database, accounts, saving state)
    # Pruned 2026-04-18 during T2 grind: "track", "log", "history",
    # "bookmark", "favorite" were over-aggressive — "a task list that
    # tracks pomodoros" is React state, not SQLite. "todo" likewise
    # is a local-state app 90% of the time. Only trigger fullstack on
    # explicit backend/DB signals.
    if needs("database", "login", "auth", "account", "persist", "crud",
             "backend", "api server", "express", "sqlite", "saas",
             "signup", "user accounts", "multi-user"):
        if (SCAFFOLDS_DIR / "fullstack").exists():
            return "fullstack"

    # 5. Needs file handling (uploads, spreadsheets). Removed bare "file"
    # — it matched "single-file SPA" in the AURUM prompt and mis-routed a
    # react-app task to form-app. "file upload" as a multi-word key is
    # still here; drop "import"/"export"/"parse"/"diff" which collide
    # with generic dev verbs ("import component", "export default",
    # "parse props"). Keep the explicit format extensions.
    if needs("upload", "file upload", "xlsx", "csv", "excel", "spreadsheet",
             "pdf", "document upload", "sheet"):
        if (SCAFFOLDS_DIR / "form-app").exists():
            return "form-app"

    # 6a. Dashboard (sidebar + charts + tables)
    if needs("dashboard", "dash", "admin", "panel", "monitor"):
        if (SCAFFOLDS_DIR / "dashboard").exists():
            return "dashboard"

    # 6b. Data visualization (charts, graphs, d3 — no sidebar)
    # Dropped bare "stats" — caught "stats row" on landing pages that
    # just display a few KPI numbers (luxury brand sites routinely list
    # top speed / range / horsepower without needing a chart library).
    # Dropped bare "data", "metrics", "report" — all too generic.
    # Prefer multi-word signals + chart-library names.
    if needs("bar chart", "line chart", "pie chart", "scatter plot",
             "time series", "histogram", "heatmap",
             "data visualization", "data viz", "chart library",
             "analytics dashboard", "metrics dashboard",
             "recharts", "d3", "plotly", "chart.js", "echarts",
             "visualize data", "visualization"):
        if (SCAFFOLDS_DIR / "data-viz").exists():
            return "data-viz"

    # 6c. Documentation site (sidebar + prose + search).
    # Checked before the generic "landing" bucket because docs-specific
    # keywords ("docs site", "api reference") are more specific.
    if needs("docs site", "documentation site", "doc site",
             "api reference", "reference site", "user guide",
             "docs portal", "knowledge base"):
        if (SCAFFOLDS_DIR / "web" / "docs-site").exists():
            return "web/docs-site"

    # 6d. E-commerce (product grid + cart + checkout). Checked before
    # landing because ecommerce-specific keywords ("store", "shop",
    # "cart") are more specific; "shop" is multi-word-guarded below
    # to avoid catching "shopify app" on a generic landing page.
    if needs("ecommerce", "e-commerce", "online store", "product catalog",
             "shopping cart", "checkout flow", "product grid",
             "online shop", "web store"):
        if (SCAFFOLDS_DIR / "web" / "ecommerce").exists():
            return "web/ecommerce"

    # 6e. Infra — docker-compose multi-service stack. Keywords are
    # multi-word / specific to avoid catching generic "compose" or
    # "stack" on a React prompt.
    if needs("docker compose", "docker-compose", "compose stack",
             "multi-service stack", "compose.yml", "compose file",
             "dockerfile stack", "compose up"):
        if (SCAFFOLDS_DIR / "infra" / "docker-compose").exists():
            return "infra/docker-compose"

    # 6f. Blog — post list + detail + tag filter. Specific signals
    # before the generic "landing" / react-app buckets.
    if needs("blog", "personal blog", "dev blog", "writing platform",
             "post list", "post detail", "blog site", "blog post"):
        if (SCAFFOLDS_DIR / "web" / "blog").exists():
            return "web/blog"

    # 7. Presentation (landing, portfolio)
    if needs("landing", "portfolio", "marketing", "homepage", "website",
             "showcase", "brochure", "about"):
        if (SCAFFOLDS_DIR / "landing").exists():
            return "landing"

    # 8. Default: minimal React app
    if (SCAFFOLDS_DIR / "react-app").exists():
        return "react-app"

    return ""


class ProjectInit(BaseTool):
    name = "project_init"
    description = (
        "Create a project from the scaffold library. "
        "Analyzes what the project needs (3D, database, file uploads, charts, etc.) "
        "and picks the right template. Installs deps, starts dev server. "
        "You write everything in src/ after this. "
        "Pass extra npm packages in 'dependencies' (e.g. ['xlsx', 'three'])."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Project name (lowercase, no spaces). Created in workspace/deliverables/",
                },
                "template": {
                    "type": "string",
                    "description": (
                        "Explicit scaffold override — bypasses auto-detection. "
                        "Options: 'react-app', 'dashboard', 'data-viz', 'landing', "
                        "'form-app', 'fullstack', 'realtime', 'electron-app', "
                        "'chrome-extension', 'game', 'api-only', 'ai-app', 'auth-app'. Omit to auto-detect from name."
                    ),
                },
                "dependencies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Extra npm packages to install (e.g. ['xlsx', 'three'])",
                    "default": [],
                },
            },
            "required": ["name"],
        }

    # Map model-facing template names → scaffold directory names
    _TEMPLATE_MAP = {
        "react-app":        "react-app",
        "dashboard":        "dashboard",
        "data-viz":         "data-viz",
        "dataviz":          "data-viz",
        "landing":          "landing",
        "form-app":         "form-app",
        "fullstack":        "fullstack",
        "realtime":         "realtime",
        "electron-app":     "electron-app",
        "electron":         "electron-app",
        "chrome-extension": "chrome-extension",
        "chrome-ext":       "chrome-extension",
        "game":             "game",
        "gamedev":          "game",
        "api-only":         "api-only",
        "api":              "api-only",
        "ai-app":           "ai-app",
        "ai":               "ai-app",
        "aiapp":            "ai-app",
        "chatbot":          "ai-app",
        "auth-app":         "auth-app",
        "auth":             "auth-app",
        "authapp":          "auth-app",
        # CLI verticals (Python). Nested paths trigger the pip-install branch.
        "cli":              "cli/data-processor",
        "data-processor":   "cli/data-processor",
        "cli/data-processor": "cli/data-processor",
        "file-converter":   "cli/file-converter",
        "cli/file-converter": "cli/file-converter",
        "config-generator": "cli/config-generator",
        "cli/config-generator": "cli/config-generator",
        "docs-site":        "web/docs-site",
        "web/docs-site":    "web/docs-site",
        "ecommerce":        "web/ecommerce",
        "e-commerce":       "web/ecommerce",
        "web/ecommerce":    "web/ecommerce",
        "docker-compose":   "infra/docker-compose",
        "compose":          "infra/docker-compose",
        "infra/docker-compose": "infra/docker-compose",
        "blog":             "web/blog",
        "web/blog":         "web/blog",
    }

    async def execute(self, name: str, dependencies: list = None, template: str = "", prompt: str = "", **kw) -> ToolResult:
        dependencies = dependencies or []

        ws = Path(self.config.workspace_dir)
        project_dir = ws / "deliverables" / name

        if (project_dir / "package.json").exists():
            # Auto-suffix to avoid overwriting existing projects
            import time
            suffix = str(int(time.time()))[-4:]
            name = f"{name}-{suffix}"
            project_dir = ws / "deliverables" / name
            log.info(f"Project name collision — using '{name}' instead")

        # Register the dir so filesystem tools allow writes here this session.
        from .filesystem import register_session_project
        register_session_project(name)

        try:
            # Explicit template overrides auto-detection
            if template:
                mapped = self._TEMPLATE_MAP.get(template.lower(), template.lower())
                if (SCAFFOLDS_DIR / mapped).exists():
                    scaffold_name = mapped
                    log.info(f"Using explicit template={template!r} → scaffold={scaffold_name!r}")
                else:
                    log.warning(f"template={template!r} scaffold not found; falling back to auto-detect")
                    scaffold_name = _pick_scaffold(name, dependencies, prompt)
            else:
                scaffold_name = _pick_scaffold(name, dependencies, prompt)

            # Step 10: out-of-scope game genre sentinel. _pick_scaffold
            # returns "__oos__:<genre>" when the prompt matches one of the 7
            # game-genre families the action-blocks scaffold isn't designed
            # for (IF / RTS / TBS / card / multi-unit-sim / MMO / CRPG).
            # Instead of scaffolding something that will fail to render a
            # coherent game, surface a redirect message the model can act
            # on: reduce scope, pick a different scaffold, or reject.
            if scaffold_name.startswith("__oos__:"):
                genre = scaffold_name.split(":", 1)[1]
                msg = _OOS_REDIRECT_MESSAGES.get(
                    genre,
                    f"Prompt matches an out-of-scope game genre ({genre}); "
                    "no action-blocks scaffold is available for this family."
                )
                log.info(f"project_init: out-of-scope genre {genre!r} — redirecting")
                return ToolResult(
                    f"REDIRECT: {msg}\n\n"
                    "Do not call project_init again with a game prompt for this "
                    "genre. Either scope the request down, pick a different "
                    "scaffold (e.g. 'fullstack' for MMO-lite), or call "
                    "message_chat to clarify with the user.",
                    is_error=True,
                )

            # Python CLI scaffolds live at scaffolds/cli/<name> and use
            # pip / pyproject.toml. npm/vite are irrelevant here, so
            # fork early rather than threading "is-python" booleans
            # through the web/game copy block below.
            if scaffold_name.startswith("cli/"):
                return self._init_cli_scaffold(name, project_dir, scaffold_name)

            # Infra scaffolds (docker-compose, k8s manifests, terraform)
            # are pure config trees — no install step. Copy + return.
            if scaffold_name.startswith("infra/"):
                return self._init_infra_scaffold(name, project_dir, scaffold_name)

            if scaffold_name:
                scaffold_dir = SCAFFOLDS_DIR / scaffold_name
                shutil.copytree(
                    scaffold_dir, project_dir,
                    ignore=shutil.ignore_patterns(
                        "node_modules", "dist", ".vite", "package-lock.json"
                    ),
                )
                log.info(f"Copied scaffold '{scaffold_name}' → {project_dir}")

                # Game scaffold's tsconfig references ../engine/src/* for
                # @engine/* imports, but the engine lives in the ark repo's
                # scaffolds/engine/. Symlink deliverables/engine → the real
                # engine so path resolution works from the deliverable.
                if scaffold_name == "game":
                    engine_src = SCAFFOLDS_DIR / "engine"
                    engine_link = project_dir.parent / "engine"
                    if engine_src.is_dir() and not engine_link.exists():
                        try:
                            engine_link.symlink_to(engine_src.resolve())
                            log.info(f"Symlinked {engine_link} → {engine_src.resolve()}")
                        except OSError as _sle:
                            log.warning(f"engine symlink failed: {_sle}")

                if dependencies:
                    pkg_path = project_dir / "package.json"
                    pkg = json.loads(pkg_path.read_text())
                    for dep in dependencies:
                        pkg["dependencies"][dep] = "latest"
                    pkg["name"] = name
                    pkg_path.write_text(json.dumps(pkg, indent=2))

                app_tsx = project_dir / "src" / "App.tsx"
                if app_tsx.exists():
                    app_tsx.write_text(
                        '// TODO: Replace with your app\n'
                        'export default function App() {\n'
                        '  return <div>Loading...</div>\n'
                        '}\n'
                    )
            else:
                project_dir.mkdir(parents=True, exist_ok=True)
                src = project_dir / "src"
                src.mkdir(exist_ok=True)
                (src / "components").mkdir(exist_ok=True)

                deps = {"react": "^19.0.0", "react-dom": "^19.0.0"}
                for dep in dependencies:
                    deps[dep] = "latest"

                (project_dir / "package.json").write_text(json.dumps({
                    "name": name, "private": True, "type": "module",
                    "scripts": {"dev": "vite", "build": "tsc --noEmit && vite build"},
                    "dependencies": deps,
                    "devDependencies": {
                        "@types/react": "^19.0.0", "@types/react-dom": "^19.0.0",
                        "@vitejs/plugin-react": "^4.3.0",
                        "typescript": "~5.7.0", "vite": "^6.0.0",
                    }
                }, indent=2))

                for fname, content in [
                    ("index.html", f'<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8"/>\n  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>\n  <title>{name}</title>\n  <style>* {{ margin:0; padding:0; box-sizing:border-box; }}</style>\n</head>\n<body>\n  <div id="root"></div>\n  <script type="module" src="/src/main.tsx"></script>\n</body>\n</html>\n'),
                    ("vite.config.ts", 'import { defineConfig } from "vite"\nimport react from "@vitejs/plugin-react"\nexport default defineConfig({ plugins: [react()] })\n'),
                    ("tsconfig.json", json.dumps({"compilerOptions": {"target": "ES2020", "module": "ESNext", "lib": ["ES2020", "DOM", "DOM.Iterable"], "jsx": "react-jsx", "moduleResolution": "bundler", "strict": False, "noEmit": True, "isolatedModules": True, "esModuleInterop": True, "skipLibCheck": True, "allowImportingTsExtensions": True}, "include": ["src"]}, indent=2)),
                ]:
                    (project_dir / fname).write_text(content)

                (src / "main.tsx").write_text('import { createRoot } from "react-dom/client"\nimport App from "./App"\ncreateRoot(document.getElementById("root")!).render(<App />)\n')
                (src / "App.tsx").write_text('export default function App() {\n  return <div>Loading...</div>\n}\n')

            result = subprocess.run(["npm", "install"], cwd=str(project_dir), capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                return ToolResult(f"Project created but npm install failed: {result.stderr[:300]}", is_error=True)

            try:
                from ..serve import serve_project
                url = serve_project(str(project_dir))
            except Exception:
                url = ""

            scaffold_info = f" (scaffold: {scaffold_name})" if scaffold_name else ""
            dep_list = ", ".join(dependencies) if dependencies else "none"

            # Don't inline the full scaffold README here (~3K chars). The
            # drone gets the file listing + App.tsx stub in the edit prompt
            # and the exports list below — that's enough to start writing.
            # Previously inlining the README bloated the iter 1 user message
            # to 6K+ chars and gave the model something to "verify" via
            # file_read loops. Also don't even mention README.md exists —
            # any hint about a readable file is an invitation the drone
            # will accept over actually writing code.
            readme_content = ""
            readme_path = project_dir / "README.md"
            if readme_path.exists():
                # Cache for later if any code still reads it
                self._readme_cache = readme_path.read_text()

            # Surface the actual component exports upfront so model doesn't
            # hallucinate imports and hit TS2305 at first build. Gallery runs
            # spent 3-4 iterations on CardContent/Image/etc. that didn't exist
            # until we surfaced them. Parsing index.ts exports is cheap.
            exports_note = ""
            idx_path = project_dir / "src" / "components" / "ui" / "index.ts"
            if idx_path.exists():
                try:
                    import re as _re
                    idx_text = idx_path.read_text()
                    exports = set()
                    # export { default as Name } from "./X"
                    for m in _re.findall(r"export\s+\{\s*default\s+as\s+(\w+)", idx_text):
                        exports.add(m)
                    # export { Name, Name2 } from "./X"
                    for m in _re.findall(r"export\s+\{\s*([^}]+)\s*\}\s+from", idx_text):
                        for part in m.split(","):
                            export_name = part.strip().split(" as ")[-1].strip()
                            if export_name and not export_name.startswith("default"):
                                exports.add(export_name)
                    if exports:
                        exports_note = (
                            "\n\nAvailable imports from ./components/ui "
                            "(or @/components/ui with alias):\n  "
                            + ", ".join(sorted(exports))
                            + "\n  Nothing else is exported — use raw <div>/<button>/<input> + Tailwind "
                            + "classes for anything not listed."
                        )
                except Exception:
                    pass

            return ToolResult(
                f"Project '{name}' ready{scaffold_info} at {project_dir}\n"
                f"Extra deps: {dep_list}\n"
                f"Dev server: {url or 'run npx vite --port 9876'}\n\n"
                f"src/App.tsx is a stub — replace it with your app.\n"
                f"After all files: shell_exec 'cd {project_dir} && npm run build' "
                f"(runs `tsc --noEmit && vite build` — typecheck step catches missing imports)"
                f"{exports_note}"
                f"{readme_content}"
            )

        except Exception as e:
            return ToolResult(f"Project init failed: {e}", is_error=True)

    def _init_cli_scaffold(self, name: str, project_dir: Path, scaffold_name: str) -> ToolResult:
        """Init a Python CLI scaffold. Copy tree, pip install -e, return help."""
        scaffold_dir = SCAFFOLDS_DIR / scaffold_name
        if not scaffold_dir.is_dir():
            return ToolResult(
                f"CLI scaffold not found at {scaffold_dir}", is_error=True,
            )
        try:
            shutil.copytree(
                scaffold_dir, project_dir,
                ignore=shutil.ignore_patterns(
                    "__pycache__", "*.egg-info", ".pytest_cache", "build", "dist",
                ),
            )
            log.info(f"Copied CLI scaffold '{scaffold_name}' → {project_dir}")

            install = subprocess.run(
                ["pip", "install", "--quiet", "-e", "."],
                cwd=str(project_dir), capture_output=True, text=True, timeout=120,
            )
            if install.returncode != 0:
                return ToolResult(
                    f"CLI scaffold copied but pip install -e failed: "
                    f"{install.stderr[:300]}",
                    is_error=True,
                )

            entry = scaffold_name.split("/", 1)[1]
            pkg = entry.replace("-", "_")
            return ToolResult(
                f"Project '{name}' ready (scaffold: {scaffold_name}) at {project_dir}\n"
                f"Entry point: `{entry}` (installed on PATH via pyproject.toml)\n"
                f"Run: shell_exec '{entry} --help'\n"
                f"Extend: edit src/{pkg}/cli.py (Click entrypoint). "
                f"See README.md in the project dir for the operator catalog.",
            )
        except Exception as e:
            return ToolResult(f"CLI scaffold init failed: {e}", is_error=True)

    def _init_infra_scaffold(self, name: str, project_dir: Path, scaffold_name: str) -> ToolResult:
        """Init an infra scaffold. No install step — it's a config tree."""
        scaffold_dir = SCAFFOLDS_DIR / scaffold_name
        if not scaffold_dir.is_dir():
            return ToolResult(
                f"Infra scaffold not found at {scaffold_dir}", is_error=True,
            )
        try:
            shutil.copytree(scaffold_dir, project_dir)
            log.info(f"Copied infra scaffold '{scaffold_name}' → {project_dir}")
            return ToolResult(
                f"Project '{name}' ready (scaffold: {scaffold_name}) at {project_dir}\n"
                f"Next step: copy .env.example → .env, fill in secrets.\n"
                f"Run: shell_exec 'cd {project_dir} && docker compose up --build'",
            )
        except Exception as e:
            return ToolResult(f"Infra scaffold init failed: {e}", is_error=True)
