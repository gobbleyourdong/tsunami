# Tsunami Roadmap

## Completed ✅

### Framework
- [x] Tension system (current/circulation/pressure)
- [x] Undertow QA lever-puller with eddy vision comparison
- [x] Motion detection + sequence testing in undertow
- [x] Pre-scaffold hidden step (classifier → provision before model starts)
- [x] Auto-scaffold (no package.json → provision on first file write)
- [x] Auto-swell (App.tsx imports missing components → fire eddies)
- [x] Auto-CSS inject (App.tsx always gets theme import)
- [x] Auto-compile (type errors → inject into context)
- [x] Auto-wire on exit (stub App.tsx → generate imports from components)
- [x] File protection (main.tsx, vite.config, index.css read-only)
- [x] Stall detection (8 consecutive read-only tools → force building)
- [x] Block repeated project_init per session
- [x] Requirement-based scaffold classifier (not keyword matching)
- [x] 501 token system prompt (was 4,419)
- [x] GitHub code search (search_type="code")
- [x] Double-escape fixes (unicode, newlines)
- [x] Delivery gate (tension + undertow + adversarial, max 5 attempts)

### Scaffolds (9)
- [x] react-app (minimal React + TS + Vite)
- [x] dashboard (Layout, Sidebar, StatCard, DataTable, recharts)
- [x] data-viz (recharts + d3 + papaparse)
- [x] form-app (FileDropzone, editable DataTable, xlsx/csv parser)
- [x] landing (Navbar, Hero, Section, FeatureGrid, Footer, ParallaxHero, PortfolioGrid)
- [x] fullstack (Express + SQLite + useApi CRUD)
- [x] threejs-game (Scene, Physics, Shaders, Procedural, Sprites, Textures)
- [x] pixijs-game (GameCanvas, Matter.js, SpriteAnimator, Puppet rig)
- [x] realtime (WebSocket server + useWebSocket hook)

### UI Component Library (28)
- [x] Base: Modal, Tabs, Toast, Badge
- [x] shadcn-lite: Dialog, Select, Skeleton, Progress, Avatar, Accordion, Alert, Tooltip, Switch, Dropdown
- [x] Fancy: StarRating, GlowCard, Parallax, AnimatedCounter
- [x] Niche: BeforeAfter, ColorPicker, Timeline, Kanban
- [x] CSS Effects: AnnouncementBar, Marquee, TypeWriter, GradientText
- [x] Interactive: ScrollReveal, Slideshow

