#!/usr/bin/env python3
"""Curator DPO pairs v3 — targeting L4 Hack-Free failures from eval_report.md.

Failures NOT in v1+v2:
  HF03: Stall detection — after 2 file_reads → file_write (not another read)
  HF06: Info loop — conversational message → message_chat(done=true)
  HF07: Auto-wire — after project_init → file_write (not message_result on empty scaffold)
  HF08: Dedup guard — after search results used → project_init (not search again)
  HF09: Complex plan — complex multi-component request → plan_update (not project_init)

Usage:
  python training/build_curator_v3.py
  Output: workspace/training_data/curator_dpo_v3.jsonl
"""
import json
from datetime import date
from pathlib import Path

print("Loading tokenizer (google/gemma-4-e4b-it)...")
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("google/gemma-4-e4b-it", trust_remote_code=True)
print("Tokenizer loaded.")

TODAY = date.today().isoformat()

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
    "- Visual clones ('looks like X', 'style of Y') -> search_web FIRST for reference\n"
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
    {"type": "function", "function": {"name": "project_init", "description": "Create a project.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Write a file with full content.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Make targeted modifications to an existing file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final outcome.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to the user.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "Search the web.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "plan_update", "description": "Create or revise the task plan.", "parameters": {"type": "object", "properties": {"goal": {"type": "string"}, "phases": {"type": "array"}}, "required": ["goal", "phases"]}}},
    {"type": "function", "function": {"name": "undertow", "description": "QA test an HTML file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "file_read", "description": "Read a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]


def make_pair(messages, chosen_fn, chosen_args, rejected_fn, rejected_args, source_bug, note=""):
    prompt_text = tokenizer.apply_chat_template(
        messages, tools=TOOLS, tokenize=False, add_generation_prompt=True
    )
    chosen_msg = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "dpo_c", "type": "function", "function": {"name": chosen_fn, "arguments": json.dumps(chosen_args)}}
    ]}]
    chosen_text = tokenizer.apply_chat_template(messages + chosen_msg, tools=TOOLS, tokenize=False)
    chosen_response = chosen_text[len(prompt_text):]
    rejected_msg = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "dpo_r", "type": "function", "function": {"name": rejected_fn, "arguments": json.dumps(rejected_args)}}
    ]}]
    rejected_text = tokenizer.apply_chat_template(messages + rejected_msg, tools=TOOLS, tokenize=False)
    rejected_response = rejected_text[len(prompt_text):]
    return {"prompt": prompt_text, "chosen": chosen_response, "rejected": rejected_response,
            "images": [], "source_bug": source_bug, "note": note, "date": TODAY}


PAIRS = []

# ──────────────────────────────────────────────────────────────────────────────
# HF03: Stall detection — after 2 file_reads, should file_write (not read again)
# ──────────────────────────────────────────────────────────────────────────────
for i, (project, file1, file2) in enumerate([
    ("counter-app", "vite.config.ts", "tsconfig.json"),
    ("weather-app", "package.json", "src/App.tsx"),
    ("todo-list",   "src/main.tsx",  "src/components/TodoItem.tsx"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Build a {project}"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": project})}}
        ]},
        {"role": "tool", "tool_call_id": "c1", "content": f"[project_init] Created '{project}'. Write App.tsx."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "file_read", "arguments": json.dumps({"path": file1})}}
        ]},
        {"role": "tool", "tool_call_id": "c2", "content": f"[file_read] Content of {file1}: (config content...)"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c3", "type": "function", "function": {
                "name": "file_read", "arguments": json.dumps({"path": file2})}}
        ]},
        {"role": "tool", "tool_call_id": "c3", "content": f"[file_read] Content of {file2}: (source content...)"},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write", chosen_args={"path": "src/App.tsx", "content": "// complete implementation"},
        rejected_fn="file_read", rejected_args={"path": "package.json"},
        source_bug="HF03-stall",
        note=f"stall-{i+1}: after 2 file_reads, should file_write not read a 3rd file",
    ))

# ──────────────────────────────────────────────────────────────────────────────
# HF06: Info loop — conversational turn should message_chat(done=true), not loop
# ──────────────────────────────────────────────────────────────────────────────
for i, (prompt, text) in enumerate([
    ("Thanks, the app looks great!", "Glad it worked!"),
    ("Nice work!", "Thanks! Let me know if you need anything else."),
    ("Can you explain how useState works?", "useState is a React hook that manages component state."),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="message_chat", chosen_args={"text": text, "done": True},
        rejected_fn="message_chat", rejected_args={"text": "I need more context to help. What are you building?", "done": False},
        source_bug="HF06-info-loop",
        note=f"info-loop-{i+1}: conversational turn → message_chat(done=true), not clarification loop",
    ))

