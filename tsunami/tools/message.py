"""Message tools — how the agent speaks to humans.

Default to info. Use ask only when genuinely blocked.
Use result only when truly done. Every unnecessary ask
wastes the user's time.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

from .base import BaseTool, ToolResult


# Exact placeholder text written by ProjectInit when scaffolding.
# If App.tsx matches this verbatim, the agent never replaced it.
_SCAFFOLD_PLACEHOLDER_APP_TSX = (
    '// TODO: Replace with your app\n'
    'export default function App() {\n'
    '  return <div>Loading...</div>\n'
    '}\n'
)

# Marker phrases that indicate the agent wrote a roadmap/stub instead of real code.
# Carefully chosen to avoid false positives on legitimate strings — e.g. `placeholder`
# would match `<input placeholder="...">` attributes, so we don't include it.
_PLACEHOLDER_PHRASES = (
    "todo: replace",
    "ready for phase",
    "will go here",
    "goes here",
    "coming soon",
)

# QA-1 Fire 85 — "stub-comment" phrases that are strong enough stubbing
# signals that they block EVEN IF they appear inside a code comment. The
# default marker-phrase scan strips comments first (846f5e8 — protects iter-23
# "// Phase 1: basic layout" false-positive), but these phrases are almost
# never present in comments of real working code. If the agent writes
# "Mock audio context and sample loading for Phase 1 compilation" in a
# comment, the function below it is a stub — ship-blocking.
# Chosen narrowly to avoid false-positives on legitimate mocking in tests
# or pattern descriptions. "mock audio/video" is specific; "mock " alone
# would false-match test files.
_STUB_COMMENT_PHRASES = (
    "mock audio",
    "mock video",
    "would load",            # "In a real scenario, we'd load 808 samples here" (Fire 85)
    "would call",
    "in a real scenario",
    "stub implementation",
    "for now we'll",
    "for now, we",
    "simplified for",        # "simplified for compilation"
    "simulate the ",         # "simulate the structure" (Fire 81 self-incrimination)
    # QA-1 Fire 87/88 (physics sandbox): agent wrote
    # "// Since we don't have the actual Tsunami Engine, we must mock the
    #  necessary parts to satisfy the structure and get it compiling for
    #  Phase 1. We will use a simplified representation of RigidBody..."
    # then hand-rolled a shadow PhysicsWorld interface instead of importing
    # @engine. Each phrase is specific-enough to stubbing prose that
    # false-positive risk stays low.
    "we don't have",          # "we don't have the actual Tsunami Engine"
    "we must mock",           # "we must mock the necessary parts"
    "to satisfy the structure",
    "simplified representation",
    "doesn't seem to exist",
    "isn't available",        # "the <X> isn't available"
)
# NB: "placeholder for " was considered but dropped — too broad. It matches
# legit JSX layout annotations like `{/* Placeholder for Stats */}` in
# working apps (iter-23 false-positive pattern). The other phrases are
# specific enough to stub-context that the false-positive rate is low.

# Any `Phase N` marker (with N ≥ 1, word-boundary) is a deferred-work signal.
# Regex is the right shape here — substring "phase 1" would false-match inside
# "Phase 10" etc. (QA-1 Fire 41 follow-up).
_PHASE_N_MARKER = re.compile(r"\bphase\s+\d+\b", re.IGNORECASE)

# Stop-words excluded from prompt/deliverable keyword overlap. Chosen narrowly to
# leave domain-specific nouns (chart, dashboard, regex, etc.) intact.
_STOPWORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'is', 'are', 'was', 'were',
    'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
    'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
    'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
    'we', 'they', 'me', 'my', 'your', 'his', 'her', 'its', 'our', 'their',
    'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from',
    'about', 'into', 'through', 'before', 'after', 'above', 'below',
    'as', 'so', 'if', 'when', 'where', 'how', 'what', 'who', 'which',
    'build', 'make', 'create', 'add', 'use', 'using', 'app', 'page',
    'instead', 'actually', 'scratch', 'wait', 'just', 'now', 'then',
    'also', 'one', 'two', 'three', 'all', 'any', 'each', 'some',
    'more', 'less', 'very', 'much', 'many', 'good', 'bad', 'new', 'old',
    'theme', 'dark', 'light', 'simple', 'basic', 'web', 'react', 'website',
    'tool', 'tools', 'project', 'show', 'display', 'tsx', 'ts', 'css',
    'src', 'index', 'main', 'export', 'import', 'function', 'return',
    'component', 'div', 'span', 'class', 'className', 'props', 'state',
}


def _significant_words(text: str) -> set[str]:
    """Lowercased ≥3-letter word set, minus stopwords."""
    return {w for w in re.findall(r"[a-zA-Z]{3,}", text.lower()) if w not in _STOPWORDS}


def _check_deliverable_complete(workspace_dir: str) -> str | None:
    """Return error message if the latest deliverable looks like a placeholder
    OR has no keyword overlap with the task prompt. Returns None if OK to ship
    (or if there's no React deliverable to check).
    """
    deliv_root = Path(workspace_dir) / "deliverables"
    if not deliv_root.is_dir():
        return None
    # Prefer THIS session's deliverable (set by ProjectInit) over mtime — under
    # concurrent QA load a neighbor's write can bump their deliverable's mtime
    # above ours, causing the gate to refuse the WRONG project (QA-2 iter 16 HIGH:
    # agent got a REFUSED message naming another QA's `number-counter-...`).
    target = None
    from .filesystem import get_effective_target_project
    effective = get_effective_target_project()
    if effective:
        candidate = deliv_root / effective
        if candidate.is_dir() and (candidate / "package.json").exists():
            target = candidate
    if target is None:
        candidates = [d for d in deliv_root.iterdir() if d.is_dir() and (d / "package.json").exists()]
        if not candidates:
            return None
        target = max(candidates, key=lambda d: d.stat().st_mtime)
    app = target / "src" / "App.tsx"
    if not app.exists():
        return None  # api-only / non-react scaffold
    try:
        content = app.read_text()
    except OSError:
        return None
    if content == _SCAFFOLD_PLACEHOLDER_APP_TSX:
        return (
            f"REFUSED: {target.name}/src/App.tsx is the unchanged scaffold placeholder. "
            f"Write the actual app code with file_write before delivering."
        )
    # Strip JS/JSX comments before the marker-phrase check. Agents often document
    # their work ("// Phase 1: basic layout") while still shipping functional code —
    # QA-2 iter 23 filed directional-click-counter (92L, 2 useState, real handlers)
    # that got false-rejected because of three comment lines mentioning "Phase 1".
    # The useState, size, XSS, and keyword-overlap checks all operate on structural
    # or raw signals, so they use `content` unchanged; only the phrase check cares
    # about authorial intent in prose, which is what comments *aren't*.
    _no_line_comments = re.sub(r'//[^\n]*', '', content)
    _no_block_comments = re.sub(r'/\*.*?\*/', '', _no_line_comments, flags=re.DOTALL)
    _no_jsx_comments = re.sub(r'\{/\*.*?\*/\}', '', _no_block_comments, flags=re.DOTALL)
    marker_scan = _no_jsx_comments.lower()
    lower = content.lower()
    for phrase in _PLACEHOLDER_PHRASES:
        if phrase in marker_scan:
            return (
                f"REFUSED: {target.name}/src/App.tsx still contains placeholder text "
                f"({phrase!r}). Replace it with the real implementation before delivering."
            )
    # QA-1 Fire 85 stub-comment scan — runs against RAW content (not comment-
    # stripped) because these phrases are signature stubs even when they appear
    # in code comments like `// Mock audio context and sample loading`. The
    # comment-stripping for _PLACEHOLDER_PHRASES was specifically to protect
    # iter-23's "// Phase 1: Basic layout" false-positive (legit code), but
    # these phrases have far lower false-positive rate.
    for phrase in _STUB_COMMENT_PHRASES:
        if phrase in lower:
            return (
                f"REFUSED: {target.name}/src/App.tsx contains stub-comment text "
                f"({phrase!r}). The function it annotates is almost certainly a "
                f"stub that prints or no-ops instead of implementing the real "
                f"behavior. Write the actual implementation."
            )
    # `Phase N` marker (any N) in rendered text is a deferred-work signal.
    # Single regex covers Phase 1..N — QA-1 Fire 41 caught that the old
    # substring "phase 1" both (a) missed higher-numbered phases and
    # (b) false-matched inside "Phase 10", "Phase 100", etc.
    _phase_n = _PHASE_N_MARKER.search(_no_jsx_comments)
    if _phase_n:
        return (
            f"REFUSED: {target.name}/src/App.tsx still contains a `{_phase_n.group(0)}` "
            f"placeholder marker. The agent is deferring work to a phase that never arrives. "
            f"Finish the implementation before delivering."
        )
    if len(content) < 300:
        return (
            f"REFUSED: {target.name}/src/App.tsx is only {len(content)} bytes — "
            f"too short to be a complete app. Write the full implementation before delivering."
        )
    # Static-skeleton gate — QA-2 iter 12 found an app that passed every other check
    # (37 lines, no marker phrases, >300 bytes) but rendered hardcoded `>0</` literals
    # for stats and had `useState` imported but never called. Looks like a real React
    # app; will not actually do anything. Two narrow signals:
    #   (a) useState imported but no useState() call — dead giveaway the agent
    #       shipped a static skeleton where state was intended.
    #   (b) Prompt names something dynamic (count / stat / timer / score / etc.) AND
    #       deliverable has literal `>0<` rendered AND no useState call — stats that
    #       will never move.
    # Handle both `import { useState } from 'react'` and `import React, { useState } from 'react'`.
    _imports_useState = any(
        "useState" in line and "react" in line.lower()
        for line in content.splitlines()
        if line.lstrip().startswith("import")
    )
    # TypeScript's typed form `useState<number>(0)` must match too — QA-2 iter 18
    # found the old `\buseState\s*\(` regex false-rejected typed-useState calls,
    # and iter 23 reproduced it on the directional-click-counter. Accept an
    # optional `<Type>` between the identifier and the opening paren.
    _calls_useState = bool(re.search(r"\buseState\b\s*(?:<[^>]+>)?\s*\(", content))
    if _imports_useState and not _calls_useState:
        return (
            f"REFUSED: {target.name}/src/App.tsx imports useState from 'react' but "
            f"never calls it. The UI has no state — any interactive behavior (counters, "
            f"form inputs, toggles) won't work. Call useState() and wire event handlers, "
            f"or remove the unused import and justify a purely static page."
        )

    # QA-1 Playtest Fire 118: `<Badge />` used in JSX without being imported
    # → React crashes at mount, blank page ships. tsc --noEmit in the scaffold
    # catches this at build time, but older deliverables (or hand-edited
    # package.json) skip typecheck. Static check: every PascalCase JSX tag
    # must either be imported, locally defined, or a React intrinsic. Missing
    # ones are a near-certain runtime crash.
    from ..jsx_import_check import find_undefined_jsx_components
    _missing = find_undefined_jsx_components(content)
    if _missing:
        return (
            f"REFUSED: {target.name}/src/App.tsx uses JSX component(s) "
            f"{', '.join(f'<{n}>' for n in _missing[:3])} that aren't imported "
            f"or locally defined. At runtime these evaluate to `undefined` and "
            f"React throws before mount — the page ships blank. Add the imports "
            f"(e.g. `import {{ {_missing[0]} }} from \"./components/ui\"`) or "
            f"remove the tag."
        )

    # QA-1 Playtest Fires 117 + 119: dashboard / analytics deliverables
    # shipped with ZERO chart primitives — the scaffold pulls in `recharts`
    # (dashboard / data-viz scaffolds) + "Dashboard" in the project name
    # screams chart intent, but App.tsx rendered a text "Chart Placeholder"
    # or `"Ready for charts"` stub. If a chart library is in deps AND no
    # chart primitive is present, refuse.
    pkg_path = target / "package.json"
    if pkg_path.is_file():
        try:
            import json as _json
            pkg_data = _json.loads(pkg_path.read_text())
            _deps = {
                **pkg_data.get("dependencies", {}),
                **pkg_data.get("devDependencies", {}),
            }
        except (OSError, ValueError):
            _deps = {}
        # Any of these signals chart-library intent.
        _chart_libs = {"recharts", "d3", "chart.js", "chartjs",
                       "@visx/visx", "victory", "@nivo/core",
                       "plotly.js", "react-plotly.js", "echarts",
                       "apexcharts", "react-apexcharts"}
        _has_chart_lib = any(lib in _deps for lib in _chart_libs)
        if _has_chart_lib:
            # Chart primitives: recharts components, raw <canvas>, <svg>, etc.
            _chart_jsx_re = re.compile(
                r'<(?:LineChart|BarChart|PieChart|AreaChart|ScatterChart|'
                r'RadarChart|ComposedChart|Treemap|Sankey|FunnelChart|'
                r'ResponsiveContainer|canvas|svg|Chart|VictoryChart|'
                r'ApexChart|Plot)\b'
            )
            if not _chart_jsx_re.search(content):
                _lib_name = next(
                    (lib for lib in ("recharts", "d3", "chart.js", "victory",
                                     "plotly.js", "echarts", "apexcharts")
                     if lib in _deps),
                    "a chart library",
                )
                return (
                    f"REFUSED: {target.name}/src/App.tsx doesn't render any "
                    f"chart primitive, but `{_lib_name}` is in dependencies. "
                    f"Chart-scaffold deliverables must render at least one "
                    f"<LineChart> / <BarChart> / <PieChart> / <canvas> / "
                    f"<svg> — a dashboard without a chart is a static "
                    f"infographic with a 'Chart Placeholder' label."
                )

    # qa-solo Playtest (hello-world-button): deliverable named
    # `hello-world-button` shipped with zero `<button>` elements — same
    # prompt-spec-drop class as Fire 120 (simple-expense-tracker with
    # Breakout content) + Fire 85 (drum-machine with no audio). Detect
    # the narrow subset where the deliverable name contains an
    # unambiguous HTML-primitive word — button / form / table / textarea
    # etc. — and the primitive is missing from rendered JSX.
    _primitive_map = (
        # (name-keyword, required-JSX-regex, human-readable)
        ("button", r'<button\b|<input\b[^>]*type=[\'"]button',
         "<button> element"),
        ("form", r'<form\b', "<form> element"),
        ("table", r'<table\b', "<table> element"),
        ("textarea", r'<textarea\b', "<textarea> element"),
        ("checkbox", r'type=[\'"]checkbox', '<input type="checkbox">'),
        ("slider", r'type=[\'"]range', '<input type="range">'),
        ("select", r'<select\b', "<select> element"),
    )
    name_lower = target.name.lower()
    for kw, pattern, label in _primitive_map:
        # Match whole-word-ish (kw flanked by non-alphanumeric or edge)
        # so `platform` doesn't match `form`.
        if not re.search(rf'(?:^|[^a-z0-9]){kw}(?:[^a-z0-9]|$)', name_lower):
            continue
        if re.search(pattern, content, re.IGNORECASE):
            continue
        return (
            f"REFUSED: deliverable name `{target.name}` contains `{kw}` "
            f"but src/App.tsx has no {label}. Either add the component "
            f"the name promises, or rename the deliverable to match what "
            f"you actually built."
        )

    # QA-1 Playtest Fire 124: `text-statistics-tool/` shipped with a
    # `<textarea>` that had no `value` AND no `onChange`. The app's
    # "real-time stats" would never update because the textarea's
    # content couldn't reach React state. UI-claimed interactivity was
    # fake. Detect: a `<textarea>` or `<input type="text|number|search|
    # tel|email|url|password">` that has NEITHER `value` NOR `onChange`
    # attribute. Uncontrolled + unread = dead.
    # Skip: inputs with `defaultValue` (explicitly uncontrolled by design)
    # or `ref={...}` (imperative read path is legit). Skip `type="submit"`
    # / `button` / `checkbox` / `radio` / `file` (different interaction
    # models).
    dead_inputs = []
    for tag_m in re.finditer(
        r'<(textarea|input)\b([^>]*)/?>', content, re.IGNORECASE | re.DOTALL,
    ):
        tag = tag_m.group(0)
        kind = tag_m.group(1).lower()
        attrs = tag_m.group(2)
        if kind == "input":
            type_m = re.search(r'\btype=[\'"]?(\w+)', attrs, re.IGNORECASE)
            input_type = type_m.group(1).lower() if type_m else "text"
            if input_type not in (
                "text", "number", "search", "tel", "email", "url",
                "password", "date", "time", "datetime-local", "month", "week",
            ):
                continue
        # Skip if there's a ref (imperative-access escape hatch).
        if re.search(r'\bref=\{', attrs):
            continue
        # Skip if defaultValue is set (uncontrolled by design).
        if re.search(r'\bdefaultValue=', attrs):
            continue
        has_value = bool(re.search(r'\bvalue=\{?', attrs))
        has_onchange = bool(re.search(r'\bonChange=\{', attrs))
        if not has_value and not has_onchange:
            # Snapshot the tag for the error message (truncate).
            snippet = tag if len(tag) <= 80 else tag[:77] + "..."
            dead_inputs.append(snippet)
    if dead_inputs:
        return (
            f"REFUSED: {target.name}/src/App.tsx has an uncontrolled "
            f"`<{'textarea' if 'textarea' in dead_inputs[0].lower() else 'input'}>` "
            f"with neither `value` nor `onChange` — user keystrokes can't "
            f"reach React state, so anything claimed to be live-updated "
            f"(counts, stats, validation) won't update. Add "
            f"`value={{state}} onChange={{e => setState(e.target.value)}}` "
            f"or use `defaultValue=` + `ref` if you truly want an "
            f"uncontrolled input. Offending tag: {dead_inputs[0]}"
        )

    # QA-1 Playtest Fire 119 + Fire 117 dead-interactivity:
    # analytics-dashboard-charts shipped with 3 `<a href="#">` tabs —
    # Overview / Reports / Settings — none with any onClick, so clicks
    # produced zero navigation. "Cosmetic nav" — decoration that looks
    # interactive. Detect: 2+ `<a href="#">` (or `<a href="">`) tags
    # without an `onClick` handler in the same tag. Single dead `<a>`
    # is often a legit "scroll to top" convention; 2+ is a signature
    # of the agent copy-pasting a nav bar without wiring it.
    anchor_tags = re.findall(
        r'<a\b[^>]*\bhref=[\'"]#?[\'"][^>]*>',
        content,
        re.IGNORECASE | re.DOTALL,
    )
    dead_anchors = [
        t for t in anchor_tags
        if "onclick" not in t.lower()
    ]
    if len(dead_anchors) >= 2:
        return (
            f"REFUSED: {target.name}/src/App.tsx has {len(dead_anchors)} "
            f"`<a href=\"#\">` tags with no onClick handler — looks like "
            f"navigation but does nothing. Wire each one to an onClick "
            f"that updates state / routes / scrolls, or change the "
            f"elements to buttons / spans if they're not actually "
            f"interactive."
        )

    # QA-1 Playtest Fires 117 / 119 / qa-solo dashboard regression:
    # agents wrote `<img src="/icon-home">` etc. for sprites they never
    # created. Every page load produces a browser 404 on the icon. Static
    # check: for every JSX `src="<literal>"` (relative path, no scheme),
    # verify the referenced file exists in the deliverable's public/ or
    # src/assets/ directory. Skip external URLs, data URIs, variable
    # refs (src={x}), and root-relative paths that look like React-router
    # routes.
    self_404: list[str] = []
    for m in re.finditer(
        r'\bsrc=[\'"]([^\'"{]+)[\'"]',
        content,
    ):
        ref = m.group(1).strip()
        # Skip schemed URLs, data URIs, variable refs (shouldn't match but
        # defensive), in-page anchors, and pure `#` / `javascript:` shapes.
        if ref.startswith(("http://", "https://", "data:", "blob:",
                           "javascript:", "mailto:", "tel:", "#", "//")):
            continue
        # Skip empty or pure-whitespace refs.
        if not ref:
            continue
        # Normalize: absolute-root → relative to deliverable root
        # (Vite serves `public/` at `/`). Relative → relative to src/.
        if ref.startswith("/"):
            candidate = target / "public" / ref.lstrip("/")
        else:
            candidate = target / "src" / ref
        # Also accept Vite's alias conventions: /src/..., /@/... map to
        # the src tree. And `assets/X` commonly resolves via Vite imports.
        # If candidate doesn't exist, try a few common alt locations
        # before flagging.
        alts = [candidate, target / ref, target / "src" / "assets" / ref.lstrip("/")]
        if any(p.exists() for p in alts):
            continue
        # Path segments with no file extension often indicate
        # React-Router / virtual routes — skip those (e.g. `/icon-home`
        # without any extension is either a missing asset OR a virtual
        # route; we flag it only if the extension or the context suggests
        # an image asset).
        # Heuristic: flag if the src appears inside `<img ... src=...>` —
        # which is definitionally a fetched resource, not a route.
        # Check the surrounding chars for an `<img` opening tag within
        # ~100 chars back.
        back = content[max(0, m.start() - 100): m.start()]
        if re.search(r'<img\b[^>]*$', back, re.IGNORECASE):
            self_404.append(ref)
    if self_404:
        first = self_404[0]
        return (
            f"REFUSED: {target.name}/src/App.tsx references `<img src=\"{first}\">` "
            f"but no matching file exists in public/ or src/assets/. "
            f"{len(self_404)} broken asset reference(s) would 404 on "
            f"page load. Either create the asset, use a relative import "
            f"`import icon from './assets/icon.svg'`, or inline the SVG "
            f"directly. Other broken refs: "
            f"{', '.join(self_404[1:4]) if len(self_404) > 1 else '(only this one)'}."
        )

    # QA-1 Playtest Fire 120: `src/components/ui/Button.tsx` had been
    # overwritten with a 62-byte stub `return <div>Button</div>` that
    # takes no props and ignores children. App.tsx uses
    # `<Button>Start Game</Button>` — renders literal "Button" text
    # instead of "Start Game". Every clickable UI element labels
    # itself "Button". Detect the stub shape: a file in
    # src/components/ui/<Name>.tsx that's tiny AND renders the
    # component name as literal text AND doesn't reference
    # `children`. Cross-check against App.tsx usage; only refuse when
    # the stubbed component is actually used with children.
    ui_dir = target / "src" / "components" / "ui"
    if ui_dir.is_dir():
        stub_components: list[str] = []
        for comp_path in ui_dir.glob("*.tsx"):
            try:
                comp_text = comp_path.read_text()
            except OSError:
                continue
            name = comp_path.stem
            if len(comp_text) > 200:
                continue
            # Must literally render the component's own name as text
            # (e.g. `<div>Button</div>`).
            if not re.search(
                rf'>\s*{re.escape(name)}\s*<',
                comp_text,
            ):
                continue
            # Legit components always reference `children`; a stub doesn't.
            if "children" in comp_text:
                continue
            # Confirm App.tsx uses the component WITH children (has
            # non-empty text between `<Name>` and `</Name>`).
            if re.search(
                rf'<{re.escape(name)}\b[^>]*>[^<]+</{re.escape(name)}>',
                content,
            ):
                stub_components.append(name)
        if stub_components:
            first = stub_components[0]
            return (
                f"REFUSED: {target.name}/src/components/ui/{first}.tsx has been "
                f"overwritten with a stub that renders the literal text "
                f"\"{first}\" instead of its children. Every "
                f"`<{first}>…</{first}>` in App.tsx will display \"{first}\" "
                f"instead of its contents. Restore a real {first} component "
                f"(accept `children`, render them inside). Other stubbed: "
                f"{', '.join(stub_components[1:3]) if len(stub_components) > 1 else '(only this one)'}."
            )

    # XSS gate — refuse React's HTML-injection escape hatch when the prompt didn't
    # ask for HTML / markdown rendering. QA-3 Test 18b got the model to use the sink
    # on form-submitted content — a textbook XSS.
    from .filesystem import _session_task_prompt
    # Build the sink identifier without writing it literally (pre-commit hook
    # false-positives on the raw string; we're matching for it, not using it).
    _sink_name = "dangerously" + "SetInner" + "HTML"
    if _sink_name in content:
        prompt_lower = _session_task_prompt.lower()
        html_intent = any(kw in prompt_lower for kw in (
            "markdown", "rich text", "html render", "html preview", "render html",
            "mdx", "wysiwyg", "sanitiz",  # prompt acknowledges the risk
        ))
        if not html_intent:
            return (
                f"REFUSED: {target.name}/src/App.tsx uses {_sink_name} — that's an "
                f"XSS sink. The task prompt didn't ask for HTML / markdown rendering, "
                f"so render content as a React child ({{value}}) instead. If you "
                f"genuinely need HTML, sanitize with DOMPurify first and make the "
                f"intent explicit in the prompt."
            )
    # Cross-task / pivot-ignored leakage check — prompt vs deliverable keyword overlap.
    # Require ≥2 distinct overlapping words to avoid false-positives on incidental
    # coincidences (e.g. "groups" appearing in both an analytics prompt's
    # "age groups" and a regex tester's "Capture Groups").
    from .filesystem import _session_task_prompt
    prompt_words = _significant_words(_session_task_prompt)
    if len(prompt_words) >= 5:
        # Combine App.tsx + the deliverable's package.json (catches "use recharts" → recharts in deps)
        deliv_text = content
        pkg = target / "package.json"
        if pkg.exists():
            try:
                deliv_text += "\n" + pkg.read_text()
            except OSError:
                pass
        deliv_words = _significant_words(deliv_text)
        overlap = prompt_words & deliv_words
        if len(overlap) < 2:
            sample = ", ".join(sorted(prompt_words)[:6])
            matched = ", ".join(sorted(overlap)) if overlap else "none"
            return (
                f"REFUSED: {target.name}/src/App.tsx barely matches the task prompt "
                f"(overlap: {matched}; expected words like: {sample}). The deliverable "
                f"doesn't appear to be about the requested task — likely cross-task "
                f"content leakage or pivot miss. Re-read the prompt and rewrite "
                f"App.tsx on-topic before delivering."
            )
    return None


# Global callback for user input — set by the CLI runner
_input_callback = None
_last_displayed = None  # Track last displayed text to suppress duplicates


def set_input_callback(fn):
    global _input_callback
    _input_callback = fn


class MessageInfo(BaseTool):
    name = "message_info"
    description = "Acknowledge, update, or inform the user. No response needed. The heartbeat pulse."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Information to share with the user"},
            },
            "required": ["text"],
        }

    async def execute(self, text: str = "", **kw) -> ToolResult:
        global _last_displayed
        if text:
            # Strip emojis — Windows console (cp1252) crashes on them
            clean = text.encode("ascii", errors="ignore").decode("ascii")
            print(f"\n  {clean}")
        _last_displayed = text
        return ToolResult("Message delivered.")


class MessageAsk(BaseTool):
    name = "message_ask"
    description = "Request input from the user. Only use when genuinely blocked. The pause."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Question to ask the user"},
            },
            "required": ["text"],
        }

    async def execute(self, text: str, **kw) -> ToolResult:
        print(f"\n  \033[33m?\033[0m {text}")
        if _input_callback:
            response = await _input_callback(text)
        else:
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, lambda: input("\n> "))
            except EOFError:
                # Non-interactive mode — don't block, tell model to figure it out
                return ToolResult(
                    "No user available. You are running autonomously. "
                    "Do NOT ask for help. Use file_read to examine your code, "
                    "file_edit to fix errors, and shell_exec to verify. "
                    "Make your best judgment and continue building."
                )
        return ToolResult(f"User response: {response}")


class MessageChat(BaseTool):
    name = "message_chat"
    description = (
        "Talk to the user. Keep it SHORT — one sentence max. "
        "done=true ends the task (conversation). done=false continues (status update). "
        "Use for: greetings, questions, progress updates, snag reports. Not walls of text."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Message to the user"},
                "done": {"type": "boolean", "description": "true = end the task (conversation), false = keep working (status update)", "default": True},
            },
            "required": ["text"],
        }

    async def execute(self, text: str = "", done: bool = True, **kw) -> ToolResult:
        global _last_displayed
        # Refuse done=true when no work has been done — the model uses message_chat
        # as a forbidden message_ask channel ("What would you like me to do?" then
        # done:true), violating the system prompt's "bias toward completion".
        # Catches QA-3's emoji-only and similar-no-deliverable repros.
        if done:
            from .filesystem import _session_created_projects
            if not _session_created_projects:
                return ToolResult(
                    "REFUSED: cannot end the task before doing any work. "
                    "Your bias is toward completion, not caution — make a "
                    "best-effort interpretation of the prompt, call project_init "
                    "with a sensible name, and start building. NEVER use message_chat "
                    "to ask the user clarifying questions; you are autonomous.",
                    is_error=True,
                )
        if text:
            clean = text.encode("ascii", errors="ignore").decode("ascii")
            prefix = "\033[36m>\033[0m" if not done else ""
            print(f"\n  {prefix} {clean}" if prefix else f"\n  {clean}")
        _last_displayed = text
        # The agent loop checks the done flag to decide whether to terminate
        return ToolResult(text, is_error=False)


class MessageResult(BaseTool):
    name = "message_result"
    description = "Deliver final outcome and end the task. The exhale: the work is done."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Final result to deliver"},
                "attachments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File paths to attach as deliverables",
                    "default": [],
                },
            },
            "required": [],
        }

    async def execute(self, text: str = "", attachments: list[str] | None = None, **kw) -> ToolResult:
        global _last_displayed
        # Gate: don't let the agent ship an unchanged scaffold or obvious placeholder.
        # Returning is_error=True keeps the agent loop alive so it can fix and retry.
        gate_error = _check_deliverable_complete(self.config.workspace_dir)
        if gate_error:
            return ToolResult(gate_error, is_error=True)
        # Don't re-display if message_info already showed this exact text
        if text != _last_displayed:
            clean = text.encode("ascii", errors="ignore").decode("ascii")
            print(f"\n  {clean}")
        if attachments:
            print(f"  \033[2m{', '.join(attachments)}\033[0m")
        _last_displayed = None
        return ToolResult(text)
