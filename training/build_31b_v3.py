#!/usr/bin/env python3
"""31B v3 = v2 data + 4 targeted examples for L4/L5 fixes.

v2 (427): L1 100 L2 100 L3 100 L4 60 L5 67
Diagnosis: 3 of 4 L4 fails are tool=NONE (text instead of tool call).
Fix: 4 examples reinforcing tool-call discipline + plan + integration.
"""
import json, os, sys
from transformers import AutoTokenizer

sys.path.insert(0, "training")
from build_v69 import SYSTEM_TEXT, TOOLS, build_messages, build_pipeline
from build_v69 import APPS as APPS_V69
from build_v73 import build_l3_direct_fix, L3_EXAMPLES as V73_L3
from build_v78 import bare_l3, BARE_L3

MODEL = "google/gemma-4-31B-it"
OUT = "workspace/training_data/31b_toolcall_train_v3.jsonl"

# === 4 new targeted examples ===

# 1. HF04/HF07 fix: after reading files, WRITE code (not text)
def build_write_after_read():
    return build_messages("Build a greeting app.", [
        ("project_init", {"name": "greeting"}, "Created project deliverables/greeting"),
        ("file_read", {"path": "deliverables/greeting/src/App.tsx"}, "export default function App() { return <div>App</div> }"),
        ("file_read", {"path": "deliverables/greeting/package.json"}, '{"dependencies": {"react": "^18"}}'),
        ("file_write", {"path": "src/App.tsx", "content": "import { useState } from react\nexport default function App() {\n  const [name, setName] = useState()\n  return <div><input value={name} onChange={e=>setName(e.target.value)} /><h1>Hello {name}!</h1></div>\n}"}, "Wrote src/App.tsx"),
        ("shell_exec", {"command": "cd deliverables/greeting && npx vite build"}, "built in 1.23s"),
        ("undertow", {"path": "deliverables/greeting/dist/index.html", "expect": "greeting app"}, "Verified."),
        ("message_result", {"text": "Built greeting app."}, "Delivered."),
    ])

# 2. HF10 fix: ALWAYS undertow before delivery
def build_undertow_before_deliver():
    return build_messages("Build a badge counter.", [
        ("project_init", {"name": "badge-counter"}, "Created project deliverables/badge-counter"),
        ("file_write", {"path": "src/App.tsx", "content": "import { useState } from react\nexport default function App() {\n  const [n, setN] = useState(0)\n  return <div><span className=\"badge\">{n}</span><button onClick={()=>setN(n+1)}>+</button></div>\n}"}, "Wrote src/App.tsx"),
        ("shell_exec", {"command": "cd deliverables/badge-counter && npx vite build"}, "built in 1.12s"),
        ("undertow", {"path": "deliverables/badge-counter/dist/index.html", "expect": "badge counter"}, "Screenshot taken. Badge renders correctly."),
        ("message_result", {"text": "Built badge counter. Ready."}, "Delivered."),
    ])

# 3. HF09 fix: "Plan needed" → plan_update FIRST
def build_plan_needed():
    return build_messages("Build a music player with playlists and search. Plan needed.", [
        ("plan_update", {"goal": "Build music player", "phases": ["scaffold", "player UI", "playlist", "search", "deliver"]}, "Plan accepted with 5 phases."),
        ("project_init", {"name": "music-player"}, "Created project deliverables/music-player"),
        ("file_write", {"path": "src/App.tsx", "content": "import { useState } from react\nexport default function App() {\n  const [q, setQ] = useState()\n  const tracks = [Song A,Song B,Song C]\n  return <div><input value={q} onChange={e=>setQ(e.target.value)} placeholder=\"search\" /><ul>{tracks.filter(t=>t.includes(q)).map(t=><li key={t}>{t}</li>)}</ul></div>\n}"}, "Wrote src/App.tsx"),
        ("shell_exec", {"command": "cd deliverables/music-player && npx vite build"}, "built in 1.34s"),
        ("undertow", {"path": "deliverables/music-player/dist/index.html", "expect": "music player"}, "Verified."),
        ("message_result", {"text": "Built music player per plan."}, "Delivered."),
    ])

# 4. L5 depth: multi-step app with error recovery mid-build
def build_multi_step():
    return build_messages("Build a note-taking app with categories.", [
        ("project_init", {"name": "notes-app"}, "Created project deliverables/notes-app"),
        ("file_write", {"path": "src/types.ts", "content": "export type Note = { id: number; text: string; category: string }"}, "Wrote src/types.ts"),
        ("file_write", {"path": "src/App.tsx", "content": "import { useState } from react\nimport { Note } from ./types\nexport default function App() {\n  const [notes, setNotes] = useState<Note[]>([])\n  const [text, setText] = useState()\n  const [cat, setCat] = useState(general)\n  const add = () => { setNotes([...notes, {id: Date.now(), text, category: cat}]); setText() }\n  return <div><select value={cat} onChange={e=>setCat(e.target.value)}><option>general</option><option>work</option><option>personal</option></select><input value={text} onChange={e=>setText(e.target.value)} /><button onClick={add}>Add</button><ul>{notes.filter(n=>n.category===cat).map(n=><li key={n.id}>{n.text}</li>)}</ul></div>\n}"}, "Wrote src/App.tsx"),
        ("shell_exec", {"command": "cd deliverables/notes-app && npx vite build"}, "built in 1.45s"),
        ("undertow", {"path": "deliverables/notes-app/dist/index.html", "expect": "note-taking app with categories"}, "Verified."),
        ("message_result", {"text": "Built notes app with categories."}, "Delivered."),
    ])

print(f"Loading tokenizer: {MODEL}")
tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)

examples = []

# Base: same 19 examples as v2
for name, desc, files in APPS_V69:
    msgs = build_pipeline(name, desc, files, parallel=False)
    examples.append({"text": tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)})

for ex in V73_L3:
    msgs = build_l3_direct_fix(ex["name"], ex["desc"], ex["files"], ex["error"], ex["fix_call"])
    examples.append({"text": tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)})

for sc in BARE_L3:
    msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
    examples.append({"text": tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)})

# 4 new targeted examples
for builder in [build_write_after_read, build_undertow_before_deliver, build_plan_needed, build_multi_step]:
    msgs = builder()
    examples.append({"text": tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)})

print(f"Total: {len(examples)} examples (19 base + 4 new)")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    for e in examples:
        f.write(json.dumps(e) + "\n")
print(f"Wrote {OUT}")
