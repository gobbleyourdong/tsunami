# Building — Research, Build, Test

## 1. Research on GitHub (MAX 2 searches)

Search for real implementations: `search_web(query, search_type="code")`
Read the actual source. Study the patterns. Don't guess at APIs.

## 2. Scaffold with webdev_scaffold

ALWAYS call webdev_scaffold first. It sets up Vite + React + TypeScript + Tailwind.
Then write .tsx components in src/. Never write vanilla HTML/JS.

## 3. Decompose into small .tsx components

Each file does ONE thing (<100 lines). Each file fits in your head.

Example for a game:
```
src/App.tsx              — main shell, screen routing
src/components/Game.tsx  — canvas + game loop
src/components/HUD.tsx   — score, stats display
src/components/Menu.tsx  — start/game over screens
src/hooks/useGameLoop.ts — requestAnimationFrame
src/hooks/useAudio.ts    — Web Audio API sounds
src/hooks/useInput.ts    — keyboard handling
src/game/engine.ts       — game logic, scoring
src/game/types.ts        — TypeScript interfaces
```

Example for a web app:
```
src/App.tsx              — main layout + routing
src/components/Header.tsx
src/components/Card.tsx
src/hooks/useApi.ts      — data fetching
src/types.ts             — interfaces
```

## 4. Test with undertow, fix, repeat

Read the QA report. Fix failures. Test again. Repeat until it works.

## 5. Deliver only when it works
