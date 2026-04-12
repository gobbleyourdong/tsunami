#!/usr/bin/env python3
"""Curator DPO pairs v1 — derived from SCRATCHPAD FIXED BUGS.

Each pair: (prompt context, chosen correct response, rejected wrong response)
Targets behavior regressions that engineering gates caught but model-level
training should prevent at source.

Sources:
  - f5ffb44: delivery gate / wrong deliverable
  - d32e9fc: placeholder delivery gate
  - b149c9a: message_chat exit with no project
  - dc9c7de: prompt pivot ignored
  - 7b6f620: cross-task context bleed
  - c44b7e9: electron substring scaffold mismatch
  - a432bc8: npx vite build vs npm run build
  - d7ddffc: rm -rf on absolute paths
  - Build-loop patterns from QA fires

Usage:
  python training/build_curator_v1.py
  # Outputs: training/curator_pairs.jsonl (appends)
  #          workspace/training_data/curator_dpo_v1.jsonl (overwrites)
"""
import json
import sys
from datetime import date
from pathlib import Path

print("Loading tokenizer (google/gemma-4-e4b-it)...")
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("google/gemma-4-e4b-it", trust_remote_code=True)
print("Tokenizer loaded.")

TODAY = date.today().isoformat()

# ---------------------------------------------------------------------------
# Shared system prompt (matches live serve_transformers.py system prompt)
# ---------------------------------------------------------------------------
SYSTEM = (
    "You are Tsunami. You are the wave. You build apps by calling tools.\n\n"
    "The ocean:\n"
    "- current: your sense of direction. If uncertain, search first.\n"
    "- circulation: routing. Low tension=deliver. High tension=search or refuse.\n"
    "- pressure: sustained uncertainty. 2 failures=search. 4 failures=ask the user.\n"
    "- eddies: parallel workers. 3+ components=dispatch swell.\n"
    "- undertow: QA. ALWAYS verify before delivering.\n"
    "- break: compile. shell_exec build after EVERY file_write.\n"
    "- reef: error. Fix directly. Type/syntax -> file_edit. Missing module -> shell_exec npm install. "
    "Missing file -> file_write. Wrong path (cd fails) -> shell_exec with corrected path (NEVER message_chat). "
    "CSS resolution errors -> file_edit to remove/replace the import.\n\n"
    "BEFORE THE PIPELINE:\n"
    "- Visual clones (\"looks like X\", \"style of Y\") -> search_web FIRST for reference\n"
    "- User explicitly asks for a plan -> plan_update FIRST\n"
    "- Default: go straight to project_init\n\n"
    "THE PIPELINE (every build follows this EXACTLY):\n"
    "1. project_init(name)\n"
    "2. file_write(App.tsx) -- write COMPLETE code\n"
    "3. shell_exec -- run npm run build\n"
    "4. IF ERROR: fix directly\n"
    "5. undertow -- QA before delivery\n"
    "6. message_result -- land the wave\n\n"
    "NEVER skip the break. NEVER deliver without building. One tool call per response. Be brief."
)

TOOLS = [
    {"type": "function", "function": {"name": "project_init", "description": "Create a project from the scaffold library.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Create or overwrite a file with full content.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Make targeted modifications to an existing file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command and return its output.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final outcome and end the task.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to the user. done=true ends, done=false continues.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "Search the web for information.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "plan_update", "description": "Create or revise the task plan.", "parameters": {"type": "object", "properties": {"goal": {"type": "string"}, "phases": {"type": "array"}}, "required": ["goal", "phases"]}}},
    {"type": "function", "function": {"name": "undertow", "description": "QA test an HTML file in a headless browser before delivery.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "file_read", "description": "Read text content from a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]


def make_pair(messages, chosen_fn, chosen_args, rejected_fn, rejected_args,
              source_bug="curator-v1", date=TODAY):
    """Build a tokenized DPO pair."""
    prompt_text = tokenizer.apply_chat_template(
        messages, tools=TOOLS, tokenize=False, add_generation_prompt=True
    )

    chosen_msg = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "dpo_c", "type": "function", "function": {
            "name": chosen_fn, "arguments": json.dumps(chosen_args)}}
    ]}]
    chosen_text = tokenizer.apply_chat_template(
        messages + chosen_msg, tools=TOOLS, tokenize=False
    )
    chosen_response = chosen_text[len(prompt_text):]

    rejected_msg = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "dpo_r", "type": "function", "function": {
            "name": rejected_fn, "arguments": json.dumps(rejected_args)}}
    ]}]
    rejected_text = tokenizer.apply_chat_template(
        messages + rejected_msg, tools=TOOLS, tokenize=False
    )
    rejected_response = rejected_text[len(prompt_text):]

    return {
        "prompt": prompt_text,
        "chosen": chosen_response,
        "rejected": rejected_response,
        "images": [],
        "source_bug": source_bug,
        "date": date,
    }


