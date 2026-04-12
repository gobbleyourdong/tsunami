#!/usr/bin/env python3
"""build_gamedev_dpo_v6.py -- DPO v6 for gamedev adapter.

18 pairs (3 per fault, 6 faults) targeting v9 patterns:
  GHF-ECS1: Multi-file ECS (entity.ts + components.ts + systems.ts) vs monolithic main.ts
  GHF-ECS2: Systems are pure functions over EntityManager, not methods
  GHF-SAVE1: Dedicated saveState.ts module, not inline localStorage in game loop
  GHF-SAVE2: Typed SaveData interface, not untyped JSON.parse
  GHF-PROC1: Procedural generation in separate dungeon.ts, not in main.ts
  GHF-MENU1: type Scene = 'menu'|'game'|'gameover' dispatch, not boolean flags
"""
import json, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

OUT = Path("workspace/training_data/gamedev_dpo_v6.jsonl")
TODAY = str(date.today())


def pair(source_bug, chosen, rejected, note):
    return {
        "prompt": f"[GHF probe: {source_bug}]",
        "chosen": chosen,
        "rejected": rejected,
        "source_bug": source_bug,
        "note": note,
        "images": [],
        "date": TODAY,
    }


# ── GHF-ECS1: Multi-file ECS vs monolithic main.ts ────────────────────────────
GHFECS1_PAIRS = [
    pair("GHF-ECS1a",
         chosen="ECS game plan: entity.ts (EntityManager), components.ts (interface defs), systems.ts (pure functions), main.ts (wiring)",
         rejected="ECS game plan: one large main.ts with all entity tracking, component objects, and game systems inline",
         note="ECS means separate files: EntityManager in entity.ts, component types in components.ts, systems in systems.ts"),
    pair("GHF-ECS1b",
         chosen="file_write entity.ts → file_write components.ts → file_write systems.ts → file_write main.ts",
         rejected="file_write main.ts (all ECS logic in one 600-line file)",
         note="ECS requires 4 files; writing everything in main.ts defeats the purpose of the architecture"),
    pair("GHF-ECS1c",
         chosen="EntityManager in entity.ts exports: create(), destroy(), add<T>(), get<T>(), has(), query(...types)",
         rejected="const entities: Map<number, any> = new Map() // inline in main.ts without a manager class",
         note="Entity manager belongs in its own module; inline Maps in main.ts mix concerns and aren't reusable"),
]

# ── GHF-ECS2: Systems as pure functions ────────────────────────────────────────
GHFECS2_PAIRS = [
    pair("GHF-ECS2a",
         chosen="export function moveSystem(em: EntityManager, dt: number) { for (const id of em.query(C.Position, C.Velocity)) { ... } }",
         rejected="class MoveSystem { update(em, dt) { ... } }  // class-based systems add boilerplate with no benefit",
         note="Systems are pure functions (em, dt) => void — no class needed; classes add constructor overhead for no gain"),
    pair("GHF-ECS2b",
         chosen="systems.ts exports: moveSystem, renderSystem, aiSystem, collisionSystem — all (em, ...) => void",
         rejected="class GameWorld { move() {...} render() {...} ai() {...} }  // one big god-class with all systems",
         note="Pure function systems are tree-shakeable, testable, and composable; a GameWorld god-class is a monolith"),
    pair("GHF-ECS2c",
         chosen="main.ts game loop: aiSystem(em); moveSystem(em, dt); collisionSystem(em); renderSystem(em, ctx)",
         rejected="main.ts: entities.forEach(e => { e.x += e.vx; e.y += e.vy; }) // per-entity ad-hoc update",
         note="System functions iterate over all relevant entities; ad-hoc per-entity code bypasses the ECS pattern"),
]

# ── GHF-SAVE1: Dedicated saveState.ts module ─────────────────────────────────
GHFSAVE1_PAIRS = [
    pair("GHF-SAVE1a",
         chosen="saveState.ts: export function saveGame(data), loadGame(): SaveData | null, hasSave(), deleteSave()",
         rejected="// Inline in main.ts: localStorage.setItem('save', JSON.stringify({coins, level, x, y})) scattered through game loop",
         note="Save/load logic belongs in saveState.ts; inline localStorage calls scatter persistence logic across the game loop"),
    pair("GHF-SAVE1b",
         chosen="file_write saveState.ts (save module) → file_write main.ts (imports saveGame/loadGame)",
         rejected="file_write main.ts (save logic inline: localStorage.getItem/setItem in input handler, level-up handler, etc.)",
         note="Separate saveState.ts keeps game loop clean; one save module is easier to extend (slots, cloud sync)"),
    pair("GHF-SAVE1c",
         chosen="import { saveGame, loadGame, hasSave } from './saveState'  // clear, named API",
         rejected="// No module — manual: localStorage.setItem('game', JSON.stringify({...})) at each save point",
         note="A dedicated save module centralizes the SAVE_KEY constant, JSON parse/stringify, and null guard"),
]

