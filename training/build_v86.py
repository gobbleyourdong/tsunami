#!/usr/bin/env python3
"""v86 = v80 base + 3 plan_update training examples (broader signal).

v80 (champion 460): 19 examples
v81 (1 plan example): 450 — HF06 regressed
v85 (more depth): 460 (same plateau, HF09 still fails)

v81 showed 1 plan example causes HF06 collateral damage.
v85 showed depth doesn't unlock HF09.

v86: try 3 plan examples instead. Stronger signal might:
  - Push the model to use plan_update on "Plan needed" prompts
  - Without overfitting any single trigger pattern
  - HF06 message_chat behavior preserved because pattern is different

3 varied prompts:
  1. "Build a Spotify-style music player with playlists and search. Plan needed."
  2. "Build a multi-step form wizard with validation. Plan carefully."
  3. "Build a full-featured photo editor with filters and crop. Plan first."

Total: 22 examples (10 happy + 6 pipeline L3 + 3 bare L3 + 3 plan).
Train at v80 hyperparams (lr=2e-4, epochs=10, grad_accum=4 = 55 steps).
"""
import json
import os
import sys

from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS, build_messages, build_pipeline
from build_v69 import APPS as APPS_V69
from build_v73 import build_l3_direct_fix, L3_EXAMPLES as V73_L3
from build_v78 import bare_l3, BARE_L3

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v86.jsonl"


def build_plan_first(user_prompt, goal, phases, name, app_code):
    """Plan-first example."""
    turns = []
    turns.append(("plan_update", {"goal": goal, "phases": phases},
                  f"Plan accepted with {len(phases)} phases."))
    turns.append(("project_init", {"name": name}, f"Created project deliverables/{name}"))
    turns.append(("file_write", {"path": "src/App.tsx", "content": app_code},
                  "Wrote src/App.tsx"))
    turns.append(("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
                  "vite v5.0.0 building... built in 1.23s"))
    turns.append(("undertow", {"path": f"deliverables/{name}/dist/index.html", "expect": "complex app"},
                  "Verified."))
    turns.append(("message_result", {"text": f"Built {name} per plan."}, "Delivered."))
    return build_messages(user_prompt, turns)


PLAN_EXAMPLES = [
    {
        "user_prompt": "Build a Spotify-style music player with playlists and search. Plan needed.",
        "goal": "Build music player with playlists, search",
        "phases": ["scaffold", "player UI", "playlist state", "search", "deliver"],
        "name": "music-player-plan",
        "app_code": "import { useState } from 'react'\nexport default function App() {\n  const [q, setQ] = useState('')\n  const tracks = ['Song A', 'Song B']\n  return <div><input value={q} onChange={e=>setQ(e.target.value)} /><ul>{tracks.filter(t=>t.includes(q)).map(t=><li key={t}>{t}</li>)}</ul></div>\n}",
    },
    {
        "user_prompt": "Build a multi-step form wizard with validation. Plan carefully.",
        "goal": "Build multi-step form wizard with validation",
        "phases": ["scaffold", "step1", "step2", "validation", "deliver"],
        "name": "form-wizard-plan",
        "app_code": "import { useState } from 'react'\nexport default function App() {\n  const [step, setStep] = useState(1)\n  return <div><h2>Step {step}</h2><button onClick={()=>setStep(step+1)}>Next</button></div>\n}",
    },
    {
        "user_prompt": "Build a full-featured photo editor with filters and crop. Plan first.",
        "goal": "Build photo editor with filters and crop",
        "phases": ["scaffold", "image upload", "filters", "crop", "deliver"],
        "name": "photo-editor-plan",
        "app_code": "import { useState } from 'react'\nexport default function App() {\n  const [filter, setFilter] = useState('none')\n  return <div><img src=\"\" style={{filter}} /><button onClick={()=>setFilter('grayscale(1)')}>Gray</button></div>\n}",
    },
]


def main():
    print(f"Loading: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    assert "explicitly asks for a plan" in SYSTEM_TEXT, "system prompt incorrect"

    examples = []

    # 1. 10 happy path
    for name, desc, files in APPS_V69:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 2. 6 pipeline L3
    for ex in V73_L3:
        msgs = build_l3_direct_fix(ex["name"], ex["desc"], ex["files"], ex["error"], ex["fix_call"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 3. 3 bare L3
    for sc in BARE_L3:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 4. 3 plan-first examples (NEW)
    for p in PLAN_EXAMPLES:
        msgs = build_plan_first(p["user_prompt"], p["goal"], p["phases"], p["name"], p["app_code"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    print(f"\nTotal: {len(examples)} examples")
    print("  10 happy / 6 pipeline L3 / 3 bare L3 / 3 plan-first")

    starts_bos = sum(1 for ex in examples if ex["text"].startswith("<bos>"))
    print(f"Starts with <bos>: {starts_bos}/{len(examples)}")

    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"Wrote {len(examples)} examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