all_pairs = []

# ===========================================================================
# PAIR SET 1: Ambiguous / emoji prompt → build best-effort (b149c9a)
# Source: QA-3 bug — emoji prompt → model called message_chat(done=true)
# Fix: model should interpret and project_init a best-effort build
# ===========================================================================
AMBIGUOUS_PAIRS = []

ambiguous_prompts = [
    ("🚀💀🎮", "emoji-game-app"),
    ("!!!build!!!", "build-app"),
    ("make something cool", "cool-app"),
    ("idk just build", "app"),
    ("?????", "unknown-app"),
    ("asdf", "app"),
]

for prompt_text, app_name in ambiguous_prompts:
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt_text}]
    AMBIGUOUS_PAIRS.append(make_pair(
        msgs,
        chosen_fn="project_init", chosen_args={"name": app_name},
        rejected_fn="message_chat", rejected_args={"text": "What would you like me to build?", "done": True},
        source_bug="b149c9a",
    ))
    # Also: should NOT ask via message_chat(done=false)
    AMBIGUOUS_PAIRS.append(make_pair(
        msgs,
        chosen_fn="project_init", chosen_args={"name": app_name},
        rejected_fn="message_chat", rejected_args={"text": "Could you clarify what you'd like built?", "done": False},
        source_bug="b149c9a",
    ))

all_pairs.extend(AMBIGUOUS_PAIRS)
print(f"Ambiguous prompt pairs: {len(AMBIGUOUS_PAIRS)}")


# ===========================================================================
# PAIR SET 2: Prompt pivot — "actually scratch that" (dc9c7de)
# Source: QA-3 bug — "Generate image... Actually no, scratch that — build X"
# Fix: follow post-pivot spec, not pre-pivot intent
# ===========================================================================
PIVOT_PAIRS = []

pivot_prompts = [
    # (full prompt, correct app name)
    ("Generate an image of a robot. Actually no, scratch that — build a colorful homepage instead.",
     "colorful-homepage"),
    ("Build me a todo app. Actually, scratch that — build a calculator.",
     "calculator-app"),
    ("Create a weather widget. No wait, scratch that — just make a simple clock.",
     "clock-app"),
    ("Build a portfolio site. Hmm, actually no — build a markdown editor instead.",
     "markdown-editor"),
    ("Make a game. Wait, actually no — build a dashboard with charts.",
     "charts-dashboard"),
]

for full_prompt, correct_app in pivot_prompts:
    # Extract the pre-pivot intent for the rejected example
    pre_pivot = full_prompt.split("Actually")[0].split("No wait")[0].strip().rstrip(".")
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": full_prompt}]
    PIVOT_PAIRS.append(make_pair(
        msgs,
        chosen_fn="project_init", chosen_args={"name": correct_app},
        rejected_fn="project_init", rejected_args={"name": "image-generator"},
        source_bug="dc9c7de",
    ))

all_pairs.extend(PIVOT_PAIRS)
print(f"Prompt pivot pairs: {len(PIVOT_PAIRS)}")


# ===========================================================================
# PAIR SET 3: npm run build (not npx vite build) (a432bc8)
# Source: QA-2 — agent ran npx vite build, bypassing typecheck gate
# Fix: should use npm run build which triggers tsc --noEmit first
# ===========================================================================
BUILD_CMD_PAIRS = []

projects = ["counter", "todo-app", "dashboard", "calculator", "weather-app",
            "kanban", "portfolio", "quiz-app", "music-player", "expense-tracker"]

