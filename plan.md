# Plan: One-Prompt Web App Building

## The Goal
One prompt → complete, working, deployable web app. No coding knowledge needed.

## Architecture
- **Scaffold CDN**: 7 pre-built templates, each compiles clean out of the box
- **Requirement classifier**: analyzes prompt → picks the right scaffold
- **README as instruction set**: model reads scaffold README, knows what's available
- **Auto-compile**: vite build after every .tsx write, errors injected as system notes
- **Auto-serve**: Vite dev server with HMR, starts on first file write
- **Stub detection**: blocks delivery if App.tsx not wired but components exist

## Scaffolds (7)
| Scaffold | Stack | Pre-built Components |
|----------|-------|---------------------|
| react-app | React+TS+Vite | Dark theme, CSS utilities |
| dashboard | + recharts | Layout, Sidebar, StatCard, DataTable, Card |
| form-app | + xlsx + papaparse | FileDropzone, DataTable, parseFile |
| landing | | Navbar, Hero, Section, FeatureGrid, Footer |
| fullstack | + Express + SQLite | CRUD API, useApi hook, server/index.js |
| threejs-game | + R3F + Rapier | Scene, Ground, Box, Sphere, HUD |
| pixijs-game | + PixiJS + Matter.js | GameCanvas, Physics2D, createRect/Circle/Text |

## Test Results
| App | Iterations | Scaffold | Renders |
|-----|-----------|----------|---------|
| Calculator | 10 | react-app | ✅ Grid card |
| Quiz | 34 | react-app | ✅ Start screen |
| Excel Diff | 17 | form-app | ✅ File upload |
| Snake | 12 | pixijs-game | ✅ Game grid |
| Todo | 25 | fullstack | ✅ Styled UI |
| Landing | 23 | landing | ✅ Hero + features |
| Rhythm | 15 | react-app | ✅ Falling letters |
| Crypto Dash | 17 | dashboard | ✅ Stat cards + charts |

## Key Fixes (in order of impact)
1. **Scaffold READMEs** → 55% fewer iterations, proper layouts
2. **App.tsx FIRST** → no more stub deliveries on complex apps
3. **Requirement classifier** → picks right scaffold automatically
4. **Auto-compile** → catches type errors immediately
5. **Base dark theme** → all apps look professional without custom CSS
6. **Global React** → fixes React.FC without import
7. **Unicode/newline escape fix** → proper symbols in generated code
8. **Stub detection** → forces App.tsx wiring before delivery
9. **CSS import instruction** → dark theme always loads

## What's Next
- More scaffolds (realtime/websocket, data-viz/d3, mobile/expo)
- Richer scaffold components (more pre-built UI)
- The 9B still overwrites main.tsx sometimes — need file protection
- Parallel eddy builds (swell) for complex apps
- Undertow QA integrated into the auto-build loop
