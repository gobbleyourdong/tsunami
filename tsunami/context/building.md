# Building — Plan, Research, Build, Test

## 1. Plan quickly, then build

Use plan_update to outline the component files you'll write. One iteration.
Don't write plan files to disk — just plan in your head and start coding.

## 2. Research on GitHub (MAX 3 searches)

Search for real implementations: `search_web(query, search_type="code")`
Read the actual source. Study the patterns. Don't guess at APIs.

LIMIT: 3 searches max, then BUILD. Don't get stuck researching forever.
Research is prep, not the deliverable.

## 3. Decompose into small files

NEVER write one massive file. Break into components:
- Each file does ONE thing (<100 lines)
- Each file fits in your head — you can reason about it fully
- index.html is a thin shell that imports everything else

Example for a game:
```
style.css      — all styling
audio.js       — sound effects
game.js        — state, scoring, logic
renderer.js    — drawing, animations
input.js       — keyboard/mouse handling
index.html     — imports and glues together
```

Example for a web app:
```
style.css      — all styling
api.js         — data fetching
state.js       — app state management
components.js  — UI components
app.js         — main logic
index.html     — shell
```

Why: a 900-line monolith pollutes context. You forget what you declared 400 lines ago. Small files = clean context = fewer bugs.

## 4. Build from researched patterns

Use what you found. Don't improvise.

## 4. Test with undertow

```
undertow(path="index.html", expect="description of the core user journey")
```

Read the report. Fix failures. Test again. Repeat until the core journey works.
Motion detection catches dead physics. Key/click checks catch broken controls.

## 5. Deliver only when it works

Not when it renders. When it PLAYS / FUNCTIONS / RESPONDS.
