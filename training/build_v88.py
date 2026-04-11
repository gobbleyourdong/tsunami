#!/usr/bin/env python3
"""v88 — v87 base + 6 targeted examples for remaining 68-point gap.

v87 (432/500): 31 examples, 14/14 tools
  L1=100 L2=92 L3=83 L4=90 L5=67

Remaining failures:
  S11  (-8):  scaffold names "data-dashboard" not "data-viz"
  ER05 (-17): file_write instead of shell_exec for wrong path
  HF09 (-10): project_init instead of plan_update for complex builds
  IE01/IM03/IH02 (-33): L5 timeouts from shell_exec loops

v88 strategy: +6 targeted examples
  - 1 scaffold naming (data-viz keyword)
  - 2 bare ER05 (stronger wrong-path → corrected-path signal)
  - 1 plan_update (second complex build trigger)
  - 2 stall recovery (build fail → file_read → file_write rewrite)

Total: 37 examples. Same hyperparams.
"""
import json
import os
import sys

from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS, build_pipeline, build_messages
from build_v69 import APPS as APPS_V69
from build_v73 import build_l3_direct_fix, L3_EXAMPLES as V73_L3
from build_v78 import bare_l3, BARE_L3

# Import all v87 additions
from build_v87 import (
    EXTRA_BARE_L3, INTEGRATION_APPS,
    build_plan_example, build_integration_with_error,
    build_search_then_build, build_read_then_edit, build_glob_then_read,
    build_swell_example, build_message_info_example,
    build_swell_generic, build_swell_analyze_example,
)

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v88.jsonl"


# === NEW v88: Scaffold naming (S11) ===
def build_dataviz_example():
    """Data visualization app — scaffold should be named with 'data-viz' or 'd3'."""
    user_prompt = "Build a data visualization dashboard with d3 charts."
    turns = [
        ("project_init", {"name": "d3-data-viz"}, "Created project deliverables/d3-data-viz"),
        ("file_write", {"path": "src/App.tsx", "content": (
            "import { useEffect, useRef } from 'react'\n"
            "export default function App() {\n"
            "  const ref = useRef<SVGSVGElement>(null)\n"
            "  useEffect(() => {\n"
            "    // D3 bar chart\n"
            "    const data = [30, 50, 80, 40, 90, 60]\n"
            "    const svg = ref.current\n"
            "    if (!svg) return\n"
            "  }, [])\n"
            "  return <svg ref={ref} width={600} height={400} />\n"
            "}\n"
        )}, "Wrote App.tsx"),
        ("shell_exec", {"command": "cd deliverables/d3-data-viz && npx vite build"},
         "vite v5.0.0 building... built in 1.23s"),
        ("undertow", {"path": "deliverables/d3-data-viz/dist/index.html",
                      "expect": "data visualization with charts"}, "Verified."),
        ("message_result", {"text": "Built d3-data-viz: data visualization dashboard. Ready."},
         "Delivered."),
    ]
    return build_messages(user_prompt, turns)


# === NEW v88: Extra ER05 bare examples (wrong path) ===
EXTRA_ER05 = [
    # Variant 1: workspace/ prefix error (most common)
    dict(
        initial_cmd="cd workspace/deliverables/timer && npx vite build",
        error="bash: cd: workspace/deliverables/timer: No such file or directory",
        fix_tool="shell_exec",
        fix_args={"command": "cd deliverables/timer && npx vite build"},
    ),
    # Variant 2: double deliverables path
    dict(
        initial_cmd="cd deliverables/deliverables/app && npx vite build",
        error="bash: cd: deliverables/deliverables/app: No such file or directory",
        fix_tool="shell_exec",
        fix_args={"command": "cd deliverables/app && npx vite build"},
    ),
]


