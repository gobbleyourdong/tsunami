#!/usr/bin/env python3
"""v20 = v14 base (512) + 25 v18 wins + 31 v19 L3 multi-turn examples
with v14 ORIGINAL system prompt. Total 568 examples.

v19 taught us:
- 31 multi-turn L3 examples work (L3: 33% -> 67%)
- BUT the new system prompt change caused L5 collapse (22% -> 0%)
- path_errors +200%, model uses file_edit where it should use file_write

v20: keep the examples, revert the prompt. Hypothesis: the multi-turn
examples teach the L3 behavior directly. The prompt doesn't need to
change — removing it should let L5 recover while L3 stays strong.
"""
import json
import random
import re
import sys

sys.path.insert(0, 'training')
from build_v16 import (
    SYSTEM_TEXT,  # This is the v14 original prompt
    QUOTE, TOOL_SCHEMAS, ARG_ORDER,
    format_declaration, format_value, format_tool_call, format_tool_response,
    build_example,  # uses SYSTEM_TEXT (v14 original)
)
from build_v17 import gen_extreme_project_init, gen_dedup_project_init
from build_v19 import (
    gen_l3_type_error, gen_l3_syntax_error, gen_l3_import_not_found,
    gen_l3_missing_module, gen_l3_wrong_path, gen_l3_css_import,
)

random.seed(5101)


def main():
    v14_path = 'workspace/training_data/e4b_toolcall_train_v14.jsonl'
    v20_path = 'workspace/training_data/e4b_toolcall_train_v20.jsonl'

    v14 = []
    with open(v14_path) as f:
        for line in f:
            v14.append(json.loads(line))
    print(f"Loaded {len(v14)} v14 examples")

    generators = [
        # v18's proven wins
        (gen_extreme_project_init, 15),
        (gen_dedup_project_init, 10),
        # v19's L3 multi-turn recovery examples
        (gen_l3_type_error, 8),
        (gen_l3_syntax_error, 8),
        (gen_l3_import_not_found, 4),
        (gen_l3_missing_module, 4),
        (gen_l3_wrong_path, 3),
        (gen_l3_css_import, 4),
    ]

    new = []
    for gen, count in generators:
        for _ in range(count):
            user, turns = gen()
            # CRITICAL: build_example (from v16) uses SYSTEM_TEXT (v14 original)
            # NOT build_example_v19 which uses the changed prompt
            text = build_example(user, turns)
            new.append({'text': text})

    lens = [len(re.findall(r'call:\w+', ex['text'])) for ex in new]
    print(f"Generated {len(new)} new examples")
    print(f"  length: min={min(lens)} max={max(lens)} avg={sum(lens)/len(lens):.1f}")
    print(f"  1-tool: {sum(1 for l in lens if l == 1)}")
    print(f"  2-tool (L3): {sum(1 for l in lens if l == 2)}")

    # Verify uses v14 original prompt
    check = new[30]['text']  # a L3 example
    if 'file_edit for targeted' in check:
        print("ERROR: new prompt leaked through!")
    elif 'REWRITE with file_write' in check:
        print("✓ Using v14 original system prompt")

    with open(v20_path, 'w') as f:
        for ex in v14 + new:
            f.write(json.dumps(ex, ensure_ascii=False) + '\n')
    print(f"Wrote {len(v14) + len(new)} examples to {v20_path}")


if __name__ == '__main__':
    main()
