#!/usr/bin/env python3
"""Curator DPO pairs v4 — targeting 4 uncovered build HF scenarios.

Current combined_v3 (73 pairs) covers: HF03/06/07/08/09/10 + bug-fixes.
MISSING explicit DPO pairs for:
  HF01: Auto-scaffold — simple build prompt -> project_init (not search_web or chat)
  HF02: Research gate — visual clone prompt -> search_web first (not project_init)
  HF04: Code-write gate — after project_init -> file_write code (not message_result empty)
  HF05: Shell loop — after 2 identical failures -> file_write missing file (not retry build)

3 pairs per scenario = 12 new pairs.

Usage:
  /usr/bin/python3 training/build_curator_v4.py
  Output: workspace/training_data/curator_dpo_v4.jsonl
  Then:   cat workspace/training_data/curator_dpo_combined_v3.jsonl
              workspace/training_data/curator_dpo_v4.jsonl >
              workspace/training_data/curator_dpo_combined_v4.jsonl
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
    "Missing file -> file_write. Wrong path -> shell_exec with corrected path (NEVER message_chat). "
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
    {"type": "function", "function": {"name": "project_init", "description": "Create a project.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Write a file with full content.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Make targeted modifications.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final outcome.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to the user.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "Search the web.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "plan_update", "description": "Create or revise the task plan.",
        "parameters": {"type": "object", "properties": {"goal": {"type": "string"}, "phases": {"type": "array"}}, "required": ["goal", "phases"]}}},
    {"type": "function", "function": {"name": "undertow", "description": "QA test an HTML file.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "file_read", "description": "Read a file.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]

CALC_APP = (
    "import { useState } from 'react';\n\n"
    "export default function App() {\n"
    "  const [display, setDisplay] = useState('0');\n"
    "  const [prev, setPrev] = useState('');\n"
    "  const [op, setOp] = useState('');\n\n"
    "  function press(key: string) {\n"
    "    if ('0123456789.'.includes(key)) {\n"
    "      setDisplay(d => d === '0' ? key : d + key);\n"
    "    } else if ('+-*/'.includes(key)) {\n"
    "      setPrev(display); setOp(key); setDisplay('0');\n"
    "    } else if (key === '=') {\n"
    "      const a = parseFloat(prev), b = parseFloat(display);\n"
    "      const r = op==='+' ? a+b : op==='-' ? a-b : op==='*' ? a*b : a/b;\n"
    "      setDisplay(String(r)); setPrev(''); setOp('');\n"
    "    } else if (key === 'C') { setDisplay('0'); setPrev(''); setOp(''); }\n"
    "  }\n\n"
    "  const KEYS = ['C','+-','%','/','7','8','9','*','4','5','6','-','1','2','3','+','0','.','='];\n"
    "  return (\n"
    "    <div className='app' style={{display:'flex',justifyContent:'center',alignItems:'center',minHeight:'100vh'}}>\n"
    "      <div className='card' style={{width:280,padding:16}}>\n"
    "        <div style={{textAlign:'right',fontSize:36,padding:'8px 12px',marginBottom:8,background:'rgba(0,0,0,.2)',borderRadius:8}}>{display}</div>\n"
    "        <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:6}}>\n"
    "          {KEYS.map(k=><button key={k} className={k==='='?'primary':'ghost'} onClick={()=>press(k)} style={{padding:'14px 0',fontSize:18}}>{k}</button>)}\n"
    "        </div>\n"
    "      </div>\n"
    "    </div>\n"
    "  );\n"
    "}"
)

TIMER_APP = (
    "import { useState, useEffect, useRef } from 'react';\n\n"
    "export default function App() {\n"
    "  const [ms, setMs] = useState(0);\n"
    "  const [running, setRunning] = useState(false);\n"
    "  const ref = useRef<NodeJS.Timeout | null>(null);\n\n"
    "  useEffect(() => {\n"
    "    if (running) { ref.current = setInterval(() => setMs(m => m + 10), 10); }\n"
    "    else if (ref.current) clearInterval(ref.current);\n"
    "    return () => { if (ref.current) clearInterval(ref.current); };\n"
    "  }, [running]);\n\n"
    "  const fmt = (n: number) => String(Math.floor(n / 60000)).padStart(2,'0') + ':' +\n"
    "    String(Math.floor((n % 60000) / 1000)).padStart(2,'0') + '.' +\n"
    "    String(Math.floor((n % 1000) / 10)).padStart(2,'0');\n\n"
    "  return (\n"
    "    <div className='app' style={{display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',minHeight:'100vh',gap:24}}>\n"
    "      <div style={{fontSize:64,fontWeight:700,fontVariantNumeric:'tabular-nums'}}>{fmt(ms)}</div>\n"
    "      <div style={{display:'flex',gap:12}}>\n"
    "        <button className='primary' onClick={()=>setRunning(r=>!r)}>{running?'Pause':'Start'}</button>\n"
    "        <button className='ghost' onClick={()=>{setRunning(false);setMs(0);}}>Reset</button>\n"
    "      </div>\n"
    "    </div>\n"
    "  );\n"
    "}"
)

COLOR_APP = (
    "import { useState } from 'react';\n\n"
    "export default function App() {\n"
    "  const [h, setH] = useState(210);\n"
    "  const [s, setS] = useState(80);\n"
    "  const [l, setL] = useState(55);\n"
    "  const hex = `hsl(${h},${s}%,${l}%)`;\n\n"
    "  return (\n"
    "    <div className='app' style={{display:'flex',justifyContent:'center',alignItems:'center',minHeight:'100vh'}}>\n"
    "      <div className='card' style={{width:340,padding:24,display:'flex',flexDirection:'column',gap:20}}>\n"
    "        <div style={{height:120,borderRadius:12,background:hex}} />\n"
    "        <div style={{fontFamily:'monospace',textAlign:'center',fontSize:18}}>{hex}</div>\n"
    "        {[['Hue',h,setH,0,360],[' Saturation',s,setS,0,100],['Lightness',l,setL,0,100]].map(([label,val,set,min,max])=>\n"
    "          <div key={String(label)}>\n"
    "            <label style={{display:'flex',justifyContent:'space-between',marginBottom:4}}><span>{label}</span><span>{val}</span></label>\n"
    "            <input type='range' min={min} max={max} value={val} onChange={e=>(set as any)(+e.target.value)} style={{width:'100%'}} />\n"
    "          </div>\n"
    "        )}\n"
    "      </div>\n"
    "    </div>\n"
    "  );\n"
    "}"
)


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

# ── HF01: Auto-scaffold — simple build -> project_init (not search first) ────
for i, (app, name) in enumerate([
    ("a calculator app",   "calculator"),
    ("a countdown timer",  "timer"),
    ("a color picker tool","color-picker"),
]):
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Build " + app}]
    PAIRS.append(make_pair(msgs,
        chosen_fn="project_init", chosen_args={"name": name},
        rejected_fn="search_web",  rejected_args={"query": app + " react typescript tutorial"},
        source_bug="HF01-auto-scaffold",
        note=f"hf01-{i+1}: simple build prompt -> project_init immediately, NOT search_web",
    ))

# ── HF02: Research gate — visual clone -> search_web first ───────────────────
for i, (prompt, query) in enumerate([
    ("Build a pricing page that looks like the Stripe pricing page",
     "Stripe pricing page design layout 2026"),
    ("Build a dashboard inspired by the Linear app UI",
     "Linear app dashboard UI design reference"),
    ("Build a landing page styled like Vercel's homepage",
     "Vercel homepage design layout reference"),
]):
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    PAIRS.append(make_pair(msgs,
        chosen_fn="search_web",    chosen_args={"query": query},
        rejected_fn="project_init", rejected_args={"name": "app"},
        source_bug="HF02-research-gate",
        note=f"hf02-{i+1}: visual clone prompt -> search_web FIRST, NOT project_init",
    ))

# ── HF04: Code-write gate — after project_init -> file_write (not deliver) ───
for i, (app, name, code) in enumerate([
    ("a calculator app",    "calculator",   CALC_APP),
    ("a countdown timer",   "timer",        TIMER_APP),
    ("a color picker tool", "color-picker", COLOR_APP),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build " + app},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": name})}}]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created project '{name}'. Write in src/."},
    ]
    PAIRS.append(make_pair(msgs,
        chosen_fn="file_write",    chosen_args={"path": "src/App.tsx", "content": code},
        rejected_fn="message_result", rejected_args={"text": name + " scaffold is ready."},
        source_bug="HF04-code-write-gate",
        note=f"hf04-{i+1}: after project_init -> file_write App.tsx with code, NOT message_result empty scaffold",
    ))

# ── HF05: Shell loop — 2 identical failures -> file_write missing file ────────
for i, (component, module_err) in enumerate([
    ("Header",    "Cannot find module './components/Header'"),
    ("Sidebar",   "Cannot find module './components/Sidebar'"),
    ("DataTable", "Cannot find module './components/DataTable'"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Build a dashboard app"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function",
            "function": {"name": "project_init", "arguments": json.dumps({"name": "dashboard"})}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "[project_init] Created 'dashboard'."},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c2", "type": "function",
            "function": {"name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": f"import {component} from './components/{component}';\nexport default function App() {{ return <{component} />; }}"})}}]},
        {"role": "tool", "tool_call_id": "c2", "content": "[file_write] src/App.tsx written."},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c3", "type": "function",
            "function": {"name": "shell_exec", "arguments": json.dumps({"command": "npm run build"})}}]},
        {"role": "tool", "tool_call_id": "c3", "content": f"[shell_exec] ERROR: {module_err}. Build failed."},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c4", "type": "function",
            "function": {"name": "shell_exec", "arguments": json.dumps({"command": "npm run build"})}}]},
        {"role": "tool", "tool_call_id": "c4", "content": f"[shell_exec] ERROR: {module_err}. Build failed."},
    ]
    PAIRS.append(make_pair(msgs,
        chosen_fn="file_write",
        chosen_args={"path": f"src/components/{component}.tsx",
                     "content": f"export default function {component}() {{ return <div className='card'>{component}</div>; }}"},
        rejected_fn="shell_exec", rejected_args={"command": "npm run build"},
        source_bug="HF05-shell-loop",
        note=f"hf05-{i+1}: 2 identical build failures (missing {component}) -> file_write the missing file, NOT retry shell_exec",
    ))


# ── Output ────────────────────────────────────────────────────────────────────
OUT_V4 = Path("workspace/training_data/curator_dpo_v4.jsonl")
OUT_COMBINED = Path("workspace/training_data/curator_dpo_combined_v4.jsonl")
OUT_V4.parent.mkdir(parents=True, exist_ok=True)

with open(OUT_V4, "w") as f:
    for p in PAIRS:
        f.write(json.dumps(p) + "\n")

# Merge combined_v3 + v4 -> combined_v4
existing = Path("workspace/training_data/curator_dpo_combined_v3.jsonl")
all_lines = []
if existing.exists():
    all_lines.extend(l for l in existing.read_text().splitlines() if l.strip())
all_lines.extend(l for l in OUT_V4.read_text().splitlines() if l.strip())
OUT_COMBINED.write_text("\n".join(all_lines) + "\n")

counts = {
    "hf01-auto-scaffold":  sum(1 for p in PAIRS if "hf01" in p["note"]),
    "hf02-research-gate":  sum(1 for p in PAIRS if "hf02" in p["note"]),
    "hf04-code-write-gate":sum(1 for p in PAIRS if "hf04" in p["note"]),
    "hf05-shell-loop":     sum(1 for p in PAIRS if "hf05" in p["note"]),
}
print(f"\n=== BUILD CURATOR DPO v4 SUMMARY ===")
print(f"  New pairs: {len(PAIRS)}")
print(f"  v4 file: {OUT_V4}")
combined_total = sum(1 for l in OUT_COMBINED.read_text().splitlines() if l.strip())
print(f"  Combined v4: {OUT_COMBINED} ({combined_total} total pairs)")
for k, v in counts.items():
    print(f"  {k}: {v}")
print(f"\nAll 10 HF scenarios now covered:")
print(f"  HF01-auto-scaffold: v4 (3 pairs)")
print(f"  HF02-research-gate: v4 (3 pairs)")
print(f"  HF03-stall:         v3 (3 pairs)")
print(f"  HF04-code-write:    v4 (3 pairs)")
print(f"  HF05-shell-loop:    v4 (3 pairs)")
print(f"  HF06-info-loop:     v3 (3 pairs)")
print(f"  HF07-auto-wire:     v3 (3 pairs)")
print(f"  HF08-dedup-guard:   v3 (3 pairs)")
print(f"  HF09-complex-plan:  v3 (3 pairs)")
print(f"  HF10-undertow-qa:   v3 + v1 (multiple pairs)")
print(f"\nTo train build-v90 (use combined_v4):")
print(f"  python training/train_dpo.py \\")
print(f"    --base-model models/gemma-4-e4b-tsunami-v89-merged \\")
print(f"    --data workspace/training_data/curator_dpo_combined_v4.jsonl \\")
print(f"    --output models/gemma-4-e4b-tsunami-build-v90 \\")
print(f"    --epochs 1 --lora-r 16 --lr 5e-6 --beta 0.1")
