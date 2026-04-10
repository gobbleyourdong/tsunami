#!/usr/bin/env python3
"""v81 = v80 base + 1 plan_update training example for explicit plan requests.

v79 (463): L1 correct 7/40 (plan over-trigger), L5 100% (plan enables expense tracker)
v80 (460): L1 correct 34/40 (plan tightened), L5 89% (IH03 fails again)

v81 strategy: Keep v80 system prompt ("explicitly asks for plan"), but ADD 1
training example teaching plan_update flow for HF09's exact pattern.

This gives the model:
  - Tight system trigger (doesn't fire for L1 format tests)
  - 1 concrete example of WHEN to fire (user says "Plan needed")
  - Hope that plan_update structuring helps L5 IH03 too

Total: 20 examples (10 happy + 6 pipeline L3 + 3 bare L3 + 1 plan).
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
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v81.jsonl"


def build_plan_first(user_prompt, goal, phases, name, desc, files):
    """Plan-first example for 'Plan needed' prompts."""
    turns = []
    turns.append(("plan_update", {"goal": goal, "phases": phases},
                  f"Plan accepted with {len(phases)} phases."))
    turns.append(("project_init", {"name": name}, f"Created project deliverables/{name}"))
    for path, content in files:
        turns.append(("file_write", {"path": path, "content": content}, f"Wrote {path}"))
    turns.append(("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
                  "vite v5.0.0 building... built in 1.23s"))
    turns.append(("undertow", {"path": f"deliverables/{name}/dist/index.html", "expect": desc},
                  "Verified."))
    turns.append(("message_result", {"text": f"Built {name} per plan: {desc}."}, "Delivered."))
    return build_messages(user_prompt, turns)


# One plan example matching HF09's pattern "X. Plan needed."
PLAN_EXAMPLE = {
    "user_prompt": "Build a music player with playlists, search, and favorites. Plan needed.",
    "goal": "Build music player with playlists, search, favorites",
    "phases": ["scaffold", "player UI", "playlist state", "search", "favorites", "deliver"],
    "name": "music-player",
    "desc": "a music player with playlists and search",
    "files": [
        ("src/App.tsx",
         "import { useState } from 'react'\n"
         "export default function App() {\n"
         "  const [q, setQ] = useState('')\n"
         "  const tracks = [{id:1,title:'Song A'},{id:2,title:'Song B'}]\n"
         "  return <div><input placeholder=\"search\" value={q} onChange={e=>setQ(e.target.value)} />"
         "<ul>{tracks.filter(t=>t.title.includes(q)).map(t=><li key={t.id}>{t.title}</li>)}</ul></div>\n"
         "}"),
    ],
}


def main():
    print(f"Loading: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    assert "explicitly asks for a plan" in SYSTEM_TEXT, "v80 system prompt not loaded"

    examples = []

    # 1. Happy-path: 10 v69 apps
    for name, desc, files in APPS_V69:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 2. Pipeline-format L3: 6
    for ex in V73_L3:
        msgs = build_l3_direct_fix(ex["name"], ex["desc"], ex["files"], ex["error"], ex["fix_call"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 3. Bare L3: 3
    for sc in BARE_L3:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 4. Plan-first: 1 new
    p = PLAN_EXAMPLE
    msgs = build_plan_first(p["user_prompt"], p["goal"], p["phases"],
                             p["name"], p["desc"], p["files"])
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    print(f"\nTotal: {len(examples)} examples")
    print("  10 happy / 6 pipeline L3 / 3 bare L3 / 1 plan-first (new)")

    starts_bos = sum(1 for ex in examples if ex["text"].startswith("<bos>"))
    print(f"Starts with <bos>: {starts_bos}/{len(examples)}")

    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"Wrote {len(examples)} examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
