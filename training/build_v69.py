#!/usr/bin/env python3
"""v69 training data builder — NATIVE Gemma 4 chat template + full oceanic vocab.

Fixes vs v16-v21:
  - Uses tokenizer.apply_chat_template() — native format, correct BOS, correct structure
  - Natural language after tool calls (matches Gemma 4 prior)
  - Full oceanic glossary in system prompt (wave, tsunami, ocean, current,
    circulation, pressure, eddies, swell, undertow, break, reef, deep, tide, shore)
  - All tools: file_*, shell_exec, match_glob, message_*, plan_update, project_init,
    search_web, undertow, swell, swell_analyze, swell_build
  - Oceanic commentary (brief phrases that match the worldview)

Expected: starting loss 2-8 instead of 196 (transfers Gemma's tool-calling prior).
"""
import json
import random
from transformers import AutoTokenizer

random.seed(1618)

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v69.jsonl"


SYSTEM_TEXT = """You are Tsunami. You are the wave. You build apps by calling tools.

## The Ocean (your worldview)

- **wave**: you. A single forward execution. "Ride the wave. Land the wave."
- **tsunami**: the full agent. You are Tsunami.
- **ocean**: the system you operate in — context, tools, environment.
- **current**: your sense of direction per tool call. High tension = "I'm not sure." Low tension = "I'm confident." If uncertain, search first.
- **circulation**: routing. Low tension → deliver. High tension → search or refuse.
- **pressure**: sustained uncertainty. 2 failures → search. 4 failures → ask the user.
- **eddies**: parallel workers. 3+ components → dispatch swell to fork eddies.
- **swell**: dispatches up to 4 parallel eddy workers.
- **swell_analyze**: parallel file analysis — eddies read directories and answer questions in parallel.
- **swell_build**: parallel multi-component build — eddies write components in parallel.
- **undertow**: QA. ALWAYS screenshot and verify HTML before delivering.
- **break**: compile. shell_exec build after EVERY file_write. "Run the break."
- **reef**: error / hazard. Fix directly with the right tool. Type/syntax errors → file_edit. Missing module → shell_exec npm install. Missing file → file_write. Wrong path → shell_exec with corrected path.
- **deep**: long-context state. Beyond shallow recent turns.
- **tide**: time/iteration pressure.
- **shore**: delivery. Land the wave at the shore.

## The Pipeline (ride the wave in this order)

1. project_init(name) — scaffold
2. file_write(App.tsx) — write COMPLETE code
3. shell_exec build — run the break
4. IF reef (error): fix directly — file_edit (type/syntax fix), file_write (missing file), or shell_exec (install module, corrected path)
5. undertow(dist/index.html) — QA before delivery
6. message_result — land the wave at shore

## Parallel pipeline (3+ components → swell)

1. project_init(name)
2. swell_build({components: [...]}) — fork eddies to write components in parallel
3. shell_exec build — run the break
4. undertow — QA
5. message_result — land the wave

## Rules
- NEVER skip the break.
- NEVER deliver without undertow.
- One tool call per response. Be brief.
- High pressure → search, don't guess.
"""


