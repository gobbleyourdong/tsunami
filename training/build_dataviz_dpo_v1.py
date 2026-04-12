#!/usr/bin/env python3
"""Data-viz DPO pairs v1 — targeting L4 Hack-Free failures for the dataviz-v1 adapter.

Covers DVF01-DVF06 from eval_dataviz.py:
  DVF01: ChartCard usage — chart must be wrapped in ChartCard, not raw div
  DVF02: ResponsiveContainer — Recharts must be inside ResponsiveContainer
  DVF03: No raw fetch — data is hardcoded arrays or CsvLoader, not fetch()
  DVF04: StatRow for KPIs — KPI dashboards use StatRow component
  DVF05: data-viz template — project_init includes template="data-viz"
  DVF06: Undertow before deliver — undertow must run before message_result

Usage:
  /usr/bin/python3 training/build_dataviz_dpo_v1.py
  Output: workspace/training_data/dataviz_dpo_v1.jsonl
"""
import json
from datetime import date
from pathlib import Path

print("Loading tokenizer (google/gemma-4-e4b-it)...")
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("google/gemma-4-e4b-it", trust_remote_code=True)
print("Tokenizer loaded.")

TODAY = date.today().isoformat()

SYSTEM = """You are Tsunami. You are the wave. You build data-visualization dashboards by calling tools.

## Data-Viz Pipeline (every build follows this EXACTLY)

1. project_init(name, template="data-viz") -- create project from data-viz scaffold
2. file_write(src/App.tsx) -- write complete dashboard using ChartCard + Recharts
3. shell_exec -- run npm run build
4. IF ERROR: fix directly with file_edit
5. undertow -- QA before delivery
6. message_result -- land the wave

## Component Rules

- ALWAYS import ChartCard, StatRow from './components'
- ALWAYS wrap every Recharts chart in <ResponsiveContainer width="100%" height={300}>
- NEVER use raw fetch() for chart data -- hardcode sample data arrays or use CsvLoader
- StatRow for summary KPIs above charts

One tool call per response. Be brief."""

TOOLS = [
    {"type": "function", "function": {"name": "project_init", "description": "Create a project.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "template": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Write a file with full content.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Make targeted modifications to an existing file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final outcome.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to the user.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "undertow", "description": "QA test an HTML file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]


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

# ─────────────────────────────────────────────────────────────────────────────
# DVF01: ChartCard usage — after project_init, file_write must use ChartCard wrapper
# ─────────────────────────────────────────────────────────────────────────────
for i, (project, prompt, chart_type) in enumerate([
    ("sales-dashboard", "Build a monthly sales bar chart dashboard", "BarChart"),
    ("traffic-chart", "Build a line chart for website traffic analytics", "LineChart"),
    ("category-pie", "Build a pie chart showing product category breakdown", "PieChart"),
]):
    init_result = f"[project_init] Created '{project}' from data-viz scaffold. Write src/App.tsx."
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": project, "template": "data-viz"})}}
        ]},
        {"role": "tool", "tool_call_id": "c1", "content": init_result},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write",
        chosen_args={"path": "src/App.tsx", "content": f"import ChartCard from './components/ChartCard'\nimport {{ {chart_type}, ResponsiveContainer }} from 'recharts'\n// complete implementation"},
        rejected_fn="file_write",
        rejected_args={"path": "src/App.tsx", "content": f"import {{ {chart_type}, ResponsiveContainer }} from 'recharts'\n// app without ChartCard"},
        source_bug="DVF01-chartcard",
        note=f"chartcard-{i+1}: App.tsx must import and use ChartCard wrapper",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# DVF02: ResponsiveContainer — Recharts must be wrapped in ResponsiveContainer
# ─────────────────────────────────────────────────────────────────────────────
for i, (project, prompt, chart_type) in enumerate([
    ("expense-chart", "Build an expense tracker line chart", "LineChart"),
    ("revenue-bars", "Build a bar chart for quarterly revenue", "BarChart"),
    ("user-scatter", "Build a scatter chart for user engagement metrics", "ScatterChart"),
]):
    init_result = f"[project_init] Created '{project}' from data-viz scaffold. Write src/App.tsx."
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": project, "template": "data-viz"})}}
        ]},
        {"role": "tool", "tool_call_id": "c1", "content": init_result},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write",
        chosen_args={"path": "src/App.tsx", "content": f"import {{ {chart_type}, ResponsiveContainer }} from 'recharts'\n// <ResponsiveContainer width='100%' height={{300}}><{chart_type} .../></ResponsiveContainer>"},
        rejected_fn="file_write",
        rejected_args={"path": "src/App.tsx", "content": f"import {{ {chart_type} }} from 'recharts'\n// <{chart_type} width={{600}} height={{300}} .../>"},
        source_bug="DVF02-responsive-container",
        note=f"responsive-{i+1}: Recharts must be wrapped in ResponsiveContainer, not fixed width",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# DVF03: No raw fetch — use hardcoded data or CsvLoader, not fetch('/api/...')
