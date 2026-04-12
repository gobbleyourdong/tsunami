"""Auto-adapter selection — chat → build → gamedev transitions.

Matches the Manus-style criteria: stay in base chat until the user's intent
crystallizes as "build X", then transition to the specialized adapter. Game
prompts go to `gamedev`; general web-dev goes to `build-v89`. Iteration on
an existing specialized project holds the current adapter (don't flip back
to chat on an "add dark mode" follow-up).

Pure function — returns (adapter_name, reason). Caller mutates
`self.model.adapter` and, on transition, may log / surface the reason.
"""

from __future__ import annotations

# ---- Signal vocabularies ---------------------------------------------------

# Cancel / revert — user pulls back, go to chat.
_REVERT_PHRASES = (
    "forget about",
    "cancel that",
    "actually, no",
    "scrap that",
    "scratch that",
    "nevermind",
    "never mind",
    "stop that build",
    "don't build",
)

# Game signals — strongest match wins (checked before build).
# Include artifact nouns that are specifically game-shaped.
_GAME_WORDS = (
    # explicit category
    "game", "gamedev", "game dev",
    # engines / runtimes
    "webgpu", "three.js", "three js", "tsunami engine",
    # genres
    "platformer", "shooter", " rpg ", "roguelike", "bullet hell",
    "idle game", "incremental game", "tower defense",
    # mechanics / rendering
    "sprite", "tilemap", "tile map", "physics simulation",
    "3d scene", "3d game", "2d game", "canvas game",
    "bouncing ball", "particle system",
    # input / control
    "wasd ", "keyboard controls", "gamepad",
)

# Electron / desktop signals — main.ts + preload.ts + useIPC hook pipeline.
_ELECTRON_WORDS = (
    "electron app", "electron desktop",
    "desktop app", "desktop application", "native app", "native desktop",
    "system tray", "tray app", "menubar app", "menu bar app",
    "native file dialog", "open file dialog", "native dialog",
    "desktop markdown editor", "desktop notes", "desktop text editor",
    "desktop file browser", "desktop image viewer", "desktop file viewer",
    "ipcrenderer", "ipcmain", "contextbridge",
)

# Chrome extension signals — distinct pipeline (3-file: popup + bg + content).
_CHROME_EXT_WORDS = (
    "chrome extension",
    "browser extension",
    "extension popup",
    "popup extension",
    "manifest.json",
    "chrome.tabs",
    "chrome.storage",
    "service worker extension",
    "content script",
)

# Realtime signals — WebSocket + rooms; server/index.js (ws library) + useWebSocket hook.
_REALTIME_WORDS = (
    # explicit WebSocket vocabulary
    "real-time", "realtime", "real time",
    "websocket", "web socket", "live chat", "live feed",
    "collaborative", "multi-user", "multiplayer chat",
    # presence / rooms
    "online presence", "typing indicator", "chat rooms",
    "live updates", "live notifications", "push notifications",
    # apps that are inherently real-time
    "chat app", "chat application",
    "collaborative editor", "collaborative whiteboard",
    "live poll", "live voting", "live dashboard",
    "real-time sync",
)

# Fullstack signals — Express + SQLite + useApi; distinct two-file pipeline.
_FULLSTACK_WORDS = (
    # explicit
    "fullstack app", "full stack app", "full-stack app",
    "backend api", "rest api app", "sqlite app", "sqlite backend",
    # express + db combos
    "express server", "express + sqlite", "express sqlite",
    "node backend", "node server",
    # persistence patterns
    "database backend", "with a database", "sqlite database",
    "persisted to database", "save to database", "stored in database",
    "crud app", "crud api",
    # useApi pattern (when mentioned explicitly)
    "useapi hook", "useapi(",
)

