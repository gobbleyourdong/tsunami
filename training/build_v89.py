#!/usr/bin/env python3
"""v89 — v88 + 2 bare examples for HF05/HF06 L4 regressions.

v88 (445/500): L5=100% but L4 regressed 90→70 (lost HF05+HF06).
v89: add 2 bare examples to recover L4 while keeping L5=100%.
Target: v87 L4 (90%) + v88 L5 (100%) = 465/500.
"""
import json, os, sys
from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS
from build_v88 import *  # all v88 examples + builders

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v89.jsonl"

# HF05: After 2 build failures → file_write the missing component
def bare_hf05():
    """Shell loop: 2 failed builds → write missing file (not retry)."""
    return [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "The build keeps failing. Fix it."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/app && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "[shell_exec] Error: Cannot find module './components/Header'"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/app && npx vite build"}}}]},
        {"role": "tool", "name": "shell_exec",
         "content": "[shell_exec] Error: Cannot find module './components/Header'"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "file_write",
             "arguments": {"path": "deliverables/app/src/components/Header.tsx",
                          "content": "export default function Header() {\n  return <header><h1>Header</h1></header>\n}"}}}]},
    ]

# HF06: Conversational prompt → message_chat (not project_init)
def bare_hf06():
    """Conversation: greeting → message_chat with done=true."""
    return [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Hello! What can you build?"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_chat",
             "arguments": {"text": "I'm Tsunami. I can build web apps, dashboards, games, tools — anything you can describe. What would you like?", "done": True}}}]},
    ]

def main():
    print(f"Loading: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    assert "Components" in SYSTEM_TEXT
    print("SYSTEM_TEXT verified.")

    examples = []

    # === All 37 v88 examples ===
    for name, desc, files in APPS_V69:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    for ex in V73_L3:
        msgs = build_l3_direct_fix(ex["name"], ex["desc"], ex["files"], ex["error"], ex["fix_call"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    for sc in BARE_L3:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    for sc in EXTRA_BARE_L3:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    msgs = build_plan_example()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    for name, desc, files in INTEGRATION_APPS[:2]:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    name, desc, files = INTEGRATION_APPS[2]
    msgs = build_integration_with_error(name, desc, files)
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    for builder in [build_search_then_build, build_read_then_edit, build_glob_then_read,
                    build_swell_example, build_message_info_example,
                    build_swell_generic, build_swell_analyze_example]:
        msgs = builder()
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # v88 additions
    msgs = build_dataviz_example()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    for sc in EXTRA_ER05:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    msgs = build_plan_example_2()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    msgs = build_stall_recovery_1()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    msgs = build_stall_recovery_2()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # === NEW v89: +2 bare L4 examples ===
    msgs = bare_hf05()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    msgs = bare_hf06()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    print(f"\nTotal: {len(examples)} examples (37 from v88 + 2 new L4 bare)")

    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"Wrote {len(examples)} examples to {OUT_PATH}")

if __name__ == "__main__":
    main()
