# Plan: Manus-Level Web App Building

## The Goal
One prompt → complete, working, deployable web app. No coding knowledge needed.
"Build me an expense tracker" → fully functional React+TS app served on localhost.

## What Works Today
- 9B wave can write React/TSX components (proven: direct prompting produces valid code)
- 2B eddies can write focused leaf components in parallel (proven: swell + write_targets)
- Vite build catches type errors (proven: compile check loop)
- Undertow catches visual/interaction bugs (proven: lever system + eddy vision)
- Auto-serve with HMR (proven: Vite dev server on port 9876)
- Code tension feeds into pressure system (proven: lever fail ratio)

## What Doesn't Work Yet
1. **9B can't set up projects from scratch** — writes components but skips package.json, configs
2. **9B ignores multi-step build instructions** — does step 1, forgets steps 2-7
3. **No compile-fix loop in the agent** — compile errors aren't automatically fed back
4. **Swell not used automatically** — wave writes files sequentially instead of firing eddies
5. **App.tsx (the orchestrator) often left as template** — wave writes leaves but not the root
6. **Auto-serve triggers but undertow doesn't test the served app** — QA uses python http.server instead of Vite

## The Fix (in order of priority)

### Phase 1: Reliable Project Setup
The 9B can't write 6 config files reliably. Instead of fighting this:
- Create a `project_init` tool that writes ONLY infrastructure (package.json, index.html, vite.config, tsconfig, main.tsx)
- The tool takes just a project name and a list of npm dependencies
- The wave calls it once, gets a blank project, then writes all src/ files
- This is NOT hardcoding game logic — it's the equivalent of `npm create vite`
- Test: wave calls project_init("excel-diff", ["xlsx"]) → blank project ready

### Phase 2: Compile-Fix Loop in Agent
After any file_write to a Vite project:
- Auto-run `npx vite build` 
- If errors: inject them as system note with the exact file + line
- Wave reads errors and fixes (it's good at this — proven with TypeScript)
- Repeat until clean build
- Test: write a component with a typo → agent auto-detects and fixes

### Phase 3: Wave Writes App.tsx Last
The orchestrator file (App.tsx) must be written AFTER all components exist.
- Track which components have been written in the session
- When wave calls message_result, check if App.tsx imports all written components
- If not, inject: "You wrote GameHUD.tsx and LetterFalls.tsx but App.tsx doesn't import them"
- Test: wave writes 3 components → App.tsx automatically imports all 3

### Phase 4: Swell for Parallel Component Writing
The wave should decompose and fire eddies automatically:
- Wave writes types.ts first (the shared vocabulary)
- Wave calls swell with [{prompt, target}] for each component
- 2B eddies write leaf components (hooks, simple UI) in parallel
- Wave writes complex files (App.tsx, engine logic) itself
- Test: "build a quiz app" → types.ts + 4 eddies fire + App.tsx written by wave

### Phase 5: Live QA via Served App
The undertow should test the actual Vite dev server, not a separate http.server:
- After build passes, undertow connects to localhost:9876
- Pulls levers against the live app (screenshot, click, type, motion)
- Results feed back to wave for fixing
- Test: app serves → undertow finds "button doesn't work" → wave fixes → undertow re-tests

### Phase 6: End-to-End One-Prompt Flow
Everything wired together:
1. User: "Build an expense tracker"
2. Wave: project_init("expense-tracker", []) → blank Vite+React+TS project
3. Wave: writes types.ts with interfaces
4. Wave: swell fires eddies for leaf components
5. Wave: writes App.tsx importing everything
6. Auto: vite build → errors? → wave fixes → rebuild
7. Auto: vite dev server on 9876, HMR active
8. Auto: undertow tests live app → failures? → wave fixes → retest
9. Wave: message_result → "Your app is live at localhost:9876"

## Test Suite (run after each change)
- `tests/run_excel_diff.py` — real app, business use case
- `tests/run_rhythm.py` — game, interactive, needs physics/animation
- `tests/run_test_calc.py` — simple, baseline
- `tests/run_test_quiz.py` — medium complexity

Each is ONE PROMPT. No hardcoding. Pass = the app works. Fail = framework needs fixing.

## Success Criteria
- Any of the 4 test prompts produces a working app that compiles and renders
- The user never writes code
- The user never configures anything
- The app is served live on localhost:9876 with HMR
- Total time: under 15 minutes for a simple app, under 30 for complex