# ──────────────────────────────────────────────────────────────────────────────
# HF07: Auto-wire — after project_init, write App.tsx (not deliver empty scaffold)
# ──────────────────────────────────────────────────────────────────────────────
for i, (project, prompt) in enumerate([
    ("expense-tracker", "Build an expense tracker with categories and a monthly chart"),
    ("markdown-editor", "Build a markdown editor with live preview"),
    ("kanban-board",    "Build a kanban board with drag and drop"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": project})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{project}'. Write App.tsx."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write", chosen_args={"path": "src/App.tsx", "content": "// complete component"},
        rejected_fn="message_result", rejected_args={"text": f"{project} scaffolded and ready."},
        source_bug="HF07-auto-wire",
        note=f"auto-wire-{i+1}: after project_init, file_write App.tsx not message_result on empty scaffold",
    ))

# ──────────────────────────────────────────────────────────────────────────────
# HF08: Dedup guard — after search results, use them → project_init, not search again
# ──────────────────────────────────────────────────────────────────────────────
for i, (query, project) in enumerate([
    ("Spotify music player UI design reference", "spotify-clone"),
    ("Airbnb booking app UI reference", "airbnb-clone"),
    ("Trello kanban board interface reference", "trello-clone"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Build a {project.replace('-', ' ')} that looks like {query.split()[0]}"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "search_web", "arguments": json.dumps({"query": query})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[search_web] Found {query.split()[0]} UI: card layout, dark sidebar, primary color #1DB954..."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="project_init", chosen_args={"name": project},
        rejected_fn="search_web", rejected_args={"query": f"{query} screenshot examples"},
        source_bug="HF08-dedup-guard",
        note=f"dedup-{i+1}: after search results received, project_init next (not search again)",
    ))

# ──────────────────────────────────────────────────────────────────────────────
# HF09: Complex plan — multi-component build → plan_update first, not project_init
# ──────────────────────────────────────────────────────────────────────────────
for i, prompt in enumerate([
    "Build a full e-commerce site with product listings, cart, checkout, and user auth",
    "Build a social media dashboard with analytics, post scheduler, and multi-account support",
    "Build a project management tool with boards, sprints, team assignments, and Gantt charts",
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="plan_update",
        chosen_args={"goal": prompt[:60], "phases": ["Phase 1", "Phase 2", "Phase 3"]},
        rejected_fn="project_init",
        rejected_args={"name": "app"},
        source_bug="HF09-complex-plan",
        note=f"complex-plan-{i+1}: complex multi-component request → plan_update first, not project_init",
    ))


# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────
OUT_PATH = Path("workspace/training_data/curator_dpo_v3.jsonl")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

with open(OUT_PATH, "w") as f:
    for p in PAIRS:
        f.write(json.dumps(p) + "\n")

counts = {
    "stall": sum(1 for p in PAIRS if "stall" in p["note"]),
    "info-loop": sum(1 for p in PAIRS if "info-loop" in p["note"]),
    "auto-wire": sum(1 for p in PAIRS if "auto-wire" in p["note"]),
    "dedup": sum(1 for p in PAIRS if "dedup" in p["note"]),
    "complex-plan": sum(1 for p in PAIRS if "complex-plan" in p["note"]),
}
print(f"\n=== CURATOR DPO v3 SUMMARY ===")
print(f"  Total pairs: {len(PAIRS)}")
print(f"  File: {OUT_PATH}")
for k, v in counts.items(): print(f"  {k}: {v}")
print(f"\nTo merge with v1+v2 and train:")
print(f"  cat workspace/training_data/curator_dpo_v1.jsonl \\")
print(f"      workspace/training_data/curator_dpo_v2.jsonl \\")
print(f"      workspace/training_data/curator_dpo_v3.jsonl > \\")
print(f"      workspace/training_data/curator_dpo_combined_v3.jsonl")
print(f"  python training/train_dpo.py \\")
print(f"    --base-model models/gemma-4-e4b-tsunami-v89-merged \\")
print(f"    --data workspace/training_data/curator_dpo_combined_v3.jsonl \\")
print(f"    --output models/gemma-4-e4b-tsunami-build-v90 \\")
print(f"    --epochs 1 --lora-r 16 --lr 5e-6 --beta 0.1")