# ── GHF-SAVE2: Typed SaveData interface ───────────────────────────────────────
GHFSAVE2_PAIRS = [
    pair("GHF-SAVE2a",
         chosen="interface SaveData { coins: number; level: number; playerX: number; playerY: number; timestamp: number }",
         rejected="const save = JSON.parse(localStorage.getItem('save') || '{}')  // untyped, no type safety on load",
         note="Define a SaveData interface; TypeScript catches field mismatches at compile time vs silent runtime bugs"),
    pair("GHF-SAVE2b",
         chosen="export function loadGame(): SaveData | null { ... return JSON.parse(raw) as SaveData }",
         rejected="export function loadGame() { return JSON.parse(localStorage.getItem('save') || 'null') }  // any type",
         note="Return type SaveData | null forces callers to handle the null case and use typed fields"),
    pair("GHF-SAVE2c",
         chosen="saveGame({ coins, level, playerX: px, playerY: py })  // type-checked call site",
         rejected="localStorage.setItem('save', JSON.stringify({ coins, lvl: level, x: px }))  // field name inconsistency",
         note="The SaveData interface enforces consistent field names; raw object literals let typos silently diverge"),
]

# ── GHF-PROC1: Procedural generation in separate module ──────────────────────
GHFPROC1_PAIRS = [
    pair("GHF-PROC1a",
         chosen="file_write dungeon.ts (BSP generator, TILE constants, generateDungeon() exports) → file_write main.ts (imports dungeon)",
         rejected="file_write main.ts with all BSP splitting, room carving, corridor code inline before the game loop",
         note="Dungeon generator is a pure function (cols, rows) => { tiles, rooms, start }; belongs in its own module"),
    pair("GHF-PROC1b",
         chosen="dungeon.ts: export function generateDungeon(cols, rows): { tiles, rooms, start }  // reusable, testable",
         rejected="// Inline in main.ts: function split(node) { ... function carveRoom() { ... function carveCorridor() { ...}}}",
         note="Procedural generation logic is complex enough to deserve its own file; inline it and main.ts becomes unreadable"),
    pair("GHF-PROC1c",
         chosen="import { generateDungeon, TILE } from './dungeon'  // clean import, dungeon.ts is self-contained",
         rejected="// Everything in main.ts: const TILE = ...; function randInt() ...; function generateDungeon() ...; // 200 lines before game loop",
         note="Separate dungeon.ts exports TILE constants + generateDungeon; main.ts is just render loop + input"),
]

# ── GHF-MENU1: Scene type dispatch vs boolean flags ───────────────────────────
GHFMENU1_PAIRS = [
    pair("GHF-MENU1a",
         chosen="type Scene = 'menu' | 'game' | 'pause' | 'gameover'\nlet scene: Scene = 'menu'\n// loop: if(scene==='menu') drawMenu()",
         rejected="let inMenu = true, isPaused = false, isGameOver = false  // booleans conflict (inMenu+isGameOver both true?)",
         note="Scene type string is mutually exclusive by design; multiple booleans can reach impossible states"),
    pair("GHF-MENU1b",
         chosen="function loop() {\n  if (scene === 'menu') drawMenu()\n  else if (scene === 'game') drawGame()\n  else if (scene === 'gameover') drawGameOver()\n}",
         rejected="function loop() {\n  if (inMenu) { drawMenu() }\n  if (!inMenu && !isPaused) { drawGame() }\n  if (isGameOver) { drawGameOver() }\n}",
         note="Scene dispatch with a single variable is cleaner than guarding multiple boolean combinations"),
    pair("GHF-MENU1c",
         chosen="To enter pause: scene = 'pause'  // one assignment, clearly named",
         rejected="To enter pause: isPaused = true; isPlaying = false  // two assignments, both must stay in sync",
         note="Single scene variable transition; boolean pairs require keeping both in sync or the state diverges"),
]


def main():
    all_pairs = GHFECS1_PAIRS + GHFECS2_PAIRS + GHFSAVE1_PAIRS + GHFSAVE2_PAIRS + GHFPROC1_PAIRS + GHFMENU1_PAIRS
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for p in all_pairs:
            f.write(json.dumps(p) + "\n")
    print(f"Wrote {len(all_pairs)} pairs to {OUT}")
    for p in all_pairs:
        print(f"  {p['source_bug']}: {p['note'][:65]}")


if __name__ == "__main__":
    main()
