# Weekend Autonomous Build Plan — 48 Hours

## How to Run
```bash
# On the Spark — start a tmux session
tmux new -s tsunami

# Inside tmux, start a chunk:
cd ~/ComfyUI/CelebV-HQ/ark
claude --dangerously-skip-permissions

# Then say: "Execute PLAN.md chunk N" (where N = current chunk)

# To check in from Windows:
ssh jb@<spark-ip>
tmux attach -t tsunami     # watch live
# Ctrl+B D to detach safely (doesn't kill anything)
# Or just: cat ~/ComfyUI/CelebV-HQ/ark/STATUS.md
```

## Rules
- Each chunk = 1 fresh Claude Code session (context stays clean)
- Commit + push after each chunk completes
- Update STATUS.md with what was done + any blockers
- Run tests after each chunk: `cd ark && python -m pytest tsunami/tests/ -x`
- If a chunk finishes early, move to the next one
- If stuck on something for >30 min, skip it, note in STATUS.md, move on

---

## Chunk 1 (Hours 0-3): Context Intelligence — File-Backed Context
**Why first**: This is the #1 cause of long-build degradation. Every file read
dumps full content into context. On 72+ iter builds the agent forgets its plan.

- [ ] Lower `tool_result_storage.py` threshold from 2KB to 500 chars
- [ ] Write large tool results to `workspace/.context/<hash>.txt`
- [ ] Keep 1-line reference in conversation: "Wrote App.tsx (45 lines) — .context/abc123"
- [ ] file_read results: store on disk, keep first 10 + last 5 lines in context
- [ ] shell_exec output: store full output on disk, keep last 20 lines in context
- [ ] Test: run a 50+ iteration build, verify plan is still in context at iter 40

---

## Chunk 2 (Hours 3-6): Context Intelligence — Incremental Summarization
**Why**: Compression is all-or-nothing. By the time it triggers, critical context
is already gone.

- [ ] New `session_memory.py` — running summary updated every 10 iterations
- [ ] Summary format: "Iter 1-10: scaffolded react-app, wrote types.ts with Item/User interfaces, user wants dark theme"
- [ ] Pin session memory with importance=1.0 (never compressed)
- [ ] Extract facts before compression: scan messages about to be dropped for key decisions
- [ ] Fact categories: files written, types defined, user preferences, architecture decisions
- [ ] Facts block pinned at importance=0.95
- [ ] Test: build a dashboard (30+ iters), verify facts block contains "recharts" and layout info

---

## Chunk 3 (Hours 6-9): Context Intelligence — Semantic Dedup
**Why**: Same error message repeated 5 times wastes 500+ tokens. Same file
content read twice wastes even more.

- [ ] Before compression, group messages by content similarity (hash first 200 chars)
- [ ] Keep only the newest version of duplicate content
- [ ] Special case: repeated error messages → collapse to "Error X occurred N times"
- [ ] Special case: repeated file_read of same path → keep only latest
- [ ] Integrate with fast_prune — dedup runs before importance scoring
- [ ] Test: simulate 10 identical error messages, verify they collapse to 1

---

## Chunk 4 (Hours 9-12): Dynamic Tool Filtering
**Why**: Tension measures quality post-hoc but doesn't influence the next tool
choice. The agent keeps making the same mistakes.

- [ ] After each tool call, record (tool, tension_delta) — did tension go up or down?
- [ ] Track rolling window of last 10 tool calls + their tension impact
- [ ] Before tool selection, inject "TOOL GUIDANCE" note:
      "Recently effective: file_write (+0.15), shell_exec (+0.08)"
      "Recently ineffective: search_web (-0.02), file_read (-0.01)"
- [ ] Phase detection: if >60% of recent tools are search/read, inject "SWITCH TO BUILDING"
- [ ] If >80% are write/edit with rising tension, inject "GOOD MOMENTUM — KEEP BUILDING"
- [ ] Test: verify guidance injection appears in context after 10 tool calls

---

## Chunk 5 (Hours 12-15): Inter-Eddy Communication
**Why**: Eddies in a swell batch are blind to each other. Eddy 2 re-researches
what eddy 1 already found. Wastes time and context.

