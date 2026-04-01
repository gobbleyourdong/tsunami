# Plan: Manus-Level Web App Building

## The Goal
One prompt → complete, working, deployable web app. No coding knowledge needed.

## Intel (from Manus directly)
- Manus uses `webdev_init_project` — a FEATURE-BASED scaffold
- "the platform provisions a project from a template based on what features are requested"
- Need auth → OAuth pre-wired. Need database → Drizzle ORM ready. Need uploads → S3 helpers.
- The model ONLY writes domain-specific logic. Never touches infrastructure.
- Manus writes `todo.md` with checkboxes — reads it each iteration, checks off items
- The checklist IS the attention mechanism. The file system IS the control loop.

## Phase 1: Feature-Based project_init ✅ (basic version)
- project_init tool created — writes Vite+React+TS infrastructure
- Takes project name + npm dependencies
- Starts Vite dev server with HMR
- **TODO**: Make it feature-aware (analyze request → scaffold matching features)

## Phase 1b: todo.md Checklist Pattern (NEXT)
The 9B forgets steps because the plan is in context, not on disk.
Fix: the wave writes todo.md FIRST, then reads it each iteration.
- Add to prompt: "Write a todo.md in your project dir before writing code"
- Auto-inject todo.md contents into context at the start of each iteration
- Wave checks off items as it completes them
- Test: wave writes todo.md → works through it → all items checked

## Phase 2: Compile-Fix Loop in Agent
After any file_write to a Vite project:
- Auto-run `npx vite build`
- If errors: inject as system note with exact file + line
- Wave reads and fixes
- Test: write component with typo → agent auto-detects and fixes

## Phase 3: Smart Scaffold (Manus parity)
project_init should analyze the request and provide matching features:
- File handling → xlsx/csv parsing helpers
- Data display → table component
- Forms → form helpers
- Charts → chart library
- Auth → auth flow skeleton
- The wave still writes all domain logic

## Phase 4: End-to-End
1. User prompt
2. Wave: project_init → todo.md → write components checking off each → compile → fix → serve
3. App works

## Progress Log
- Session 1: Built current/circulation/pressure tension system, undertow lever-puller, auto-serve
- Session 1: Calculator (0.12 tension), Quiz (0.07), Pinball (0.21 — was 0.62 black screen)
- Session 1: Rhythm game — vanilla JS worked, React compiles but App.tsx not wired by wave
- Session 1: Discovered Manus uses feature-based scaffold + todo.md checklist
- Session 1: Built project_init tool, Three.js game scaffold (Scene/Ground/Box/Sphere/HUD)
- Session 1: Phase 1b+2: todo.md injection + auto-compile in agent loop
- Session 1: Calculator with project_init: 27 iters, 6 typed components, compiles clean, dist/ built
- Session 1: Calculator did NOT write todo.md (9B skipped it). Works for simple apps, will need it for complex.
- Session 1: Excel diff: 60 iters, 6 components written, failed on missing npm install (no project_init used)
- Session 1: Manus insight: the scaffold IS the product. Opus writes scaffolds, 9B fills them in.
- Session 1: Quiz PASSES: 34 iters, 11 typed components (Question, ProgressBar, ScoreCounter, Results, StartScreen, Button + CSS), compiles clean, dist/ built
- Session 1: project_init now picks from scaffolds/ library (threejs-game, react-app). The Manus pattern.
- Session 1: Auto-compile wired into agent loop — errors injected as system notes
- Session 1: todo.md injection wired — auto-reads checklist each iteration if unchecked items exist
- Session 1: EXCEL DIFF PASSES: 22 iters, 6 components (FileUpload, Table, DiffPanel, SubmitPanel), compiles clean
- Session 1: ALL 4 TEST APPS PASS: calculator (27), quiz (34), excel-diff (22) — all from one-prompt runners
- Session 1: Dashboard scaffold built (Layout, Sidebar, Card, StatCard, DataTable + recharts)
- Session 1: project_init picks scaffold by keyword: game→threejs, dashboard→dashboard, form→form-app, landing→landing, default→react-app
- Session 1: Excel diff v2 with form-app scaffold: 59 iters, 8 files, compiles clean, dist/ built
- Session 1: 5 scaffolds built: threejs-game, react-app, dashboard, form-app, landing — all compile clean
- Session 1: Phase 3 (smart scaffold) largely complete — keyword matching + 5 templates
- Session 1: Phase 4 (E2E): All 3 apps RENDER and are FUNCTIONAL (calc, quiz, excel-diff)
- Session 1: Gap: apps work but are unstyled (white background, default HTML buttons)
- Session 1: Base dark theme added to all scaffolds — buttons/inputs/tables styled automatically
- Session 1: Calculator with theme: dark bg, styled buttons. 15 iters (was 27). Unicode escape bug on ÷/×.
- Session 1: Unicode fix: \\u00f7 → ÷ in file_write. Calculator now shows proper symbols.
- Session 1: Remaining gap: grid layout (9B writes flex row not CSS grid)