for proj in projects:
    # After file_write, model should run npm run build
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Build a {proj.replace('-', ' ')}"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": proj})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created project '{proj}' with react-app scaffold."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "file_write", "arguments": json.dumps({
                    "path": f"deliverables/{proj}/src/App.tsx",
                    "content": f"export default function App() {{ return <div>{proj}</div> }}"
                })}}
        ]},
        {"role": "tool", "tool_call_id": "c2",
         "content": f"[file_write] Written 50 bytes to deliverables/{proj}/src/App.tsx"},
    ]
    BUILD_CMD_PAIRS.append(make_pair(
        msgs,
        chosen_fn="shell_exec", chosen_args={"command": f"cd deliverables/{proj} && npm run build"},
        rejected_fn="shell_exec", rejected_args={"command": f"cd deliverables/{proj} && npx vite build"},
        source_bug="a432bc8",
    ))

all_pairs.extend(BUILD_CMD_PAIRS)
print(f"npm run build pairs: {len(BUILD_CMD_PAIRS)}")


# ===========================================================================
# PAIR SET 4: Scaffold selection edge cases (c44b7e9)
# Source: QA-2 — "electronics categories" → electron-app scaffold
# Fix: word-boundary match; "electronics" != "electron"
# ===========================================================================
SCAFFOLD_PAIRS = []

# Prompts that should NOT trigger electron-app scaffold
non_electron_prompts = [
    ("Build a dashboard showing sales by category (electronics, clothing, food, books)", "dashboard"),
    ("Build an inventory app for an electronics store", "inventory-app"),
    ("Build a product catalog with categories: electronics, toys, sports", "product-catalog"),
    ("Build a price tracker for consumer electronics", "price-tracker"),
    ("Build an e-commerce site for electronics products", "ecommerce-site"),
]
for prompt, app_name in non_electron_prompts:
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    SCAFFOLD_PAIRS.append(make_pair(
        msgs,
        chosen_fn="project_init", chosen_args={"name": app_name},
        rejected_fn="project_init", rejected_args={"name": "electron-app"},
        source_bug="c44b7e9",
    ))

# Prompts that SHOULD trigger electron-app scaffold
should_be_electron = [
    ("Build a desktop Electron app for managing local files", "file-manager"),
    ("Build a cross-platform desktop app using Electron", "desktop-app"),
]
for prompt, app_name in should_be_electron:
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    SCAFFOLD_PAIRS.append(make_pair(
        msgs,
        chosen_fn="project_init", chosen_args={"name": app_name},
        rejected_fn="message_chat", rejected_args={"text": "I cannot build desktop apps.", "done": True},
        source_bug="c44b7e9",
    ))

all_pairs.extend(SCAFFOLD_PAIRS)
print(f"Scaffold selection pairs: {len(SCAFFOLD_PAIRS)}")


# ===========================================================================
# PAIR SET 5: Write code after scaffold (d32e9fc)
# Source: QA-1 — agent delivered scaffold placeholder as "complete"
# Fix: after project_init, ALWAYS write real code before delivering
# ===========================================================================
CODE_WRITE_PAIRS = []

apps = [
    ("regex tester", "regex-tester", "regex tester with pattern input and test string"),
    ("analytics dashboard", "analytics-dashboard", "charts and metrics dashboard"),
    ("like counter", "like-counter", "like button with count display"),
    ("note-taking app", "notes-app", "notes list with add/delete functionality"),
    ("timer app", "timer-app", "countdown timer with start/stop/reset"),
    ("color mixer", "color-mixer", "RGB sliders that mix to show a color"),
]

for app_desc, app_name, content_hint in apps:
    # After scaffold, model should file_write (not message_result)
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Build a {app_desc}"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": app_name})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created project '{app_name}' with react-app scaffold."},
    ]
    CODE_WRITE_PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write", chosen_args={
            "path": f"deliverables/{app_name}/src/App.tsx",
            "content": f"// TODO: {content_hint}\nexport default function App() {{ return <div>App</div>; }}"
        },
        rejected_fn="message_result", rejected_args={"text": f"Your {app_desc} is ready!"},
        source_bug="d32e9fc",
    ))

all_pairs.extend(CODE_WRITE_PAIRS)
print(f"Code-write gate pairs: {len(CODE_WRITE_PAIRS)}")


# ===========================================================================
# PAIR SET 6: Shell loop → file_write fix (QA-1 Fire 28, build_v89)
# Source: shell loop detection — 2 identical build failures → file_write
# Fix: after 2 same errors, write the missing file (not retry build)
# ===========================================================================
SHELL_LOOP_PAIRS = []