# === NEW v88: Second plan_update example ===
def build_plan_example_2():
    """Complex multi-feature build with plan trigger words."""
    user_prompt = "Build a project management tool with task boards, team members, deadlines, and progress tracking. Plan this out first."
    turns = [
        ("plan_update", {
            "goal": "Project management tool with boards, teams, deadlines, progress",
            "phases": [
                "Scaffold dashboard project",
                "Write App.tsx with task board, team sidebar, deadline view",
                "Build and fix errors",
                "QA and deliver",
            ],
        }, "Plan created."),
        ("project_init", {"name": "project-manager"}, "Created project deliverables/project-manager"),
        ("file_write", {"path": "src/App.tsx", "content": (
            "import { useState } from 'react'\n"
            "import { Button, Card, Badge, Input, Progress } from './components/ui'\n"
            "\n"
            "type Task = { title: string; assignee: string; deadline: string; done: boolean }\n"
            "\n"
            "export default function App() {\n"
            "  const [tasks, setTasks] = useState<Task[]>([\n"
            "    { title: 'Design mockups', assignee: 'Alex', deadline: '2026-04-15', done: true },\n"
            "    { title: 'Build API', assignee: 'Sam', deadline: '2026-04-20', done: false },\n"
            "    { title: 'Write tests', assignee: 'Alex', deadline: '2026-04-25', done: false },\n"
            "  ])\n"
            "  const pct = Math.round(tasks.filter(t => t.done).length / tasks.length * 100)\n"
            "  return (\n"
            "    <div className='container p-6'>\n"
            "      <h1>Project Manager</h1>\n"
            "      <Progress value={pct} />\n"
            "      <p className='text-muted'>{pct}% complete</p>\n"
            "      {tasks.map((t, i) => (\n"
            "        <Card key={i} className='p-4' style={{marginTop:'0.5rem'}}>\n"
            "          <div className='flex' style={{justifyContent:'space-between'}}>\n"
            "            <span style={{textDecoration: t.done ? 'line-through' : 'none'}}>{t.title}</span>\n"
            "            <div className='flex gap-2'>\n"
            "              <Badge>{t.assignee}</Badge>\n"
            "              <Badge>{t.deadline}</Badge>\n"
            "              <Button onClick={() => setTasks(tasks.map((x,j) => j===i ? {...x, done:!x.done} : x))}>\n"
            "                {t.done ? 'Undo' : 'Done'}\n"
            "              </Button>\n"
            "            </div>\n"
            "          </div>\n"
            "        </Card>\n"
            "      ))}\n"
            "    </div>\n"
            "  )\n"
            "}\n"
        )}, "Wrote App.tsx"),
        ("shell_exec", {"command": "cd deliverables/project-manager && npx vite build"},
         "vite v5.0.0 building... built in 1.67s"),
        ("undertow", {"path": "deliverables/project-manager/dist/index.html",
                      "expect": "project manager with tasks, teams, progress"},
         "Screenshot taken. Task board with progress bar, team badges, deadlines."),
        ("message_result", {"text": "Built project-manager: task boards, team members, deadlines, progress tracking. Ready."},
         "Delivered."),
    ]
    return build_messages(user_prompt, turns)