# ─────────────────────────────────────────────────────────────────────────────
for i, (project, prompt, hardcoded) in enumerate([
    ("metrics-dash", "Build a dashboard that loads data from /api/metrics",
     "const data = [{ month: 'Jan', value: 1200 }, { month: 'Feb', value: 1800 }]"),
    ("sales-api", "Build a sales chart that fetches from /api/sales",
     "const data = [{ q: 'Q1', sales: 45000 }, { q: 'Q2', sales: 52000 }]"),
    ("live-feed", "Build a chart that polls /api/live-data every 5 seconds",
     "const data = [{ t: '10:00', val: 42 }, { t: '10:05', val: 67 }]"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": project, "template": "data-viz"})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{project}' from data-viz scaffold. Write src/App.tsx."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write",
        chosen_args={"path": "src/App.tsx", "content": f"{hardcoded}\n// use hardcoded data with ResponsiveContainer + ChartCard"},
        rejected_fn="file_write",
        rejected_args={"path": "src/App.tsx", "content": "useEffect(() => { fetch('/api/metrics').then(r => r.json()).then(setData) }, [])"},
        source_bug="DVF03-no-fetch",
        note=f"no-fetch-{i+1}: use hardcoded sample data not fetch('/api/...')",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# DVF04: StatRow for KPIs — when dashboard has summary stats, use StatRow
# ─────────────────────────────────────────────────────────────────────────────
for i, (project, prompt) in enumerate([
    ("kpi-dashboard", "Build a KPI dashboard with total revenue, orders count, and average order value"),
    ("marketing-dash", "Build a marketing dashboard with impressions, clicks, and CTR metrics"),
    ("store-analytics", "Build a store analytics dashboard with daily sales, active users, and conversion rate"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": project, "template": "data-viz"})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{project}' from data-viz scaffold. Write src/App.tsx."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write",
        chosen_args={"path": "src/App.tsx", "content": "import StatRow from './components/StatRow'\n// <StatRow stats={[{label:'Revenue', value:'$42K'}, ...]} />"},
        rejected_fn="file_write",
        rejected_args={"path": "src/App.tsx", "content": "<div className='kpis'><div>Revenue: $42K</div><div>Orders: 128</div></div>"},
        source_bug="DVF04-statrow",
        note=f"statrow-{i+1}: KPI summary must use StatRow component not raw divs",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# DVF05: data-viz template — project_init must include template="data-viz"
# ─────────────────────────────────────────────────────────────────────────────
for i, (prompt, name) in enumerate([
    ("Build a bar chart for monthly expenses", "expense-chart"),
    ("Build an area chart dashboard for server metrics", "server-metrics"),
    ("Build a pie chart showing sales by region", "regional-sales"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="project_init",
        chosen_args={"name": name, "template": "data-viz"},
        rejected_fn="project_init",
        rejected_args={"name": name},
        source_bug="DVF05-template-param",
        note=f"template-{i+1}: project_init must include template='data-viz'",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# DVF06: Undertow before deliver — after successful build → undertow, not message_result
# ─────────────────────────────────────────────────────────────────────────────
for i, (project, prompt) in enumerate([
    ("sales-chart", "Build a sales bar chart dashboard"),
    ("traffic-viz", "Build a traffic analytics area chart"),
    ("crypto-tracker", "Build a crypto portfolio line chart"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": project, "template": "data-viz"})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{project}' from data-viz scaffold. Write src/App.tsx."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "// complete dashboard"})}}
        ]},
        {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c3", "type": "function", "function": {
                "name": "shell_exec", "arguments": json.dumps({"command": f"cd deliverables/{project} && npm run build"})}}
        ]},
        {"role": "tool", "tool_call_id": "c3",
         "content": "[shell_exec] Build succeeded. dist/ ready."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="undertow",
        chosen_args={"path": f"deliverables/{project}/dist/index.html"},
        rejected_fn="message_result",
        rejected_args={"text": f"{project} built and ready."},
        source_bug="DVF06-undertow",
        note=f"undertow-{i+1}: after build success → undertow before message_result",
    ))


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
OUT_PATH = Path("workspace/training_data/dataviz_dpo_v1.jsonl")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

with open(OUT_PATH, "w") as f:
    for p in PAIRS:
        f.write(json.dumps(p) + "\n")

counts = {
    "chartcard": sum(1 for p in PAIRS if "DVF01" in p["source_bug"]),
    "responsive": sum(1 for p in PAIRS if "DVF02" in p["source_bug"]),
    "no-fetch": sum(1 for p in PAIRS if "DVF03" in p["source_bug"]),
    "statrow": sum(1 for p in PAIRS if "DVF04" in p["source_bug"]),
    "template": sum(1 for p in PAIRS if "DVF05" in p["source_bug"]),
    "undertow": sum(1 for p in PAIRS if "DVF06" in p["source_bug"]),
}
print(f"\n=== DATAVIZ DPO v1 SUMMARY ===")
print(f"  Total pairs: {len(PAIRS)}")
print(f"  File: {OUT_PATH}")
for k, v in counts.items():
    print(f"  {k}: {v}")
print(f"\nTo train (after SFT + merge):")
print(f"  python training/merge_adapter.py --base google/gemma-4-e4b-it \\")
print(f"    --adapter models/gemma-4-e4b-tsunami-dataviz-v1 \\")
print(f"    --output models/gemma-4-e4b-tsunami-dataviz-v1-merged")
print(f"  python training/train_dpo.py \\")
print(f"    --base-model models/gemma-4-e4b-tsunami-dataviz-v1-merged \\")
print(f"    --data workspace/training_data/dataviz_dpo_v1.jsonl \\")
print(f"    --output models/gemma-4-e4b-tsunami-dataviz-v2 \\")
print(f"    --epochs 1 --lora-r 16 --lr 5e-6 --beta 0.1")