### Distribution
- [x] setup.sh (Mac/Linux one-liner)
- [x] setup.bat (Windows, battle-tested with CUDA detection)
- [x] setup.ps1 (PowerShell, from PR #6)
- [x] Desktop launcher (auto-downloads llama-server + models)
- [x] IDE-style desktop UI (VS Code layout, live preview, terminal)
- [x] GitHub Actions builds Windows .exe automatically
- [x] v0.1.0 release published
- [x] VRAM detection on all platforms (lite <10GB, full ≥10GB)
- [x] Lite mode: 2B on both ports, everything still works
- [x] SD-Turbo image gen available in all modes
- [x] SD-Turbo in-process (no server needed, auto-downloads 2GB model)
- [x] Vision grounding (Qwen-VL extracts element positions → layout.css)
- [x] No iteration cap (while True, delivers when done)
- [x] Research gate (search before writing visual projects)
- [x] Mid-loop auto-wire (App.tsx wired when 2+ components exist)
- [x] Runtime error check (Playwright catches JS crashes after compile pass)
- [x] Verification stall detector (forces delivery after 8 read-only checks)
- [x] Conversational short-circuit (greetings skip tension gate, 1 iteration)
- [x] DDG image search curl bypass (TLS fingerprint detection workaround)
- [x] Windows installer (Inno Setup, 64-bit, proper GPU detection)
- [x] Persistent serve daemon (like ComfyUI on :9876)
- [x] Eddy is a role not a model (unified endpoint, lite mode = one server)
- [x] Auto-inject React hook imports (2B forgets useState)
- [x] Unified WebUI (chat + files/code + preview with maximize)

### Tested Apps (15 delivered)
- [x] Calculator (10 iters)
- [x] Quiz (34 iters)
- [x] Excel Diff (17 iters)
- [x] Snake (12 iters)
- [x] Todo (25 iters)
- [x] Landing (23 iters)
- [x] Rhythm (15 iters)
- [x] Crypto Dashboard (17 iters)
- [x] Kanban (27 iters)
- [x] Weather (24 iters)
- [x] Game Boy DMG-01 CSS (72 iters, vision grounded)
- [x] Typing Game "NEON TYPE RUSH" (13 iters)
- [x] Storybook Encyclopedia (29 iters, SD-Turbo art)
- [x] Picture Gallery (73 iters, 6 SD-Turbo images)
- [x] ComfyUI Clone (15 iters, wired to SD-Turbo :8091)
- [x] Counter (7 iters, lite mode verified)
- [x] Pomodoro Timer (15 iters, overnight build)

---

## In Progress 🔨

### CLI Improvements (from meanaverage PRs)
- [ ] Tab autocomplete for slash commands
- [ ] `/attach` with filesystem path completion
- [ ] `/unattach` and `/detach` commands
- [ ] Trace tail view (live tool call log)
- [ ] Status display with health indicators

### Docker Sandbox (from meanaverage PR #4)
- [ ] Docker-backed execution for shell_exec, python_exec
- [ ] Host keeps GPU + models, Docker gets the blast radius
- [ ] exec.Dockerfile for the sandbox container
- [ ] Docker health check integration

---

## Planned 📋

### Installer & Distribution
- [ ] One-click Windows .exe that downloads everything on first run (no setup.bat needed)
- [ ] Mac .dmg or Homebrew formula
- [ ] Progress bar UI for model downloads
- [ ] Auto-update mechanism
- [ ] Pin llama.cpp to specific tested release in setup.sh

### Framework
- [ ] Undertow QA against live Vite dev server (not separate http.server)
- [ ] Swell auto-dispatch from App.tsx imports (framework fires eddies, not model)
- [ ] todo.md checklist pattern (wave writes, reads each iteration)
- [ ] Capability routing in plan phases (research → cheap model, code → 9B)
- [ ] Three-strike error recovery with tool-specific playbooks
- [ ] Expose tool for public URL tunneling (like ngrok)

### Scaffolds
- [ ] mobile-app (Expo + React Native)
- [ ] chrome-extension
- [ ] vscode-extension
- [ ] electron-app (desktop apps)
- [ ] api-only (Express + OpenAPI, no frontend)

### Components
- [ ] Rich text editor (Tiptap or ProseMirror)
- [ ] Data grid with sorting/filtering/pagination
- [ ] File manager (tree view + upload)
- [ ] Chat interface (message bubbles, streaming)
- [ ] Map component (Leaflet or MapLibre)
- [ ] Calendar / date picker
- [ ] Notification center
- [ ] Command palette (⌘K)

### 3D / Creative
- [ ] Volumetric smoke/fog shader
- [ ] Ocean rendering (FFT waves)
- [ ] Particle system component
- [ ] GLTF model loader with animations
- [ ] Post-processing pipeline (bloom, DOF, SSAO)
- [ ] 2D skeletal animation (Spine-like)

### Intelligence
- [ ] Train small tension classifier (50M params) for packaging
- [ ] Vision model integration (Qwen3.5 multimodal with mmproj)
- [ ] Eddy specialization (some eddies for code, some for research)
- [ ] Session persistence across agent restarts
- [ ] Learning from successful builds (pattern extraction)

### Methodology — SPA Visual Validation (compile ≠ renders)
The #1 unresolved failure mode: build passes but page is blank.
React SPAs render on the client — dist/index.html is an empty shell.
The agent verifies compile (vite build) but has no reliable way to
verify the output actually RENDERS in the browser.

Three builds tonight had white screens despite clean compiles:
- External dep crashed at runtime (markdown-note-taking)
- Wrong cross-file imports tree-shook away (typing-speed-game)
- Wrong rendering approach (canvas vs CSS) never caught (gameboy)

- [ ] **Blank page detection**: After compile pass, load dev server in
      Playwright, check that `document.body.innerText.length > 0` or
      that the screenshot has >5% non-white pixels. Inject error if blank.
- [ ] **Content verification**: Compare visible text on page against the
      user's original request. "Build a calculator" → page should contain
      numbers/buttons. Use 2B eddy to check.
- [ ] **Screenshot diff on re-builds**: After each file edit that passes
      compile, screenshot the page. If the screenshot is identical to
      the previous one (nothing changed visually), the edit was likely
      wrong — nudge the agent.
- [ ] **External dep validation**: Before npm-installing a package the
      agent requested, check it actually exists on npm and has >100
      weekly downloads. Prevents phantom package crashes.
- [ ] **Dev server health gate at delivery**: Before message_result,
      curl the dev server. If it returns 500 or the page has JS errors,
      block delivery (like the compile gate but for runtime).

### Methodology — Priority-Based Context Management
Context management is FIFO — oldest messages get pruned regardless of
importance. On long builds (72+ iters), the agent forgets its own plan,
architecture decisions, and user constraints because they were in early
messages that got compressed away.

The 9B on this machine has 32K context. At ~500 tokens/iter, that's
~64 iterations before compression triggers. But compression drops
critical early context (architecture, types, user intent) while
keeping recent noise (build output, grep results).

- [ ] **Message importance scoring**: Tag messages with importance
      (0.0-1.0). plan_update=0.9, file_write=0.7, shell_exec "build
      succeeded"=0.1. Compress low-importance first regardless of age.
- [ ] **Pinned messages**: System prompt + user request + plan +
      types.ts content should NEVER be compressed. Mark as pinned.
      Currently plan is appended at the end (recency bias) but gets
      swept on next compression cycle.
- [ ] **File-backed context**: Instead of keeping file contents in
      the conversation, write them to disk with a 1-line reference.
      "Wrote src/App.tsx (45 lines) — see workspace/.context/App.tsx"
      The tool_result_storage does this for large results but the
      threshold is too high (2KB). Should be 500 chars.
- [ ] **Incremental summarization**: Instead of compressing a big
      block at once, summarize every 10 iterations into a running
      "session memory" that's always in context. Like git commit
      messages for the conversation.
- [ ] **Fact extraction before compression**: Before dropping messages,
      extract key facts ("wrote types.ts with Item interface",
      "user wants dark theme", "build needs recharts") and keep
      them in a pinned facts block.

### Methodology — Closed-Loop Feedback (highest leverage)
The agent measures quality (tension, undertow, pressure) but none of it
feeds back into the next tool choice. All feedback loops are one-way.

- [ ] **Dynamic tool filtering**: After measuring tension on tool choice,
      inject "avoid X, prefer Y" into the next prompt based on what worked.
      Currently tension is measured post-hoc and discarded.
- [ ] **Session-local learning**: Instincts are extracted post-session and
      injected into the NEXT session. The current session can't adapt.
      Track working memory of what worked/failed in the last 10 calls.
- [ ] **Pre-execution validation**: Before expensive tools (search_web,
      generate_image), ask the 2B "will this help?" (cheap probe).
      Currently all tools are treated as equal cost.
- [ ] **Inter-eddy communication**: Eddies in a swell batch can't see
      each other's outputs. Shared KV store so eddy 2 can reuse what
      eddy 1 already found.
- [ ] **Incremental compression**: Compress every 1000 tokens gained,
      not at the 13k-from-limit threshold. Prevents the cliff where
      context suddenly gets destroyed.
- [ ] **Semantic dedup in context**: When compressing, extract facts and
      keep only the newest version. "I tried X, it failed" said twice
      wastes tokens.
- [ ] **Adaptive tension thresholds**: Current thresholds (0.15/0.30/0.50/0.70)
      are fixed. Should adapt based on task type — code builds need
      different thresholds than research queries.

---

## Community Contributions Welcome 🌊

Best areas for PRs (isolated, low conflict):
- New scaffolds in `scaffolds/`
- New UI components in `scaffolds/react-app/src/components/ui/`
- New test runners in `tests/`
- Documentation and examples
- Bug reports with reproduction steps

Open an issue first for anything touching core files (agent.py, prompt.py, tools/).