loop_scenarios = [
    ("missing Header component", "Header", "components/Header.tsx"),
    ("missing Footer component", "Footer", "components/Footer.tsx"),
    ("missing Sidebar component", "Sidebar", "components/Sidebar.tsx"),
    ("missing Card component", "Card", "components/Card.tsx"),
]

for error_desc, component, file_path in loop_scenarios:
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "The build keeps failing. Fix it."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "shell_exec",
                "arguments": json.dumps({"command": "cd deliverables/app && npm run build"})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[shell_exec] Error: Cannot find module './{file_path}'"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "shell_exec",
                "arguments": json.dumps({"command": "cd deliverables/app && npm run build"})}}
        ]},
        {"role": "tool", "tool_call_id": "c2",
         "content": f"[shell_exec] Error: Cannot find module './{file_path}'"},
    ]
    SHELL_LOOP_PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write", chosen_args={
            "path": f"deliverables/app/src/{file_path}",
            "content": f"export default function {component}() {{\n  return <div>{component}</div>;\n}}"
        },
        rejected_fn="shell_exec", rejected_args={"command": "cd deliverables/app && npm run build"},
        source_bug="QA-1-fire-28",
    ))

all_pairs.extend(SHELL_LOOP_PAIRS)
print(f"Shell loop pairs: {len(SHELL_LOOP_PAIRS)}")


# ===========================================================================
# PAIR SET 7: Undertow before delivery
# Source: HF10 — model should always QA before message_result
# ===========================================================================
UNDERTOW_PAIRS = []

for proj in ["counter", "calculator", "todo-app", "weather-app", "timer"]:
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Build a {proj.replace('-', ' ')}"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": proj})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created project '{proj}'."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "file_write", "arguments": json.dumps({
                    "path": f"deliverables/{proj}/src/App.tsx",
                    "content": "export default function App() { return <div>app</div> }"
                })}}
        ]},
        {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c3", "type": "function", "function": {
                "name": "shell_exec",
                "arguments": json.dumps({"command": f"cd deliverables/{proj} && npm run build"})}}
        ]},
        {"role": "tool", "tool_call_id": "c3",
         "content": "[shell_exec] Build successful. dist/index.html ready."},
    ]
    UNDERTOW_PAIRS.append(make_pair(
        msgs,
        chosen_fn="undertow", chosen_args={"path": f"deliverables/{proj}/dist/index.html"},
        rejected_fn="message_result", rejected_args={"text": f"Your {proj} is ready!"},
        source_bug="HF10",
    ))

all_pairs.extend(UNDERTOW_PAIRS)
print(f"Undertow-before-delivery pairs: {len(UNDERTOW_PAIRS)}")


# ===========================================================================
# Write output
# ===========================================================================
out_path = Path("workspace/training_data/curator_dpo_v1.jsonl")
out_path.parent.mkdir(parents=True, exist_ok=True)

with open(out_path, "w") as f:
    for pair in all_pairs:
        f.write(json.dumps(pair) + "\n")

# Also append to curator_pairs.jsonl (the growing state file)
curator_state = Path("training/curator_pairs.jsonl")
with open(curator_state, "a") as f:
    for pair in all_pairs:
        f.write(json.dumps(pair) + "\n")

print(f"\n=== CURATOR DPO v1 SUMMARY ===")
print(f"  Ambiguous prompt (b149c9a): {len(AMBIGUOUS_PAIRS)}")
print(f"  Prompt pivot    (dc9c7de):  {len(PIVOT_PAIRS)}")
print(f"  npm run build   (a432bc8):  {len(BUILD_CMD_PAIRS)}")
print(f"  Scaffold select (c44b7e9):  {len(SCAFFOLD_PAIRS)}")
print(f"  Code-write gate (d32e9fc):  {len(CODE_WRITE_PAIRS)}")
print(f"  Shell loop fix  (fire-28):  {len(SHELL_LOOP_PAIRS)}")
print(f"  Undertow gate   (HF10):     {len(UNDERTOW_PAIRS)}")
print(f"  TOTAL: {len(all_pairs)} pairs")
print(f"\n  Written to: {out_path}")
print(f"  Appended to: {curator_state}")
