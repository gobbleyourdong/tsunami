#!/usr/bin/env python3
"""31B v4 = v2 data (19 examples) + BOS fix + Unsloth response masking."""
import json, os, sys
from transformers import AutoTokenizer
sys.path.insert(0, "training")
from build_v69 import SYSTEM_TEXT, TOOLS, build_pipeline
from build_v69 import APPS as APPS_V69
from build_v73 import build_l3_direct_fix, L3_EXAMPLES as V73_L3
from build_v78 import bare_l3, BARE_L3

MODEL = "google/gemma-4-31B-it"
OUT = "workspace/training_data/31b_toolcall_train_v4.jsonl"
print(f"Loading tokenizer: {MODEL}")
tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
examples = []
for name, desc, files in APPS_V69:
    msgs = build_pipeline(name, desc, files, parallel=False)
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    text = text.removeprefix("<bos>")
    examples.append({"text": text})
for ex in V73_L3:
    msgs = build_l3_direct_fix(ex["name"], ex["desc"], ex["files"], ex["error"], ex["fix_call"])
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    text = text.removeprefix("<bos>")
    examples.append({"text": text})
for sc in BARE_L3:
    msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    text = text.removeprefix("<bos>")
    examples.append({"text": text})
print(f"Total: {len(examples)} examples")
has_bos = sum(1 for e in examples if e["text"].startswith("<bos>"))
print(f"Still has bos: {has_bos}/{len(examples)} (should be 0)")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    for e in examples:
        f.write(json.dumps(e) + "\n")
print(f"Wrote {OUT}")
