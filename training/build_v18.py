#!/usr/bin/env python3
"""v18 = v14 base + 25 PROVEN fixes = 537 examples.

Minimal delta approach. Only keep v17 additions that empirically helped:
- 15 extreme→project_init (L1 +10, 5 extreme fails → 1)
- 10 dedup→project_init (L4 HF08 passed)

DROPPED everything that hurt:
- single-turn error→file_edit (L3: 50%→0%, wrong format)
- trivial chat→message_chat (L1: overrode v14's correct message_result)
- research→search_web (didn't help)
- info→message_chat (didn't help)
- long-trajectory L5 examples (didn't help)
"""
import json
import random
import re
import sys

sys.path.insert(0, 'training')
from build_v16 import (
    SYSTEM_TEXT, QUOTE, TOOL_SCHEMAS, ARG_ORDER,
    format_declaration, format_value, format_tool_call, format_tool_response,
    build_example,
)
from build_v17 import (
    EXTREME_CASES, DEDUP_CASES,
    gen_extreme_project_init, gen_dedup_project_init,
)

random.seed(3141)


def main():
    v14_path = 'workspace/training_data/e4b_toolcall_train_v14.jsonl'
    v18_path = 'workspace/training_data/e4b_toolcall_train_v18.jsonl'

    v14 = []
    with open(v14_path) as f:
        for line in f:
            v14.append(json.loads(line))
    print(f"Loaded {len(v14)} v14 examples")

    generators = [
        (gen_extreme_project_init, 15),  # L1 extreme
        (gen_dedup_project_init, 10),     # L4 HF08
    ]

    new = []
    for gen, count in generators:
        for _ in range(count):
            user, turns = gen()
            text = build_example(user, turns)
            new.append({'text': text})

    lens = [len(re.findall(r'call:\w+', ex['text'])) for ex in new]
    print(f"Generated {len(new)} new examples")
    print(f"  length: min={min(lens)} max={max(lens)} avg={sum(lens)/len(lens):.1f}")

    with open(v18_path, 'w') as f:
        for ex in v14 + new:
            f.write(json.dumps(ex, ensure_ascii=False) + '\n')
    print(f"Wrote {len(v14) + len(new)} examples to {v18_path}")


if __name__ == '__main__':
    main()