# Data-viz signals — Recharts + ChartCard scaffold, distinct from generic build.
_DATAVIZ_WORDS = (
    # explicit vocabulary
    "data viz", "data visualization", "data dashboard", "chart dashboard",
    # libraries
    "recharts", "d3.js", "d3 chart", "chartcard",
    # chart types (must be paired with "chart" or "dashboard" to avoid false matches)
    "bar chart", "line chart", "pie chart", "area chart", "scatter chart",
    "scatter plot", "donut chart", "funnel chart", "histogram",
    # dashboard nouns
    "analytics dashboard", "metrics dashboard", "kpi dashboard",
    "sales dashboard", "revenue dashboard", "traffic dashboard",
    # csv viz (upload csv goes to form-app, not here — dataviz is for charting)
    "csv chart", "csv dashboard",
)

# Landing page signals — Hero + FeatureGrid + CTASection + Navbar + Footer scaffold.
# Distinct from generic build (no React state, no API) and dataviz (no charts).
_LANDING_WORDS = (
    # explicit
    "landing page", "landing site", "marketing page", "marketing site",
    "homepage", "home page",
    # portfolio / personal
    "portfolio page", "portfolio site", "portfolio website", "developer portfolio",
    "personal site", "personal website",
    # product marketing
    "product launch page", "launch page", "coming soon page", "waitlist page",
    "saas landing", "startup landing", "product page",
    # presentation patterns
    "hero section", "features section", "cta section", "call to action section",
    "feature grid", "testimonials section", "stats section",
)

# Dashboard signals — Layout + StatCard + ChartCard + DataTable + Modal + Toast scaffold.
# Distinct from dataviz (pure charts, no sidebar) and generic build (no StatCard/DataTable).
_DASHBOARD_WORDS = (
    # explicit admin/management vocabulary
    "admin dashboard", "management dashboard", "admin panel", "admin portal",
    "operations dashboard", "ops dashboard",
    # sidebar + stats combos
    "sidebar nav", "sidebar navigation",
    "stat card", "statcard", "kpi card", "kpi dashboard",
    # management app domains
    "user management", "user admin", "inventory management", "inventory dashboard",
    "crm dashboard", "hr dashboard", "support dashboard", "billing dashboard",
    "server monitoring", "api monitoring", "ci/cd dashboard", "pipeline dashboard",
    "content moderation", "moderation dashboard", "fleet dashboard",
    # scaffold components explicitly mentioned
    "layout component", "statcard component", "datatable component",
)

# Form-app signals — FileDropzone + DataTable + parseFile + exportCsv scaffold.
_FORM_WORDS = (
    # file upload
    "file upload", "upload file", "upload csv", "upload excel", "upload spreadsheet",
    "file dropzone", "drag and drop upload", "drag-and-drop upload",
    "drag & drop", "dropzone", "file picker",
    # spreadsheet viewing / editing
    "xlsx viewer", "excel viewer", "spreadsheet viewer", "csv viewer",
    "spreadsheet editor", "editable table", "editable spreadsheet",
    "data table", "parse csv", "parse excel", "parse xlsx",
    # multi-step / wizard forms
    "multi-step form", "wizard form", "form wizard", "stepper form",
    "form steps", "step-by-step form", "multi step form",
    # export
    "export csv", "export to csv", "download csv",
)

# Build verb + noun pair — classic web/app scaffolding.
_BUILD_VERBS = (
    "build", "create", "make", "develop", "design", "scaffold",
    "implement", "code up", "whip up",
)
_BUILD_NOUNS = (
    # apps / utilities
    "app", "application", "website", "webapp", "web app",
    "dashboard", "tool", "utility", "tracker", "manager",
    "editor", "viewer", "player", "calculator", "converter",
    # content
    "landing page", "portfolio", "blog", "homepage",
    "form", "survey",
    # data
    "todo", "to-do", "todo list", "to-do list",
    "kanban", "board", "list", "catalog",
    # pages / UI
    " page", "page.", " ui", " interface",
)

# Iteration verbs — when current adapter is specialized, these hold it.
_ITERATION_VERBS = (
    "add ", "change ", "fix ", "update ", "modify ", "improve ", "extend ",
    "make it ", "refactor ", "clean up ", "rename ", "rewrite ",
    "instead", "also add",
)


# ---- Router ----------------------------------------------------------------