- [ ] Shared store: `workspace/.swell/shared_context.json`
- [ ] Before eddy starts, load shared context (other eddies' key findings)
- [ ] After eddy completes, append its findings to shared context
- [ ] Findings format: {"eddy_id": "...", "task": "...", "key_files": [...], "decisions": [...]}
- [ ] Inject shared context into eddy system prompt: "Other workers found: ..."
- [ ] Cleanup: delete shared context after swell batch completes
- [ ] Test: fire a 3-eddy swell, verify eddy 3 sees eddy 1's output

---

## Chunk 6 (Hours 15-18): Chrome Extension Scaffold
**Why**: High-demand scaffold. Lots of people want to build browser extensions
with AI but the setup is brutal (manifest.json, content scripts, popup, etc.)

- [ ] `scaffolds/chrome-extension/` directory
- [ ] manifest.json v3 (service worker, permissions, content scripts)
- [ ] popup/index.html + popup/App.tsx (React popup UI)
- [ ] content/content.ts (page injection script)
- [ ] background/service-worker.ts (event handlers)
- [ ] Vite config with CRXJS plugin for hot reload
- [ ] README.md with load-unpacked instructions
- [ ] Add to scaffold classifier in tools/project.py
- [ ] Test: "build a chrome extension that highlights all links on a page"

---

## Chunk 7 (Hours 18-21): Electron App Scaffold
**Why**: Desktop app demand is real. Electron + React + IPC is boilerplate hell.

- [ ] `scaffolds/electron-app/` directory
- [ ] main.ts (Electron main process, BrowserWindow, IPC handlers)
- [ ] preload.ts (contextBridge, exposeInMainWorld)
- [ ] src/App.tsx (React renderer with IPC hooks)
- [ ] useIPC hook (send/receive between renderer and main)
- [ ] electron-builder config for packaging
- [ ] Vite config for electron-vite or similar
- [ ] README.md with dev + package instructions
- [ ] Add to scaffold classifier
- [ ] Test: "build a desktop markdown editor"

---

## Chunk 8 (Hours 21-24): New Components Batch 1
**Why**: The component library is the moat. More components = fewer iterations
per build = better demos.

- [ ] Rich text editor (Tiptap-based, toolbar, formatting, export)
- [ ] File manager (tree view, upload dropzone, rename, delete, breadcrumbs)
- [ ] Command palette (Cmd+K, fuzzy search, keyboard nav, action registry)
- [ ] Calendar/date picker (month view, date range, event markers)
- [ ] Add all to `scaffolds/react-app/src/components/ui/`
- [ ] Export from components index
- [ ] Test: build an app that uses each new component

---

## Chunk 9 (Hours 24-27): New Components Batch 2
**Why**: Continuing the component library expansion.

- [ ] Map component (Leaflet, markers, popups, geolocation, tile layers)
- [ ] Notification center (toast stack, persistent notifications, action buttons)
- [ ] Audio player (waveform viz, playlist, controls, progress bar)
- [ ] Video player (HLS/MP4, controls, picture-in-picture, subtitles)
- [ ] Add all to component library
- [ ] Test: build a music player app using audio player + notification components

---

## Chunk 10 (Hours 27-30): Docker Sandbox
**Why**: meanaverage's PR #4 started this. shell_exec runs on bare metal which
is scary. Docker sandbox = safe code execution.

- [ ] `exec.Dockerfile` — minimal Python + Node + common tools
- [ ] Build script that pre-builds the sandbox image
- [ ] Modify shell_exec tool: if Docker available, run inside container
- [ ] Volume mount workspace dir (read-write) + models dir (read-only)
- [ ] GPU passthrough (--gpus all) when nvidia-container-toolkit present
- [ ] Timeout enforcement (--stop-timeout)
- [ ] Fallback: if Docker not available, run on host (current behavior)
- [ ] Health check: `docker ps` integration with wave health endpoint
- [ ] Test: shell_exec "python3 -c 'print(1+1)'" runs inside container

---

## Chunk 11 (Hours 30-33): CLI Improvements
**Why**: meanaverage's PRs had good ideas. Tab completion and trace view make
the CLI feel professional.

- [ ] Tab autocomplete for slash commands (/attach, /status, /clear, etc.)
- [ ] `/attach <path>` — inject file content into next prompt
- [ ] `/detach` — remove attached files
- [ ] Trace tail view — show last N tool calls with timing
- [ ] `/status` command — model health, iteration count, tension, context usage
- [ ] Integrate with Ink CLI (cli/app.jsx) if available, Python fallback otherwise
- [ ] Test: verify tab completion works for all commands

---

## Chunk 12 (Hours 33-36): 3D Creative — Particles + GLTF
**Why**: The threejs scaffold is already strong. Adding particles and GLTF
loading makes it production-grade for 3D apps.

- [ ] Particle system component (emitter, forces, lifetime, size/color curves)
- [ ] Instanced rendering for performance (InstancedMesh)
- [ ] Preset particles: fire, smoke, rain, snow, sparks, confetti
- [ ] GLTF model loader (useGLTF hook, animation mixer, controls)
- [ ] Animation playback (play/pause/loop, blend between animations)
- [ ] Add to threejs-game scaffold components
- [ ] Test: "build a 3D scene with a character model and fire particles"

---

## Chunk 13 (Hours 36-39): 3D Creative — Post-Processing + Shaders
**Why**: Visual polish. Bloom, DOF, and custom shaders are what make demos pop.

- [ ] Post-processing pipeline (EffectComposer wrapper)
- [ ] Built-in effects: Bloom, DOF (depth of field), SSAO, Vignette, ChromaticAberration
- [ ] Custom shader component (vertex + fragment, uniforms interface)
- [ ] Volumetric fog shader (ray marching, density control, light scattering)
- [ ] Ocean rendering (FFT-based waves, foam, reflection)
- [ ] Add all to threejs-game scaffold
- [ ] Test: "build an ocean scene with fog and bloom"

---

## Chunk 14 (Hours 39-42): Phase-Based Tool Filtering + Model Probing
**Why**: Research and build phases need different tools. 2B wastes tokens on
tools it can't use well.

- [ ] Phase detection: classify current state as RESEARCH / PLAN / BUILD / VERIFY / DELIVER
- [ ] Per-phase tool subsets:
      RESEARCH: search_web, file_read, file_list, match_grep
      PLAN: plan_update, message_info
      BUILD: file_write, file_edit, shell_exec, project_init, generate_image
      VERIFY: shell_exec (build only), file_read, undertow
      DELIVER: message_result
- [ ] Phase transitions: auto-detect from tool usage patterns
- [ ] Model capability probing: on first run, send a simple coding task to model,
      measure response quality, set capability level (basic/intermediate/advanced)
- [ ] Persist capability level in config (don't re-probe every session)
- [ ] Test: verify phase transitions happen naturally during a build

---

## Chunk 15 (Hours 42-45): Quality Assessment + Screenshot Diffing
**Why**: Before iterating on an existing project, we should screenshot current
state so we know what changed.

- [ ] Before iteration: capture screenshot of current state (Playwright)
- [ ] After iteration: capture new screenshot
- [ ] Pixel-diff the two screenshots, report % changed
- [ ] If <5% changed and user asked for changes, warn "changes may not be visible"
- [ ] Store screenshots in workspace/.screenshots/ with timestamps
- [ ] Show before/after in WebUI preview tab
- [ ] Test: modify a project, verify screenshot diff detects the change

---

## Chunk 16 (Hours 45-48): Integration Testing + Cleanup + Release
**Why**: Everything built in chunks 1-15 needs to work together.

- [ ] Run full test suite, fix any failures
- [ ] Test a complex multi-component build end-to-end (dashboard with all new components)
- [ ] Test chrome extension scaffold end-to-end
- [ ] Test electron scaffold end-to-end
- [ ] Test Docker sandbox on Spark
- [ ] Update ROADMAP.md — check off everything completed
- [ ] Update README.md if needed
- [ ] Tag v0.2.0 release
- [ ] Push everything, verify Windows buddy can pull and run
- [ ] Write STATUS.md final summary

---

## STATUS.md Format
After each chunk, update STATUS.md:
```
## Chunk N — [DONE|IN PROGRESS|BLOCKED]
Started: <timestamp>
Finished: <timestamp>
Commits: <short hashes>
What was done:
- ...
Blockers:
- ...
Next: Chunk N+1
```
