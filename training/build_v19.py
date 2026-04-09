#!/usr/bin/env python3
"""v19 = v14 base + 25 proven wins (v18) + 30 L3 multi-turn error-recovery examples.

Key insight: L3 eval uses multi-turn format where error is in tool_response,
not user message. Training examples must match exactly:
  system + user("The build just failed. Fix it.") +
  model(shell_exec build) + tool(error) +
  model(FIX TOOL — this is what L3 scores)

Also: v14 system prompt teaches "file_read -> file_write (rewrite)" but L3
eval expects file_edit for targeted fixes. v19 uses an updated system
prompt that says "file_edit for targeted fixes, file_write for full rewrites
or new files".

Total: 512 v14 + 25 v18 wins + 30 L3 multi-turn = 567 examples.
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

random.seed(4711)

# Updated system prompt — file_edit for targeted fixes
SYSTEM_TEXT_V19 = """You are Tsunami. You are the wave. You build apps by calling tools.

The ocean:
- current: your sense of direction. If uncertain, search first.
- circulation: routing. Low tension=deliver. High tension=search or refuse.
- pressure: sustained uncertainty. 2 failures=search. 4 failures=ask the user.
- eddies: parallel workers. 3+ components=dispatch swell.
- undertow: QA. ALWAYS verify before delivering.
- break: compile. shell_exec build after EVERY file_write.
- reef: error. file_edit for targeted fixes (type/syntax). file_write for full rewrites or missing files.

THE PIPELINE (every build follows this EXACTLY):
1. project_init(name) — scaffold the project
2. file_write(App.tsx) — write COMPLETE code
3. shell_exec("cd deliverables/{name} && npx vite build") — run the break
4. IF ERROR: file_edit (targeted fix) or file_write (full rewrite) → shell_exec rebuild
5. undertow(dist/index.html) — QA before delivery
6. message_result — land the wave

RESUME/MODIFY (existing project):
1. file_read → 2. file_edit (small change) or file_write (rewrite) → 3. shell_exec build → 4. message_result

