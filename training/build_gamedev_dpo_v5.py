#!/usr/bin/env python3
"""build_gamedev_dpo_v5.py -- DPO v5 for gamedev adapter.

12 pairs targeting two eval failures at baseline:
  GHF09: Complex multi-system game + "plan carefully" -> plan_update FIRST
  GHF10: After successful build -> undertow BEFORE message_result

These are the last two uncovered L4 scenarios.
"""
import json, os, sys
from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import TOOLS

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/gamedev_dpo_v5.jsonl"
TODAY = "2026-04-12"

# Minimal game system prompt (full version is in eval_gamedev.py GAME_SYSTEM)
GAME_SYSTEM = (
    "You are a gamedev agent using the Tsunami Engine (WebGPU, 2D/3D, physics, AI). "
    "Tools: project_init, file_write, file_edit, shell_exec, undertow, "
    "plan_update, search_web, message_result, message_chat."
)


def tok_apply(tok, msgs):
    result = tok.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    return result if isinstance(result, str) else tok.decode(result)


def s():
    return {"role": "system", "content": GAME_SYSTEM}

def u(t):
    return {"role": "user", "content": t}

def tc(tool_name, **kw):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"type": "function", "function": {"name": tool_name, "arguments": kw}}
    ]}

def tr(tool_name, content):
    return {"role": "tool", "name": tool_name, "content": content}

def pair(prompt_msgs, chosen_msgs, rejected_msgs, fault_id, note):
    return {
        "prompt": prompt_msgs,
        "chosen": chosen_msgs,
        "rejected": rejected_msgs,
        "source_bug": fault_id,
        "note": note,
        "images": [],
        "date": TODAY,
    }


# ── GHF09: Complex game planning -> plan_update first ────────────────────────

def ghf09_pairs():
    complex_prompts = [
        "Build a full MMORPG with character classes, skill trees, inventory, crafting, dungeons, and a world map. Plan carefully before building.",
        "Build a city-builder simulation with population management, resource chains, economy, disasters, and tech tree. Think it through first.",
        "Build a tactical RPG with grid-based combat, multiple character classes, elemental affinities, and a campaign mode. Plan it out carefully.",
    ]

    plan_mmorpg = tc("plan_update",
        goal="MMORPG: character classes + skill trees + inventory + crafting + dungeons + world map",
        phases=[
            {"phase": 1, "action": "project_init", "note": "Scaffold game"},
            {"phase": 2, "action": "file_write main.ts", "note": "Game state machine: login/world/dungeon screens"},
            {"phase": 3, "action": "file_write player.ts", "note": "Character class + skill tree + inventory"},
            {"phase": 4, "action": "file_write world.ts", "note": "World map + zone transitions"},
            {"phase": 5, "action": "file_write dungeon.ts", "note": "Combat + loot + boss"},
            {"phase": 6, "action": "shell_exec build + undertow QA"},
        ])

    plan_city = tc("plan_update",
        goal="City-builder: population + resources + economy + disasters + tech tree",
        phases=[
            {"phase": 1, "action": "project_init", "note": "Scaffold game"},
            {"phase": 2, "action": "file_write main.ts", "note": "Simulation loop: tick economy + population + disasters"},
            {"phase": 3, "action": "file_write city.ts", "note": "City grid + zones + buildings"},
            {"phase": 4, "action": "file_write economy.ts", "note": "Resource chains + trade + tech"},
            {"phase": 5, "action": "shell_exec build + undertow QA"},
        ])

    plan_tactical = tc("plan_update",
        goal="Tactical RPG: grid combat + classes + elemental affinities + campaign",
        phases=[
            {"phase": 1, "action": "project_init", "note": "Scaffold game"},
            {"phase": 2, "action": "file_write main.ts", "note": "Battle screen + grid + turn manager"},
            {"phase": 3, "action": "file_write unit.ts", "note": "Character classes + elements + skills"},
            {"phase": 4, "action": "file_write campaign.ts", "note": "Map + missions + progression"},
            {"phase": 5, "action": "shell_exec build + undertow QA"},
        ])

    init_wrong = tc("project_init", name="mmorpg")
    write_wrong = tc("file_write", path="deliverables/mmorpg/src/main.ts", content="// placeholder")

    return [
        # 1. "Plan carefully" + complex multi-system -> plan_update first
        pair([s(), u(complex_prompts[0])],
             [plan_mmorpg],
             [init_wrong],
             "GHF09",
             "gamedev: 'plan carefully' + MMORPG multi-system -> plan_update BEFORE project_init"),

        # 2. "Think it through" + complex game -> plan_update first
        pair([s(), u(complex_prompts[1])],
             [plan_city],
             [tc("project_init", name="city-builder")],
             "GHF09b",
             "gamedev: 'think it through' + city-builder simulation -> plan_update BEFORE project_init"),

        # 3. "Plan it out" + tactical RPG -> plan_update first
        pair([s(), u(complex_prompts[2])],
             [plan_tactical],
             [tc("project_init", name="tactical-rpg")],
             "GHF09c",
             "gamedev: 'plan it out' + tactical RPG multi-system -> plan_update BEFORE project_init"),

        # 4. Complex game: after plan, project_init (not file_write directly)
        pair([s(), u(complex_prompts[0]), plan_mmorpg, tr("plan_update", "Plan saved.")],
             [tc("project_init", name="mmorpg")],
             [write_wrong],
             "GHF09d",
             "gamedev: after plan_update for MMORPG -> project_init next (not file_write)"),

        # 5. Very complex (7+ systems) always needs plan regardless of explicit "plan" word
        pair([s(), u("Build an open-world survival game with crafting, building, combat, weather, day/night, NPCs, and permadeath.")],
             [tc("plan_update",
                goal="Open-world survival: crafting+building+combat+weather+day-night+NPCs+permadeath",
                phases=[
                    {"phase": 1, "action": "project_init"},
                    {"phase": 2, "action": "file_write main.ts", "note": "Game loop + world state"},
                    {"phase": 3, "action": "file_write player.ts", "note": "Survival stats, inventory, combat"},
                    {"phase": 4, "action": "file_write world.ts", "note": "Procedural world, weather, NPCs"},
                    {"phase": 5, "action": "shell_exec build + undertow"},
                ])],
             [tc("project_init", name="survival-game")],
             "GHF09e",
             "gamedev: 7-system open-world -> plan_update even without explicit 'plan' word"),

        # 6. Simple game does NOT need plan_update (control pair)
        pair([s(), u("Build a snake game.")],
             [tc("project_init", name="snake")],
             [tc("plan_update",
                goal="Snake game",
                phases=[{"phase": 1, "action": "project_init"}])],
             "GHF09f",
             "gamedev: simple 1-system game (snake) -> project_init directly, no plan needed"),
    ]


