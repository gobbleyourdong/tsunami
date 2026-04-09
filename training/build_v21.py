#!/usr/bin/env python3
"""v21 = v14 base (512) + 25 v18 wins + 15 L3 multi-turn (HALF of v19)
with BALANCED system prompt that mentions file_edit but defaults to
file_write. Total 552 examples.

Findings from v19/v20:
- 31 L3 multi-turn examples break L5 regardless of prompt
- L3 67% in v19 came from the prompt change, not examples alone
- 0 L5 passes in v19 and v20 with 31 examples

Hypothesis:
- 15 L3 examples (half dose) + balanced prompt = partial L3 gain
  with less L5 disruption
- Balanced prompt says "file_write is default, file_edit for targeted fixes"
- Should land between v18 (2/9 L5, 33% L3) and v19 (0/9 L5, 67% L3)
"""
import json
import random
import re
import sys

sys.path.insert(0, 'training')
from build_v16 import (
    QUOTE, TOOL_SCHEMAS, ARG_ORDER,
    format_declaration, format_value, format_tool_call, format_tool_response,
)
from build_v17 import gen_extreme_project_init, gen_dedup_project_init
from build_v19 import (
    gen_l3_type_error, gen_l3_syntax_error, gen_l3_import_not_found,
    gen_l3_missing_module, gen_l3_wrong_path, gen_l3_css_import,
)

random.seed(6173)


# BALANCED prompt: mentions file_edit but defaults to file_write
SYSTEM_TEXT_V21 = """You are Tsunami. You are the wave. You build apps by calling tools.

The ocean:
- current: your sense of direction. If uncertain, search first.
- circulation: routing. Low tension=deliver. High tension=search or refuse.
- pressure: sustained uncertainty. 2 failures=search. 4 failures=ask the user.
- eddies: parallel workers. 3+ components=dispatch swell.
- undertow: QA. ALWAYS verify before delivering.
- break: compile. shell_exec build after EVERY file_write.
- reef: error. Default: file_write (full rewrite). For single-line type/syntax fixes only: file_edit. Then rebuild.

THE PIPELINE (every build follows this EXACTLY):
1. project_init(name) — scaffold the project
2. file_write(App.tsx) — write COMPLETE code
3. shell_exec("cd deliverables/{name} && npx vite build") — run the break
4. IF ERROR: file_read → file_write (full rewrite) → shell_exec rebuild
   EXCEPTION: single-line type/syntax fix → file_edit → shell_exec rebuild
5. undertow(dist/index.html) — QA before delivery
6. message_result — land the wave

RESUME/MODIFY (existing project):
1. file_read → 2. file_write (rewrite) or file_edit (single-line fix) → 3. shell_exec build → 4. message_result

NEVER skip the break. NEVER deliver without building. One tool call per response. Be brief."""


def build_example_v21(user_prompt, turns):
    tools_used = set(n for n, _, _ in turns) | {'file_write', 'shell_exec', 'message_result'}
    tools_used &= set(TOOL_SCHEMAS.keys())
    declarations = [format_declaration(n) for n in sorted(tools_used)]
    parts = [f'<|turn>system\n{SYSTEM_TEXT_V21}']
    parts.extend(declarations)
    parts.append('<turn|>')
    parts.append(f'<|turn>user\n{user_prompt}<turn|>')
    for name, args, response in turns:
        call = format_tool_call(name, args)
        parts.append(f'<|turn>model\n{call}<turn|>')
        resp = format_tool_response(name, response)
        parts.append(f'<|turn>user\n{resp}<turn|>')
    return '\n'.join(parts)


def main():
    v14_path = 'workspace/training_data/e4b_toolcall_train_v14.jsonl'
    v21_path = 'workspace/training_data/e4b_toolcall_train_v21.jsonl'

    v14 = []
    with open(v14_path) as f:
        for line in f:
            v14.append(json.loads(line))
    print(f"Loaded {len(v14)} v14 examples")

    generators = [
        # v18's proven wins
        (gen_extreme_project_init, 15),
        (gen_dedup_project_init, 10),
        # HALF of v19's L3 multi-turn examples (15 instead of 31)
        (gen_l3_type_error, 4),
        (gen_l3_syntax_error, 4),
        (gen_l3_import_not_found, 2),
        (gen_l3_missing_module, 2),
        (gen_l3_wrong_path, 1),
        (gen_l3_css_import, 2),
    ]

    new = []
    for gen, count in generators:
        for _ in range(count):
            user, turns = gen()
            text = build_example_v21(user, turns)
            new.append({'text': text})

    lens = [len(re.findall(r'call:\w+', ex['text'])) for ex in new]
    print(f"Generated {len(new)} new examples")
    print(f"  length: min={min(lens)} max={max(lens)} avg={sum(lens)/len(lens):.1f}")
    print(f"  1-tool: {sum(1 for l in lens if l == 1)}")
    print(f"  2-tool: {sum(1 for l in lens if l == 2)}")

    with open(v21_path, 'w') as f:
        for ex in v14 + new:
            f.write(json.dumps(ex, ensure_ascii=False) + '\n')
    print(f"Wrote {len(v14) + len(new)} examples to {v21_path}")


if __name__ == '__main__':
    main()