NEVER skip the break. NEVER deliver without building. One tool call per response. Be brief."""


def build_example_v19(user_prompt, turns):
    """Build example with v19 system prompt."""
    tools_used = set(n for n, _, _ in turns) | {'file_write', 'shell_exec', 'message_result'}
    tools_used &= set(TOOL_SCHEMAS.keys())
    declarations = [format_declaration(n) for n in sorted(tools_used)]
    parts = [f'<|turn>system\n{SYSTEM_TEXT_V19}']
    parts.extend(declarations)
    parts.append('<turn|>')
    parts.append(f'<|turn>user\n{user_prompt}<turn|>')
    for name, args, response in turns:
        call = format_tool_call(name, args)
        parts.append(f'<|turn>model\n{call}<turn|>')
        resp = format_tool_response(name, response)
        parts.append(f'<|turn>user\n{resp}<turn|>')
    return '\n'.join(parts)


# ============================================================================
# L3 MULTI-TURN ERROR RECOVERY — matches eval_error_recovery.py format exactly
# ============================================================================

# Each case: (error_text_in_tool_response, correct_tool, correct_args)
# Format matches eval: "The build just failed. Fix it." → shell_exec → error → FIX
L3_TYPE_ERRORS = [
    # (error text, path, old, new)
    ("src/App.tsx(12,5): Type 'null' is not assignable to type 'string'. setError(null) should be setError('')",
     "deliverables/app/src/App.tsx", 'setError(null)', "setError('')"),
    ("src/components/Counter.tsx(8,12): Type 'string' is not assignable to type 'number'. count: '0' should be count: 0",
     "deliverables/app/src/components/Counter.tsx", "count: '0'", "count: 0"),
    ("src/App.tsx(15,8): Property 'value' is missing in type '{}' but required in type 'Props'.",
     "deliverables/app/src/App.tsx", '<Component />', '<Component value="" />'),
    ("src/components/Input.tsx(4,10): Type '(e: Event) => void' is not assignable to type 'ChangeEventHandler'.",
     "deliverables/app/src/components/Input.tsx", '(e: Event) => void', '(e: React.ChangeEvent<HTMLInputElement>) => void'),
    ("src/App.tsx(22,6): Type 'Date' is not assignable to type 'string'. Use .toISOString().",
     "deliverables/app/src/App.tsx", 'const date = new Date()', 'const date = new Date().toISOString()'),
    ("src/components/Form.tsx(9,3): Type 'number | undefined' is not assignable to type 'number'.",
     "deliverables/app/src/components/Form.tsx", 'const n: number = props.value', 'const n: number = props.value ?? 0'),
    ("src/App.tsx(7,12): Argument of type 'unknown' is not assignable to parameter of type 'string'.",
     "deliverables/app/src/App.tsx", 'parse(data)', 'parse(data as string)'),
    ("src/App.tsx(18,4): Type 'boolean' is not assignable to type 'string'.",
     "deliverables/app/src/App.tsx", 'isActive', 'String(isActive)'),
]

L3_SYNTAX_ERRORS = [
    # Missing closing parens/brackets — file_edit fix
    ("src/App.tsx(8,45): Expected ')' to close '(' at line 8. {items.map(i => <div key={i}>{i}</div>",
     "deliverables/app/src/App.tsx", 'items.map(i => <div key={i}>{i}</div>', 'items.map(i => <div key={i}>{i}</div>)'),
    ("src/App.tsx(12,20): Unexpected token. setItems([...items, newItem",
     "deliverables/app/src/App.tsx", 'setItems([...items, newItem', 'setItems([...items, newItem])'),
    ("src/components/List.tsx(5,15): '}' expected. return <div>{children",
     "deliverables/app/src/components/List.tsx", '{children', '{children}'),
    ("src/App.tsx(11,8): ',' expected. const [x y] = useState(0)",
     "deliverables/app/src/App.tsx", 'const [x y]', 'const [x, y]'),
    ("src/App.tsx(20,4): Missing semicolon. const a = 1 const b = 2",
     "deliverables/app/src/App.tsx", 'const a = 1 const b = 2', 'const a = 1; const b = 2'),
    ("src/App.tsx(6,30): Unexpected '<'. return <div>{<Component></div>",
     "deliverables/app/src/App.tsx", '{<Component></div>', '{<Component />}</div>'),
    ("src/App.tsx(14,11): Expected identifier. import { from 'react'",
     "deliverables/app/src/App.tsx", "import { from 'react'", "import { useState } from 'react'"),
    ("src/App.tsx(3,25): Unterminated string literal. const s = \"hello",
     "deliverables/app/src/App.tsx", 'const s = "hello', 'const s = "hello"'),
]

L3_IMPORT_NOT_FOUND = [
    # Missing file → file_write to create it
    ("Could not resolve './components/Header' from src/App.tsx. File does not exist.",
     "deliverables/app/src/components/Header.tsx",
     'export default function Header() {\n  return <header><h1>App</h1></header>\n}'),
    ("Could not resolve './components/Footer' from src/App.tsx. File does not exist.",
     "deliverables/app/src/components/Footer.tsx",
     'export default function Footer() {\n  return <footer>© 2026</footer>\n}'),
    ("Could not resolve './utils/format' from src/App.tsx. File does not exist.",
     "deliverables/app/src/utils/format.ts",
     'export function format(n: number): string {\n  return n.toFixed(2)\n}'),
    ("Could not resolve './hooks/useTheme' from src/App.tsx. File does not exist.",
     "deliverables/app/src/hooks/useTheme.ts",
     'import { useState } from "react"\nexport function useTheme() {\n  return useState("light")\n}'),
]

L3_MISSING_MODULE = [
    # Missing npm module → shell_exec npm install
    ("Cannot find module 'recharts'. Did you install it?", "npm install recharts"),
    ("Cannot find module 'react-router-dom'. Did you install it?", "npm install react-router-dom"),
    ("Cannot find module 'axios'. Did you install it?", "npm install axios"),
    ("Cannot find module 'zustand'. Did you install it?", "npm install zustand"),
]

L3_WRONG_PATH = [
    # cd failed → shell_exec with correct path
    ("bash: cd: workspace/deliverables/app: No such file or directory", 'cd deliverables/app && npx vite build'),
    ("bash: cd: /home/user/app: No such file or directory", 'cd deliverables/app && npx vite build'),
]

L3_CSS_IMPORT = [
    # CSS import missing → file_edit to fix import
    ("Could not resolve 'leaflet/dist/leaflet.css' from src/App.tsx",
     "deliverables/app/src/App.tsx", "import 'leaflet/dist/leaflet.css'", "// import 'leaflet/dist/leaflet.css' — remove if not using map"),
    ("Could not resolve 'bootstrap/dist/css/bootstrap.min.css' from src/App.tsx",
     "deliverables/app/src/App.tsx", "import 'bootstrap/dist/css/bootstrap.min.css'", "// bootstrap not installed"),
    ("Could not resolve './styles.css' from src/components/Button.tsx",
     "deliverables/app/src/components/Button.tsx", "import './styles.css'", "import '../styles.css'"),
    ("Could not resolve 'material-icons/iconfont/material-icons.css' from src/App.tsx",
     "deliverables/app/src/App.tsx", "import 'material-icons/iconfont/material-icons.css'", "// material-icons not installed"),
]


def gen_l3_type_error():
    error_text, path, old, new = random.choice(L3_TYPE_ERRORS)
    turns = [
        ('shell_exec', {'command': 'cd deliverables/app && npx vite build'},
         f'[shell_exec] Error: {error_text}'),
        ('file_edit', {'path': path, 'old_text': old, 'new_text': new},
         f'[file_edit] replaced in {path}'),
    ]
    return 'The build just failed. Fix it.', turns


def gen_l3_syntax_error():
    error_text, path, old, new = random.choice(L3_SYNTAX_ERRORS)
    turns = [
        ('shell_exec', {'command': 'cd deliverables/app && npx vite build'},
         f'[shell_exec] Error: {error_text}'),
        ('file_edit', {'path': path, 'old_text': old, 'new_text': new},
         f'[file_edit] replaced in {path}'),
    ]
    return 'The build just failed. Fix it.', turns


def gen_l3_import_not_found():
    error_text, path, content = random.choice(L3_IMPORT_NOT_FOUND)
    turns = [
        ('shell_exec', {'command': 'cd deliverables/app && npx vite build'},
         f'[shell_exec] Error: {error_text}'),
        ('file_write', {'path': path, 'content': content},
         f'[file_write] wrote {len(content)} bytes to {path}'),
    ]
    return 'The build just failed. Fix it.', turns


def gen_l3_missing_module():
    error_text, fix_cmd = random.choice(L3_MISSING_MODULE)
    turns = [
        ('shell_exec', {'command': 'cd deliverables/app && npx vite build'},
         f'[shell_exec] Error: {error_text}'),
        ('shell_exec', {'command': f'cd deliverables/app && {fix_cmd}'},
         f'[shell_exec] added 1 package'),
    ]
    return 'The build just failed. Fix it.', turns


def gen_l3_wrong_path():
    error_text, fix_cmd = random.choice(L3_WRONG_PATH)
    turns = [
        ('shell_exec', {'command': 'cd workspace/deliverables/app && npx vite build'},
         f'[shell_exec] {error_text}'),
        ('shell_exec', {'command': fix_cmd},
         '[shell_exec] vite build succeeded'),
    ]
    return 'The build just failed. Fix it.', turns


def gen_l3_css_import():
    error_text, path, old, new = random.choice(L3_CSS_IMPORT)
    turns = [
        ('shell_exec', {'command': 'cd deliverables/app && npx vite build'},
         f'[shell_exec] Error: {error_text}'),
        ('file_edit', {'path': path, 'old_text': old, 'new_text': new},
         f'[file_edit] fixed import in {path}'),
    ]
    return 'The build just failed. Fix it.', turns


def main():
    v14_path = 'workspace/training_data/e4b_toolcall_train_v14.jsonl'
    v19_path = 'workspace/training_data/e4b_toolcall_train_v19.jsonl'

    v14 = []
    with open(v14_path) as f:
        for line in f:
            v14.append(json.loads(line))
    print(f"Loaded {len(v14)} v14 examples")

    generators = [
        # Proven wins from v17/v18
        (gen_extreme_project_init, 15),
        (gen_dedup_project_init, 10),
        # New L3 multi-turn examples matching eval format
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
            # Use v19 system prompt for new examples
            text = build_example_v19(user, turns)
            new.append({'text': text})

    lens = [len(re.findall(r'call:\w+', ex['text'])) for ex in new]
    print(f"Generated {len(new)} new examples")
    print(f"  length: min={min(lens)} max={max(lens)} avg={sum(lens)/len(lens):.1f}")
    print(f"  2-tool (L3 recovery): {sum(1 for l in lens if l == 2)}")

    # Validate path-first
    pf_write = total_write = 0
    pf_edit = total_edit = 0
    for ex in new:
        for m in re.findall(r'<\|tool_call>call:file_write\{(.*?)\}<tool_call\|>', ex['text'], re.DOTALL):
            total_write += 1
            if m.startswith('path:'):
                pf_write += 1
        for m in re.findall(r'<\|tool_call>call:file_edit\{(.*?)\}<tool_call\|>', ex['text'], re.DOTALL):
            total_edit += 1
            if m.startswith('path:'):
                pf_edit += 1
    print(f"  path-first file_write: {pf_write}/{total_write}")
    print(f"  path-first file_edit:  {pf_edit}/{total_edit}")

    with open(v19_path, 'w') as f:
        for ex in v14 + new:
            f.write(json.dumps(ex, ensure_ascii=False) + '\n')
    print(f"Wrote {len(v14) + len(new)} examples to {v19_path}")


if __name__ == '__main__':
    main()
