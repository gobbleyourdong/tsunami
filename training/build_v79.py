#!/usr/bin/env python3
"""v79 -- v78b data (19 examples) rebuilt with updated SYSTEM_TEXT triggers.

v78b (champion, 436): 19 examples, 48 steps, loss 0.99
  L1 100 / L2 100 / L3 67 / L4 80 / L5 89

Loss 0.99 = near memorized. Data exhausted. Remaining failures
(ER05, ER06, HF02, HF09) are stubborn priors that targeted
data didn't break.

v79 strategy: same data, updated SYSTEM_TEXT with explicit triggers:
  - CSS resolution errors -> file_edit (don't file_read first)
  - Wrong path (cd fails) -> shell_exec (NEVER message_chat)
  - Visual clones -> search_web FIRST
  - Complex builds -> plan_update FIRST

The prompt updates propagate across:
  - build_v69.py SYSTEM_TEXT (training)
  - eval_error_recovery.py SYSTEM (L3 eval)
  - eval_hack_free.py SYSTEM (L4 eval)
  - eval_toolcall.py SYSTEM_PROMPT (L1 eval)
  - tsunami/prompt.py (L5 agent lite mode)

Model sees consistent guidance at train and eval time.
Training at v78b hyperparams (grad_accum=4, epochs=10 = 50 steps).
"""
import json
import os
import sys

from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS, build_pipeline
from build_v69 import APPS as APPS_V69
from build_v73 import build_l3_direct_fix, L3_EXAMPLES as V73_L3
from build_v78 import bare_l3, BARE_L3

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v79.jsonl"


def main():
    print(f"Loading: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)

    # Sanity check: SYSTEM_TEXT must have all 4 new triggers
    assert "CSS resolution errors" in SYSTEM_TEXT, "SYSTEM_TEXT missing CSS trigger"
    assert "Visual clones" in SYSTEM_TEXT, "SYSTEM_TEXT missing visual clone trigger"
    assert "Complex builds" in SYSTEM_TEXT, "SYSTEM_TEXT missing complex build trigger"
    assert "NEVER message_chat" in SYSTEM_TEXT, "SYSTEM_TEXT missing path trigger"
    print("SYSTEM_TEXT has all 4 triggers.")

    examples = []

    # 1. Happy-path: 10 v69 apps
    for name, desc, files in APPS_V69:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 2. Pipeline-format L3: 6 (from v73)
    for ex in V73_L3:
        msgs = build_l3_direct_fix(ex["name"], ex["desc"], ex["files"], ex["error"], ex["fix_call"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 3. Bare-format L3: 3 (from v78)
    for sc in BARE_L3:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    print(f"\nTotal: {len(examples)} examples (same as v78b)")
    print(f"  10 happy path")
    print(f"  6 pipeline L3")
    print(f"  3 bare L3")

    starts_bos = sum(1 for ex in examples if ex["text"].startswith("<bos>"))
    print(f"Starts with <bos>: {starts_bos}/{len(examples)}")

    # Verify triggers landed in rendered text
    trigger_count = sum(1 for ex in examples if "CSS resolution" in ex["text"])
    print(f"Examples with 'CSS resolution' trigger in system: {trigger_count}/{len(examples)}")

    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"Wrote {len(examples)} examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