# === NEW v88: Stall recovery examples (L5 timeout fix) ===
def build_stall_recovery_1():
    """Build fails → file_read → file_write full rewrite → rebuild succeeds."""
    user_prompt = "Build me a quiz app with 5 questions and a score."
    turns = [
        ("project_init", {"name": "quiz-app"}, "Created project deliverables/quiz-app"),
        ("file_write", {"path": "src/App.tsx", "content": (
            "import { useState } from 'react'\nimport { Button, Card } from './components/ui'\n\n"
            "const QUESTIONS = [\n  { q: 'Capital of France?', a: ['Paris', 'London', 'Berlin'], correct: 0 },\n"
            "  { q: 'Largest planet?', a: ['Mars', 'Jupiter', 'Saturn'], correct: 1 },\n"
            "  { q: '2+2?', a: ['3', '4', '5'], correct: 1 },\n"
            "  { q: 'Fastest animal?', a: ['Cheetah', 'Horse', 'Eagle'], correct: 0 },\n"
            "  { q: 'H2O is?', a: ['Salt', 'Water', 'Oil'], correct: 1 },\n]\n\n"
            "export default function App() {\n  const [idx, setIdx] = useState(0)\n"
            "  const [score, setScore] = useState(0)\n  const [done, setDone] = useState(false)\n"
            "  const pick = (i: number) => {\n    if (i === QUESTIONS[idx].correct) setScore(s => s + 1)\n"
            "    if (idx < QUESTIONS.length - 1) setIdx(idx + 1)\n    else setDone(true)\n  }\n"
            "  if (done) return <Card className='p-6 text-center'><h1>Score: {score}/{QUESTIONS.length}</h1>"
            "<Button onClick={() => { setIdx(0); setScore(0); setDone(false) }}>Retry</Button></Card>\n"
            "  const q = QUESTIONS[idx]\n  return (\n    <div className='container p-6'>\n"
            "      <Card className='p-4'><h2>Q{idx+1}: {q.q}</h2>\n"
            "        {q.a.map((a, i) => <Button key={i} onClick={() => pick(i)}>{a}</Button>)}\n"
            "      </Card>\n    </div>\n  )\n}\n"
        )}, "Wrote App.tsx"),
        ("shell_exec", {"command": "cd deliverables/quiz-app && npx vite build"},
         "Error: src/App.tsx(18,5): JSX expressions must have one parent element."),
        # KEY: model reads the error, then REWRITES instead of retrying build
        ("file_read", {"path": "deliverables/quiz-app/src/App.tsx"},
         "import { useState } from 'react'\nimport { Button, Card } from './components/ui'\n..."),
        ("file_write", {"path": "src/App.tsx", "content": (
            "import { useState } from 'react'\nimport { Button, Card } from './components/ui'\n\n"
            "const QUESTIONS = [\n  { q: 'Capital of France?', a: ['Paris', 'London', 'Berlin'], correct: 0 },\n"
            "  { q: 'Largest planet?', a: ['Mars', 'Jupiter', 'Saturn'], correct: 1 },\n"
            "  { q: '2+2?', a: ['3', '4', '5'], correct: 1 },\n"
            "  { q: 'Fastest animal?', a: ['Cheetah', 'Horse', 'Eagle'], correct: 0 },\n"
            "  { q: 'H2O is?', a: ['Salt', 'Water', 'Oil'], correct: 1 },\n]\n\n"
            "export default function App() {\n  const [idx, setIdx] = useState(0)\n"
            "  const [score, setScore] = useState(0)\n  const [done, setDone] = useState(false)\n"
            "  const pick = (i: number) => {\n    if (i === QUESTIONS[idx].correct) setScore(s => s + 1)\n"
            "    if (idx < QUESTIONS.length - 1) setIdx(idx + 1)\n    else setDone(true)\n  }\n"
            "  if (done) return (\n    <Card className='p-6 text-center'>\n"
            "      <h1>Score: {score}/{QUESTIONS.length}</h1>\n"
            "      <Button onClick={() => { setIdx(0); setScore(0); setDone(false) }}>Retry</Button>\n"
            "    </Card>\n  )\n  const q = QUESTIONS[idx]\n  return (\n"
            "    <div className='container p-6'>\n      <Card className='p-4'>\n"
            "        <h2>Q{idx+1}: {q.q}</h2>\n"
            "        <div className='flex gap-2'>\n"
            "          {q.a.map((a, i) => <Button key={i} onClick={() => pick(i)}>{a}</Button>)}\n"
            "        </div>\n      </Card>\n    </div>\n  )\n}\n"
        )}, "Wrote App.tsx"),
        ("shell_exec", {"command": "cd deliverables/quiz-app && npx vite build"},
         "vite v5.0.0 building... built in 1.34s"),
        ("undertow", {"path": "deliverables/quiz-app/dist/index.html",
                      "expect": "quiz with questions and score"}, "Verified."),
        ("message_result", {"text": "Built quiz-app: 5 questions with score tracking. Ready."},
         "Delivered."),
    ]
    return build_messages(user_prompt, turns)