def pick_adapter(user_message: str, current: str = "") -> tuple[str, str]:
    """Pick the best adapter for the given user message.

    Args:
        user_message: the user's turn text.
        current: the adapter currently in use (from prior turn); drives
            iteration-hold behavior.

    Returns:
        (adapter, reason) — adapter is "none" for chat mode, "build-v89"
        for general web-dev, or "gamedev" for game scaffolds. `reason` is a
        short human-readable tag for logging.
    """
    msg = (user_message or "").lower()

    # 1. User pulls back → chat, regardless of current state.
    for phrase in _REVERT_PHRASES:
        if phrase in msg:
            return "none", f"revert signal: {phrase!r}"

    # 2. Electron desktop signals — main.ts + preload.ts + useIPC; checked first (most specific).
    for phrase in _ELECTRON_WORDS:
        if phrase in msg:
            return "electron-v1", f"electron signal: {phrase!r}"

    # 2a. Chrome extension signals — distinct 3-file scaffold, checked before game/build.
    for phrase in _CHROME_EXT_WORDS:
        if phrase in msg:
            return "chrome-ext-v1", f"chrome-ext signal: {phrase!r}"

    # 2c. Realtime signals — WebSocket + rooms; strongest real-time signal.
    for phrase in _REALTIME_WORDS:
        if phrase in msg:
            return "realtime-v1", f"realtime signal: {phrase!r}"

    # 2d. Fullstack signals — Express + SQLite + useApi two-file pipeline.
    for phrase in _FULLSTACK_WORDS:
        if phrase in msg:
            return "fullstack-v1", f"fullstack signal: {phrase!r}"

    # 2e. Data-viz signals — Recharts + ChartCard scaffold, checked before generic build.
    for phrase in _DATAVIZ_WORDS:
        if phrase in msg:
            return "dataviz-v1", f"dataviz signal: {phrase!r}"

    # 2f. Landing page signals — Hero + FeatureGrid + CTASection scaffold.
    for phrase in _LANDING_WORDS:
        if phrase in msg:
            return "landing-v1", f"landing signal: {phrase!r}"

    # 2h. Dashboard signals — Layout + StatCard + ChartCard + DataTable scaffold.
    for phrase in _DASHBOARD_WORDS:
        if phrase in msg:
            return "dashboard-v1", f"dashboard signal: {phrase!r}"

    # 2g. Form-app signals — FileDropzone + DataTable + parseFile + exportCsv.
    for phrase in _FORM_WORDS:
        if phrase in msg:
            return "form-app-v1", f"form-app signal: {phrase!r}"

    # 3. Game signals beat build signals (game is a specialization, not a
    #    fallback — if the user says "game" we go to gamedev even if the
    #    sentence also contains "build").
    for word in _GAME_WORDS:
        if word in msg:
            return "gamedev", f"game signal: {word!r}"

    # 4. Build verb + noun pair.
    matched_verb = next((v for v in _BUILD_VERBS if v + " " in msg or msg.startswith(v + " ")), None)
    matched_noun = next((n for n in _BUILD_NOUNS if n in msg), None)
    if matched_verb and matched_noun:
        return "build-v89", f"build pair: {matched_verb!r} + {matched_noun.strip()!r}"

    # 5. Iteration hold — if already specialized, an "add X" / "fix Y" / etc.
    #    turn should KEEP the current adapter, not drop back to chat.
    if current in ("gamedev", "build-v89", "chrome-ext-v1", "dataviz-v1", "fullstack-v1", "realtime-v1", "form-app-v1", "electron-v1", "landing-v1", "dashboard-v1"):
        for verb in _ITERATION_VERBS:
            if verb in msg:
                return current, f"iteration-hold: matched {verb.strip()!r}"

    # 6. No specialization signal. If we were already specialized and the
    #    user's turn is short/conversational, still hold (don't flip-flop
    #    on marginal signals like "looks good, thanks").
    if current in ("gamedev", "build-v89", "chrome-ext-v1", "dataviz-v1", "fullstack-v1", "realtime-v1", "form-app-v1", "electron-v1", "landing-v1", "dashboard-v1") and len(msg.split()) < 20:
        return current, "short conversational turn — hold specialized adapter"

    # 7. Default: chat.
    return "none", "chat mode (no specialization signal)"