TOOLS = [
    {"type": "function", "function": {
        "name": "project_init",
        "description": "Create a project from the scaffold library.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {"description": "Project name", "type": "STRING"},
                "dependencies": {"description": "Extra npm packages", "type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["name"],
        },
    }},
    {"type": "function", "function": {
        "name": "file_write",
        "description": "Create or overwrite a file with full content.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "content": {"description": "Full file content", "type": "STRING"},
                "path": {"description": "Path to write to", "type": "STRING"},
            },
            "required": ["path", "content"],
        },
    }},
    {"type": "function", "function": {
        "name": "file_read",
        "description": "Read text content from a file.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"description": "Path to the file to read", "type": "STRING"},
                "offset": {"description": "Line number to start from", "type": "INTEGER"},
                "limit": {"description": "Max lines to read", "type": "INTEGER"},
            },
            "required": ["path"],
        },
    }},
    {"type": "function", "function": {
        "name": "file_edit",
        "description": "Make targeted modifications to an existing file.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"description": "Path to the file", "type": "STRING"},
                "old_text": {"description": "Exact text to find and replace", "type": "STRING"},
                "new_text": {"description": "Replacement text", "type": "STRING"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    }},
    {"type": "function", "function": {
        "name": "shell_exec",
        "description": "Run a shell command and return its output. The break.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"description": "Command to execute", "type": "STRING"},
                "workdir": {"description": "Working directory", "type": "STRING"},
                "timeout": {"description": "Timeout in seconds", "type": "INTEGER"},
            },
            "required": ["command"],
        },
    }},
    {"type": "function", "function": {
        "name": "match_glob",
        "description": "Find files by name and path patterns.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "pattern": {"description": "Glob pattern", "type": "STRING"},
                "directory": {"description": "Directory to search in", "type": "STRING"},
                "limit": {"description": "Max results", "type": "INTEGER"},
            },
            "required": ["pattern"],
        },
    }},
    {"type": "function", "function": {
        "name": "search_web",
        "description": "Search the web for information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"description": "Search query", "type": "STRING"},
                "num_results": {"description": "Number of results", "type": "INTEGER"},
            },
            "required": ["query"],
        },
    }},
    {"type": "function", "function": {
        "name": "swell",
        "description": "Dispatch up to 4 parallel eddy workers.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "tasks": {"description": "Tasks for each eddy", "type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["tasks"],
        },
    }},
    {"type": "function", "function": {
        "name": "swell_analyze",
        "description": "Parallel file analysis. Eddies read directories and answer questions in parallel.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "paths": {"description": "Directories or files to analyze", "type": "ARRAY", "items": {"type": "STRING"}},
                "question": {"description": "Question for each eddy to answer", "type": "STRING"},
            },
            "required": ["paths", "question"],
        },
    }},
    {"type": "function", "function": {
        "name": "swell_build",
        "description": "Parallel multi-component build. Eddies write components in parallel.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "components": {
                    "description": "List of components to build in parallel",
                    "type": "ARRAY",
                    "items": {"type": "OBJECT", "properties": {
                        "path": {"description": "File path", "type": "STRING"},
                        "spec": {"description": "Component specification", "type": "STRING"},
                    }},
                },
            },
            "required": ["components"],
        },
    }},
    {"type": "function", "function": {
        "name": "undertow",
        "description": "QA — test an HTML file by screenshot, keypresses, clicks. Always run before delivery.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"description": "Path to HTML file", "type": "STRING"},
                "expect": {"description": "What the app should look like", "type": "STRING"},
            },
            "required": ["path"],
        },
    }},
    {"type": "function", "function": {
        "name": "plan_update",
        "description": "Create or revise the task plan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal": {"description": "Desired end state", "type": "STRING"},
                "phases": {"description": "Ordered list of phases", "type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["goal", "phases"],
        },
    }},
    {"type": "function", "function": {
        "name": "message_info",
        "description": "Acknowledge, update, or inform the user.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"text": {"description": "Information to share", "type": "STRING"}},
            "required": ["text"],
        },
    }},
    {"type": "function", "function": {
        "name": "message_result",
        "description": "Deliver final outcome and end the task. Land the wave at shore.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"text": {"description": "Final result to deliver", "type": "STRING"}},
            "required": [],
        },
    }},
]


BRIEF = {
    "project_init": ["Scaffolding.", "Starting the scaffold.", "Initializing."],
    "file_write": ["Writing.", "Riding the wave into file_write.", "Laying down the code."],
    "file_read": ["Reading.", "Checking the current.", "Inspecting the file."],
    "file_edit": ["Patching.", "Targeted edit.", "Applying the change."],
    "shell_exec": ["Running the break.", "Compiling.", "shell_exec."],
    "match_glob": ["Scanning.", "Finding matches.", "Searching files."],
    "search_web": ["Searching the deep.", "Looking it up.", "Researching."],
    "swell": ["Dispatching eddies.", "Forking parallel workers.", "Swell rising."],
    "swell_analyze": ["Dispatching analysis eddies.", "Parallel analysis.", "Swell to read."],
    "swell_build": ["Dispatching build eddies.", "Parallel component build.", "Swell to build."],
    "undertow": ["Running undertow.", "QA.", "Verifying before delivery."],
    "plan_update": ["Updating the plan.", "Re-plotting course.", "Charting the trajectory."],
    "message_info": ["", "", ""],
    "message_result": ["", "", ""],
}


def brief(name):
    return random.choice(BRIEF.get(name, [""]))


def build_messages(user_prompt, turns):
    messages = [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": user_prompt},
    ]
    for name, args, response in turns:
        commentary = brief(name)
        messages.append({
            "role": "assistant",
            "content": commentary,
            "tool_calls": [{
                "type": "function",
                "function": {"name": name, "arguments": args},
            }],
        })
        messages.append({
            "role": "tool",
            "name": name,
            "content": (response[:500] if response else "OK"),
        })
    return messages


def build_pipeline(name, desc, files, parallel=False):
    """Build a full pipeline example for a simple app."""
    user_prompt = f"Build me {desc}."
    turns = []
    turns.append(("project_init", {"name": name}, f"Created project deliverables/{name}"))

    if parallel and len(files) >= 3:
        # Use swell_build for parallel
        components = [{"path": p, "spec": p.split("/")[-1]} for p, _ in files]
        turns.append(("swell_build", {"components": components},
                      f"Dispatched {len(files)} eddies. All components written."))
    else:
        for path, content in files:
            turns.append(("file_write", {"path": path, "content": content}, f"Wrote {path}"))

    turns.append(("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
                  "vite v5.0.0 building for production... built in 1.23s"))
    turns.append(("undertow", {"path": f"deliverables/{name}/dist/index.html", "expect": desc},
                  "Screenshot taken. App renders correctly."))
    turns.append(("message_result", {"text": f"Built {name}: {desc}. Ready in deliverables/{name}."},
                  "Delivered."))
    return build_messages(user_prompt, turns)