def build_stall_recovery_2():
    """Build fails with type error → file_read → full rewrite → success."""
    user_prompt = "Build me a markdown editor with live preview."
    turns = [
        ("project_init", {"name": "md-editor"}, "Created project deliverables/md-editor"),
        ("file_write", {"path": "src/App.tsx", "content": (
            "import { useState } from 'react'\nimport { Card } from './components/ui'\n\n"
            "export default function App() {\n  const [text, setText] = useState('# Hello')\n"
            "  const html = text.replace(/^# (.*)/gm, '<h1>$1</h1>')\n"
            "    .replace(/^## (.*)/gm, '<h2>$1</h2>')\n"
            "    .replace(/\\n/g, '<br/>')\n"
            "  return (\n    <div className='grid grid-2 gap-4 p-6' style={{height:'100vh'}}>\n"
            "      <textarea value={text} onChange={e => setText(e.target.value)}\n"
            "        style={{width:'100%',height:'100%',fontFamily:'monospace',padding:'1rem'}} />\n"
            "      <Card className='p-4' />\n    </div>\n  )\n}\n"
        )}, "Wrote App.tsx"),
        ("shell_exec", {"command": "cd deliverables/md-editor && npx vite build"},
         "Error: src/App.tsx(11,7): Type 'string' is not assignable to type 'Element'."),
        ("file_read", {"path": "deliverables/md-editor/src/App.tsx"},
         "import { useState } from 'react'\nimport { Card } from './components/ui'\n..."),
        ("file_write", {"path": "src/App.tsx", "content": (
            "import { useState } from 'react'\nimport { Card } from './components/ui'\n\n"
            "function renderMd(md: string): string {\n"
            "  return md\n    .replace(/^# (.*)/gm, '<h1>$1</h1>')\n"
            "    .replace(/^## (.*)/gm, '<h2>$1</h2>')\n"
            "    .replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>')\n"
            "    .replace(/\\*(.*?)\\*/g, '<i>$1</i>')\n"
            "    .replace(/\\n/g, '<br/>')\n}\n\n"
            "export default function App() {\n  const [text, setText] = useState('# Hello\\n\\nType **markdown** here.')\n"
            "  return (\n    <div className='grid grid-2 gap-4 p-6' style={{height:'100vh'}}>\n"
            "      <textarea value={text} onChange={(e) => setText(e.target.value)}\n"
            "        className='bg-1 rounded p-4' style={{width:'100%',height:'100%',fontFamily:'monospace',resize:'none'}} />\n"
            "      <Card className='p-4'><div>{renderMd(text)}</div></Card>\n"
            "    </div>\n  )\n}\n"
        )}, "Wrote App.tsx"),
        ("shell_exec", {"command": "cd deliverables/md-editor && npx vite build"},
         "vite v5.0.0 building... built in 1.45s"),
        ("undertow", {"path": "deliverables/md-editor/dist/index.html",
                      "expect": "markdown editor with live preview"}, "Verified."),
        ("message_result", {"text": "Built md-editor: markdown editor with live preview. Ready."},
         "Delivered."),
    ]
    return build_messages(user_prompt, turns)


def main():
    print(f"Loading: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)

    assert "Components" in SYSTEM_TEXT, "Missing component guide"
    print("SYSTEM_TEXT verified.")

    examples = []

    # === v87 baseline: 31 examples ===

    # 1-10: Happy-path (v69)
    for name, desc, files in APPS_V69:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 11-16: Pipeline L3 (v73)
    for ex in V73_L3:
        msgs = build_l3_direct_fix(ex["name"], ex["desc"], ex["files"], ex["error"], ex["fix_call"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 17-19: Bare L3 (v78)
    for sc in BARE_L3:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 20: Extra bare L3 ER01
    for sc in EXTRA_BARE_L3:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 21: Plan gate
    msgs = build_plan_example()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # 22-23: Integration happy
    for name, desc, files in INTEGRATION_APPS[:2]:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 24: Integration + error recovery
    name, desc, files = INTEGRATION_APPS[2]
    msgs = build_integration_with_error(name, desc, files)
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # 25-31: Tool coverage
    for builder in [build_search_then_build, build_read_then_edit, build_glob_then_read,
                    build_swell_example, build_message_info_example,
                    build_swell_generic, build_swell_analyze_example]:
        msgs = builder()
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # === NEW v88: +6 targeted ===

    # 32: Data-viz scaffold naming (S11)
    msgs = build_dataviz_example()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # 33-34: Extra ER05 bare examples (wrong path)
    for sc in EXTRA_ER05:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 35: Second plan_update example (HF09)
    msgs = build_plan_example_2()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # 36-37: Stall recovery (L5 timeouts)
    msgs = build_stall_recovery_1()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    msgs = build_stall_recovery_2()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # === Summary ===
    print(f"\nTotal: {len(examples)} examples")
    print(f"  31 from v87 (baseline)")
    print(f"  1 data-viz scaffold (S11)")
    print(f"  2 bare ER05 wrong-path (ER05)")
    print(f"  1 plan_update #2 (HF09)")
    print(f"  2 stall recovery (L5 timeouts)")

    starts_bos = sum(1 for ex in examples if ex["text"].startswith("<bos>"))
    print(f"Starts with <bos>: {starts_bos}/{len(examples)}")

    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"\nWrote {len(examples)} examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
