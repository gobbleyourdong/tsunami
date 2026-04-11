#!/usr/bin/env python3
"""v91 — rebalance v90. Cut ER05 saturation, reinforce file_edit errors.

v90 (455): L4=90 (fixed HF06!) but L3=67 (ER03 regressed from oversaturated ER05).
v91: remove 3 ER05 extras, add 2 file_edit reinforcement + 1 T05 bare.
"""
import json, os, sys
from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS, build_pipeline, build_messages
from build_v69 import APPS as APPS_V69
from build_v73 import build_l3_direct_fix, L3_EXAMPLES as V73_L3
from build_v78 import bare_l3, BARE_L3
from build_v87 import (
    EXTRA_BARE_L3, INTEGRATION_APPS,
    build_plan_example, build_integration_with_error,
    build_search_then_build, build_read_then_edit, build_glob_then_read,
    build_swell_example, build_message_info_example,
    build_swell_generic, build_swell_analyze_example,
)
from build_v88 import (
    build_dataviz_example, EXTRA_ER05,
    build_plan_example_2, build_stall_recovery_1, build_stall_recovery_2,
)
from build_v90 import HF06_EXAMPLES, HF09_PROMPTS, bare_conversation, bare_plan, bare_hf05

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v91.jsonl"

# v91 NEW: Extra file_edit bare examples to counterbalance ER05
EXTRA_FILE_EDIT = [
    # ER03 variant: different syntax error → file_edit
    dict(
        initial_cmd="cd deliverables/app && npx vite build",
        error="src/App.tsx(15,3): Expression expected. Unexpected token '}'",
        fix_tool="file_edit",
        fix_args={
            "path": "deliverables/app/src/App.tsx",
            "old_text": "  }\n})",
            "new_text": "  }\n  return null\n})",
        },
    ),
    # Type error variant → file_edit
    dict(
        initial_cmd="cd deliverables/dashboard && npx vite build",
        error="src/App.tsx(22,10): Type 'number' is not assignable to type 'string'.",
        fix_tool="file_edit",
        fix_args={
            "path": "deliverables/dashboard/src/App.tsx",
            "old_text": "const label: string = count",
            "new_text": "const label: string = String(count)",
        },
    ),
]

# v91 NEW: T05 bare — "Thanks, that's all" → message_chat(done=true)
def bare_t05():
    return [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "Thanks, that's all I needed."},
        {"role": "assistant", "content": "", "tool_calls": [{
            "type": "function",
            "function": {"name": "message_chat",
             "arguments": {"text": "Glad I could help. The wave rests.", "done": True}}}]},
    ]


def main():
    print(f"Loading: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    assert "Components" in SYSTEM_TEXT
    print("SYSTEM_TEXT verified.")

    examples = []

    # === Core baseline: same as v89 (39 examples) ===
    
    # 1-10: Happy-path
    for name, desc, files in APPS_V69:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 11-16: Pipeline L3
    for ex in V73_L3:
        msgs = build_l3_direct_fix(ex["name"], ex["desc"], ex["files"], ex["error"], ex["fix_call"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 17-19: Bare L3
    for sc in BARE_L3:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 20: Extra bare ER01
    for sc in EXTRA_BARE_L3:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 21: Plan gate v1
    msgs = build_plan_example()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # 22-23: Integration happy
    for name, desc, files in INTEGRATION_APPS[:2]:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 24: Integration + error
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

    # 32: Data-viz scaffold
    msgs = build_dataviz_example()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # 33-34: v88 ER05 (KEEP only 2, not 6 like v90)
    for sc in EXTRA_ER05:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 35: Plan gate v2
    msgs = build_plan_example_2()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # 36-37: Stall recovery
    msgs = build_stall_recovery_1()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})
    msgs = build_stall_recovery_2()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # 38: HF05
    msgs = bare_hf05()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # 39-41: HF06 saturation (3 conversational → message_chat) — KEEP from v90
    for prompt, response in HF06_EXAMPLES:
        msgs = bare_conversation(prompt, response)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 42-44: HF09 saturation (3 bare plan_update) — KEEP from v90
    for prompt in HF09_PROMPTS:
        msgs = bare_plan(prompt)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # === v91 NEW: rebalance ===

    # 45-46: File_edit reinforcement (counterbalance ER05 shell_exec)
    for sc in EXTRA_FILE_EDIT:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 47: T05 bare (thanks → message_chat done)
    msgs = bare_t05()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # === Summary ===
    print(f"\nTotal: {len(examples)} examples")
    print(f"  Changes from v90 (48 → {len(examples)}):")
    print(f"  - REMOVED 3 ER05 saturation extras (6→3 total)")  
    print(f"  - ADDED 2 file_edit bare (rebalance L3)")
    print(f"  - ADDED 1 T05 bare (thanks → done)")
    print(f"  - KEPT HF06×3, HF09×3, HF05×1, stall×2")

    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"\nWrote {len(examples)} examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