# ── GHF10: After successful build -> undertow BEFORE message_result ───────────

def ghf10_pairs():
    """After shell_exec builds successfully, undertow before message_result."""

    # Common game trajectory prefix
    def game_prefix(game_name, content_summary):
        return [
            s(),
            u(f"Build a {game_name} game."),
            tc("project_init", name=game_name.replace(" ", "-")),
            tr("project_init", f"Scaffolded '{game_name.replace(' ', '-')}'. Write src/main.ts."),
            tc("file_write", path=f"deliverables/{game_name.replace(' ', '-')}/src/main.ts",
               content=f"// {game_name} — {content_summary}\nimport {{ Game }} from 'tsunami-engine'\nconst game = new Game({{ mode: '2d' }})\ngame.start()"),
            tr("file_write", "Written."),
            tc("shell_exec", command=f"cd deliverables/{game_name.replace(' ', '-')} && npm run build"),
            tr("shell_exec", "Build successful. dist/index.html ready."),
        ]

    tetris_prefix = game_prefix("tetris", "falling blocks, line clear")
    pong_prefix = game_prefix("pong", "paddle, ball, score")
    asteroids_prefix = game_prefix("asteroids", "ship, rocks, bullets")

    return [
        # 1. After build success -> undertow next (not message_result)
        pair(tetris_prefix,
             [tc("undertow", url="http://localhost:5173")],
             [tc("message_result", text="Tetris game built!")],
             "GHF10",
             "gamedev: after build success -> undertow BEFORE message_result"),

        # 2. After build success -> undertow (not shell_exec again)
        pair(pong_prefix,
             [tc("undertow", url="http://localhost:5173")],
             [tc("shell_exec", command="cd deliverables/pong && npm run build")],
             "GHF10b",
             "gamedev: after successful build -> undertow next, not another shell_exec"),

        # 3. After undertow -> message_result (not loop)
        pair(asteroids_prefix + [
                tc("undertow", url="http://localhost:5173"),
                tr("undertow", "Screenshot: ship in center, asteroids rotating, score=0."),
             ],
             [tc("message_result", text="Asteroids game: WASD to move, space to shoot, avoid asteroids.")],
             [tc("undertow", url="http://localhost:5173")],
             "GHF10c",
             "gamedev: after undertow screenshot -> message_result (not another undertow)"),

        # 4. Partial write -> build failure -> fix -> build success -> undertow
        pair([s(), u("Build a breakout game."),
              tc("project_init", name="breakout"),
              tr("project_init", "Scaffolded. Write src/main.ts."),
              tc("file_write", path="deliverables/breakout/src/main.ts",
                 content="import { Game } from 'tsunami-engine'\nconst game = new Game({ mode: '2d' })\ngame.start()"),
              tr("file_write", "Written."),
              tc("shell_exec", command="cd deliverables/breakout && npm run build"),
              tr("shell_exec", "Build successful. dist/index.html ready."),
             ],
             [tc("undertow", url="http://localhost:5173")],
             [tc("message_result", text="Breakout game ready!")],
             "GHF10d",
             "gamedev: even after first-attempt build success -> undertow before message_result"),

        # 5. After failed build then fixed build -> still undertow
        pair([s(), u("Build a platformer."),
              tc("project_init", name="platformer"),
              tr("project_init", "Scaffolded. Write src/main.ts."),
              tc("file_write", path="deliverables/platformer/src/main.ts", content="// buggy"),
              tr("file_write", "Written."),
              tc("shell_exec", command="cd deliverables/platformer && npm run build"),
              tr("shell_exec", "Error: Missing import 'physics' from 'tsunami-engine'"),
              tc("file_edit", path="deliverables/platformer/src/main.ts",
                 old_text="// buggy",
                 new_text="import { Game, PhysicsWorld } from 'tsunami-engine'\nconst game = new Game({ mode: '2d' })\ngame.start()"),
              tr("file_edit", "Edited."),
              tc("shell_exec", command="cd deliverables/platformer && npm run build"),
              tr("shell_exec", "Build successful. dist/index.html ready."),
             ],
             [tc("undertow", url="http://localhost:5173")],
             [tc("message_result", text="Platformer built!")],
             "GHF10e",
             "gamedev: fix then build success -> undertow still required before message_result"),

        # 6. After undertow with good screenshot -> message_result (not more builds)
        pair([s(), u("Build a space shooter."),
              tc("project_init", name="space-shooter"),
              tr("project_init", "Scaffolded. Write src/main.ts."),
              tc("file_write", path="deliverables/space-shooter/src/main.ts",
                 content="import { Game } from 'tsunami-engine'\nconst game = new Game({ mode: '2d' })\ngame.start()"),
              tr("file_write", "Written."),
              tc("shell_exec", command="cd deliverables/space-shooter && npm run build"),
              tr("shell_exec", "Build successful."),
              tc("undertow", url="http://localhost:5173"),
              tr("undertow", "Screenshot: black space background, player ship at bottom, stars scrolling, score display."),
             ],
             [tc("message_result", text="Space shooter: arrow keys to move, space to fire. Stars scroll, score on HUD.")],
             [tc("shell_exec", command="cd deliverables/space-shooter && npm run build")],
             "GHF10f",
             "gamedev: after undertow with good screenshot -> message_result (not another build)"),
    ]


