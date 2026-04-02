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

### Tested Apps (10/10 render)
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

---

## Community Contributions Welcome 🌊

Best areas for PRs (isolated, low conflict):
- New scaffolds in `scaffolds/`
- New UI components in `scaffolds/react-app/src/components/ui/`
- New test runners in `tests/`
- Documentation and examples
- Bug reports with reproduction steps

Open an issue first for anything touching core files (agent.py, prompt.py, tools/).