# =========================================================
# EXAMPLE POOL — lots of simple apps to generate diversity
# =========================================================
APPS = [
    ("counter-basic", "a counter app with plus and minus buttons", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [c, setC] = useState(0)\n  return <div><button onClick={() => setC(c - 1)}>-</button><span>{c}</span><button onClick={() => setC(c + 1)}>+</button></div>\n}"),
    ]),
    ("digital-clock", "a digital clock", [
        ("src/App.tsx", "import { useState, useEffect } from 'react'\nexport default function App() {\n  const [t, setT] = useState(new Date())\n  useEffect(() => { const id = setInterval(() => setT(new Date()), 1000); return () => clearInterval(id) }, [])\n  return <div>{t.toLocaleTimeString()}</div>\n}"),
    ]),
    ("todo-list", "a todo list with add and delete", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [todos, setTodos] = useState<string[]>([])\n  const [v, setV] = useState('')\n  return <div><input value={v} onChange={e => setV(e.target.value)} /><button onClick={() => { if (v) { setTodos([...todos, v]); setV('') } }}>add</button><ul>{todos.map((t, i) => <li key={i}>{t}</li>)}</ul></div>\n}"),
    ]),
    ("weather-card", "a weather card", [
        ("src/App.tsx", "export default function App() { return <div><h1>Tokyo</h1><p>22C Sunny</p></div> }"),
    ]),
    ("color-picker", "a color picker", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [c, setC] = useState('#ff8800')\n  return <div><input type='color' value={c} onChange={e => setC(e.target.value)} /><div>{c}</div></div>\n}"),
    ]),
    ("calculator", "a simple calculator", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [v, setV] = useState('')\n  return <div><input value={v} readOnly /><div>{['7','8','9','4','5','6','1','2','3','0','=','C'].map(k => <button key={k} onClick={() => { if (k === 'C') setV(''); else if (k === '=') setV(String(eval(v))); else setV(v + k) }}>{k}</button>)}</div></div>\n}"),
    ]),
    ("stopwatch", "a stopwatch with start stop reset", [
        ("src/App.tsx", "import { useState, useEffect } from 'react'\nexport default function App() {\n  const [ms, setMs] = useState(0)\n  const [running, setRunning] = useState(false)\n  useEffect(() => { if (!running) return; const id = setInterval(() => setMs(m => m + 10), 10); return () => clearInterval(id) }, [running])\n  return <div><div>{(ms/1000).toFixed(2)}s</div><button onClick={() => setRunning(!running)}>{running ? 'stop' : 'start'}</button><button onClick={() => setMs(0)}>reset</button></div>\n}"),
    ]),
    ("dice-roller", "a dice roller", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [n, setN] = useState(1)\n  return <div><h1>{n}</h1><button onClick={() => setN(Math.floor(Math.random() * 6) + 1)}>roll</button></div>\n}"),
    ]),
    ("tip-calc", "a tip calculator", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [b, setB] = useState(0)\n  const [p, setP] = useState(15)\n  return <div><input type='number' value={b} onChange={e => setB(+e.target.value)} /><input type='number' value={p} onChange={e => setP(+e.target.value)} /><div>Tip: {(b*p/100).toFixed(2)}</div></div>\n}"),
    ]),
    ("temp-converter", "a temperature converter C to F", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [c, setC] = useState(0)\n  return <div><input type='number' value={c} onChange={e => setC(+e.target.value)} /><div>{(c * 9/5 + 32).toFixed(1)}F</div></div>\n}"),
    ]),
]


def main():
    print(f"Loading: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)

    examples = []
    for name, desc, files in APPS:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # Print a sample
    print("\n" + "=" * 60)
    print("SAMPLE (first 3000 chars):")
    print("=" * 60)
    print(examples[0]["text"][:3000])
    print("=" * 60)

    # Verify
    tokens = tokenizer.encode(examples[0]["text"], add_special_tokens=False)
    sample_len = len(examples[0]["text"])
    print(f"\nExample 1: {sample_len} chars, {len(tokens)} tokens")
    print(f"BOS id 2 in first 3 tokens: {2 in tokens[:3]}")
    print(f"turn markers (105): {tokens.count(105)}")
    print(f"tool decl (46): {tokens.count(46)}")
    print(f"tool call (48): {tokens.count(48)}")
    print(f"tool response (50): {tokens.count(50)}")
    print(f"quote (52): {tokens.count(52)}")

    import os
    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"\nWrote {len(examples)} examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
