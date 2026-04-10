#!/usr/bin/env python3
"""v81 retrain — rebuild v80 champion data with updated SYSTEM_TEXT.

Changes from v80:
  - Component import guide added to SYSTEM_TEXT
  - All system prompt triggers from v79/v80 preserved
  - Same 19 examples (10 happy + 6 pipeline L3 + 3 bare L3)

Train with: train_unsloth.py --data e4b_toolcall_train_v81r.jsonl --epochs 10 --grad-accum 4

Regression analysis recommendations:
  - Try lr=1.5e-4 (between v80's 2e-4 and v84's 1e-4) to balance L4/L5
  - Try r=16 with updated SYSTEM_TEXT (v82 was r=16 with OLD text)
  - 10 epochs, grad_accum=4 = ~50 steps (v80 sweet spot)
"""
import json, os, sys
from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS, build_pipeline
from build_v69 import APPS as APPS_V69
from build_v73 import build_l3_direct_fix, L3_EXAMPLES as V73_L3
from build_v78 import bare_l3, BARE_L3

MODEL = "google/gemma-4-e4b-it"
OUT = "workspace/training_data/e4b_toolcall_train_v81r.jsonl"

print(f"Loading: {MODEL}")
tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)

# Verify SYSTEM_TEXT has all triggers
assert "Components:" in SYSTEM_TEXT, "Missing component guide"
assert "CSS resolution" in SYSTEM_TEXT, "Missing CSS trigger"
assert "Visual clones" in SYSTEM_TEXT, "Missing visual trigger"
assert "NEVER message_chat" in SYSTEM_TEXT, "Missing path trigger"
print("SYSTEM_TEXT has all triggers including component guide.")

examples = []
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

print(f"Total: {len(examples)} examples")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    for ex in examples:
        f.write(json.dumps(ex) + "\n")
print(f"Wrote {OUT}")