def main():
    print("Loading tokenizer...")
    tok = AutoTokenizer.from_pretrained(MODEL)
    print("Tokenizer loaded.")

    all_pairs = []
    for fn in [ghf09_pairs, ghf10_pairs]:
        pairs = fn()
        for p in pairs:
            p["prompt"] = tok_apply(tok, p["prompt"])
            p["chosen"] = tok_apply(tok, p["chosen"])
            p["rejected"] = tok_apply(tok, p["rejected"])
        all_pairs.extend(pairs)
        print(f"  {fn.__name__}: {len(pairs)} pairs")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for p in all_pairs:
            f.write(json.dumps(p) + "\n")

    print(f"\nTotal: {len(all_pairs)} pairs")
    print(f"Wrote to {OUT_PATH}")

    # Combine with existing gamedev DPO combined
    combined_path = "workspace/training_data/gamedev_dpo_combined_v4.jsonl"
    prev_path = "workspace/training_data/gamedev_dpo_combined_v3.jsonl"
    combined = []
    if os.path.exists(prev_path):
        with open(prev_path) as f:
            combined = [json.loads(l) for l in f if l.strip()]
    combined.extend(all_pairs)
    with open(combined_path, "w") as f:
        for p in combined:
            f.write(json.dumps(p) + "\n")
    print(f"Combined_v4: {len(combined)} pairs -> {combined_path}")


if __name__ == "__main__":
    main()
