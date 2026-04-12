#!/usr/bin/env python3
"""Eval pyramid for the dashboard-v1 adapter.

L1 (routing): does "admin dashboard / management dashboard" → dashboard-v1?
L2 (scaffold): does project_init use template="dashboard" + file_write imports Layout/StatCard/DataTable?
L3 (error recovery): does model recover from raw aside/div/table → scaffold components?
L4 (hack-free): correct template, Layout, StatCard, DataTable, undertow, App.tsx only?

Usage:
  /usr/bin/python3 training/eval_dashboard.py --endpoint http://localhost:8090 --adapter dashboard-v1 --quick
"""
import argparse, json, sys, urllib.request, urllib.error, time
from datetime import datetime
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--endpoint", default="http://localhost:8090")
parser.add_argument("--adapter",  default="dashboard-v1")
parser.add_argument("--quick",    action="store_true")
parser.add_argument("--verbose",  action="store_true")
parser.add_argument("--out-dir",  default="workspace/training_data")
args = parser.parse_args()

BASE    = args.endpoint.rstrip("/")
ADAPTER = args.adapter

SYSTEM = (
    "You are Tsunami. You are the wave. You build apps by calling tools.\n\n"
    "DASHBOARD PIPELINE:\n"
    "1. project_init(name, template='dashboard')\n"
    "2. file_write(src/App.tsx) — import Layout, StatCard, ChartCard, DataTable from './components'\n"
    "3. shell_exec — npm run build\n"
    "4. IF ERROR: fix directly\n"
    "5. undertow — QA before delivery\n"
    "6. message_result — land the wave\n\n"
    "DASHBOARD RULES:\n"
    "- ALWAYS template='dashboard' in project_init (NOT react-app, NOT dataviz)\n"
    "- ALWAYS use <Layout title navItems activeNav onNav> for the page shell\n"
    "- ALWAYS use <StatCard label value change trend icon /> for metric tiles\n"
    "- ALWAYS use <DataTable columns rows /> for tabular data\n"
    "- NEVER use raw <aside>, <sidebar div>, or layout-less wrapper\n"
    "- NEVER use raw <div className='stat'> or <span> for metrics\n"
    "- NEVER use raw <table> or <ul> for data\n"
    "- NEVER skip undertow() before message_result\n"
    "- NEVER write main.tsx, vite.config.ts, or index.html (scaffold handles them)\n\n"
    "One tool call per response."
)

TOOLS = [
    {"type": "function", "function": {"name": "project_init", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "template": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "message_result", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "undertow", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": []}}},
]


def chat(messages, max_tokens=600):
    payload = {
        "model": ADAPTER,
        "messages": messages,
        "tools": TOOLS,
        "max_tokens": max_tokens,
        "temperature": 0.1,
        "stream": False,
    }
    req = urllib.request.Request(
        f"{BASE}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        return {"error": str(e)}


def get_tool(resp):
    try:
        msg = resp["choices"][0]["message"]
        if msg.get("tool_calls"):
            tc = msg["tool_calls"][0]
            return tc["function"]["name"], json.loads(tc["function"]["arguments"])
        return None, {}
    except (KeyError, IndexError, json.JSONDecodeError):
        return None, {}


results = []


def run_test(tid, messages, check_fn, desc):
    resp = chat(messages)
    if "error" in resp:
        results.append({"id": tid, "pass": False, "desc": desc, "error": resp["error"]})
        return False, None, {}
    name, a = get_tool(resp)
    passed, note = check_fn(name, a, resp)
    results.append({"id": tid, "pass": passed, "desc": desc, "tool": name, "args": a, "note": note})
    if args.verbose:
        print(f"  {tid}: {'✓' if passed else '✗'} {note}")
    return passed, name, a


def u(t):    return {"role": "user",      "content": t}
def sys_m(): return {"role": "system",    "content": SYSTEM}
def tc_msg(name, **kwargs):
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": f"ev_{name}", "type": "function", "function": {"name": name, "arguments": json.dumps(kwargs)}}
    ]}
def tr_msg(name, result):
    return {"role": "tool", "tool_call_id": f"ev_{name}", "name": name, "content": result}


# ════════════════════════════════════════════════════════════════
# L1: Routing — does the model call project_init with template=dashboard?
# ════════════════════════════════════════════════════════════════
print("L1: Routing...")

L1_TESTS = [
    ("DAT01", "Build an admin dashboard to manage my e-commerce orders with stats and an orders table.",
     "ecommerce admin routing"),
    ("DAT02", "Create a user management admin panel with headcount stats and a users table.",
     "user admin routing"),
    ("DAT03", "Build a CRM dashboard with deal stats and a contacts table.",
     "CRM dashboard routing"),
    ("DAT04", "Make an inventory management dashboard with stock stats and a products table.",
     "inventory dashboard routing"),
    ("DAT05", "Build an HR dashboard showing headcount, open roles, and a hiring pipeline table.",
     "HR dashboard routing"),
    ("DAT06", "Create a server monitoring dashboard with uptime stats and an alerts table.",
     "server monitoring routing"),
]
if args.quick:
    L1_TESTS = L1_TESTS[:3]

for tid, prompt, desc in L1_TESTS:
    def check_l1(name, a, resp):
        if name != "project_init":
            return False, f"got {name!r}, want project_init"
        tmpl = a.get("template", "")
        if tmpl != "dashboard":
            return False, f"template={tmpl!r}, want 'dashboard'"
        return True, f"project_init(template='dashboard', name={a.get('name')!r})"
    run_test(tid, [sys_m(), u(prompt)], check_l1, desc)

# ════════════════════════════════════════════════════════════════
# L2: Scaffold — does file_write use Layout/StatCard/DataTable?
# ════════════════════════════════════════════════════════════════
print("L2: Scaffold...")

L2_TESTS = [
    ("DAS01",
     [sys_m(), u("Build an e-commerce analytics dashboard with sales stats and an orders table."),
      tc_msg("project_init", name="ecommerce-analytics", template="dashboard"),
      tr_msg("project_init", "Scaffolded with template=dashboard. Layout, StatCard, ChartCard, DataTable available in ./components.")],
     "Layout import in file_write",
     lambda n, a, r: (
         n == "file_write" and
         "<Layout" in a.get("content", "") and
         "from './components'" in a.get("content", ""),
         f"file_write with {'Layout+components' if n=='file_write' else n!r}",
     )
    ),
    ("DAS02",
     [sys_m(), u("Build a user management dashboard with active users stats and a users table."),
      tc_msg("project_init", name="user-admin", template="dashboard"),
      tr_msg("project_init", "Scaffolded with template=dashboard. Layout, StatCard, DataTable available.")],
     "StatCard in file_write",
     lambda n, a, r: (
         n == "file_write" and
         "<StatCard" in a.get("content", "") and
         "<DataTable" in a.get("content", ""),
         f"file_write with {'StatCard+DataTable' if n=='file_write' else n!r}",
     )
    ),
    ("DAS03",
     [sys_m(), u("Build an HR dashboard with headcount stats and a job openings table."),
      tc_msg("project_init", name="hr-dashboard", template="dashboard"),
      tr_msg("project_init", "Scaffolded with template=dashboard.")],
     "no raw <table> in file_write",
     lambda n, a, r: (
         n == "file_write" and
         "<DataTable" in a.get("content", "") and
         "<table" not in a.get("content", ""),
         f"file_write: DataTable={'<DataTable' in a.get('content','')!r} raw-table={'<table' in a.get('content','')!r}",
     )
    ),
]
if args.quick:
    L2_TESTS = L2_TESTS[:2]

for tid, messages, desc, check_fn in L2_TESTS:
    run_test(tid, messages, check_fn, desc)

# ════════════════════════════════════════════════════════════════
# L3: Error Recovery
# ════════════════════════════════════════════════════════════════
print("L3: Error recovery...")

# DAER01: Raw aside → should warn / re-write with Layout
DAER01_MSGS = [
    sys_m(),
    u("Build an inventory management dashboard with stock stats and a products table."),
    tc_msg("project_init", name="inventory", template="dashboard"),
    tr_msg("project_init", "Scaffolded with template=dashboard."),
    tc_msg("file_write", path="src/App.tsx", content=(
        "import { StatCard, DataTable } from './components'\n"
        "export default function App() {\n"
        "  return (\n"
        "    <div className='flex'>\n"
        "      <aside className='w-64 bg-gray-800 h-screen p-4'>\n"
        "        <h2>Inventory</h2>\n"
        "      </aside>\n"
        "      <main className='flex-1 p-6'>\n"
        "        <StatCard label='Products' value='342' trend='up' />\n"
        "        <DataTable columns={[]} rows={[]} />\n"
        "      </main>\n"
        "    </div>\n"
        "  )\n"
        "}"
    )),
    tr_msg("file_write", "Written: src/App.tsx"),
    tc_msg("shell_exec", command="cd inventory && npm run build"),
    tr_msg("shell_exec", "Warning: Raw <aside> detected. Use <Layout> from './components' for sidebar navigation."),
]

def check_daer01(name, a, resp):
    # Model should respond to the warning by rewriting with Layout
    if name == "file_write":
        content = a.get("content", "")
        if "<Layout" in content:
            return True, "file_write with <Layout> (corrected raw aside)"
        return False, f"file_write but no <Layout> in content (still using raw aside)"
    if name == "file_edit":
        new_text = a.get("new_text", "")
        if "<Layout" in new_text:
            return True, "file_edit adding <Layout>"
        return False, f"file_edit but no <Layout> in new_text"
    return False, f"got {name!r}, want file_write or file_edit with <Layout>"

run_test("DAER01", DAER01_MSGS, check_daer01, "raw aside warning → rewrite with <Layout>")

# DAER02: Raw metric div → should rewrite with StatCard
DAER02_MSGS = [
    sys_m(),
    u("Build a CRM dashboard with deal stats and a contacts table."),
    tc_msg("project_init", name="crm", template="dashboard"),
    tr_msg("project_init", "Scaffolded with template=dashboard."),
    tc_msg("file_write", path="src/App.tsx", content=(
        "import { Layout, DataTable } from './components'\n"
        "export default function App() {\n"
        "  return (\n"
        "    <Layout title='CRM' navItems={[]} activeNav='' onNav={()=>{}}>\n"
        "      <div className='grid grid-cols-3 gap-4'>\n"
        "        <div className='bg-white p-4 rounded shadow'>\n"
        "          <div className='text-sm text-gray-500'>Open Deals</div>\n"
        "          <div className='text-2xl font-bold'>34</div>\n"
        "        </div>\n"
        "      </div>\n"
        "      <DataTable columns={[]} rows={[]} />\n"
        "    </Layout>\n"
        "  )\n"
        "}"
    )),
    tr_msg("file_write", "Written: src/App.tsx"),
    tc_msg("shell_exec", command="cd crm && npm run build"),
    tr_msg("shell_exec", "Warning: Raw metric div detected. Use <StatCard> from './components' for KPI tiles."),
]

def check_daer02(name, a, resp):
    if name in ("file_write", "file_edit"):
        content = a.get("content", a.get("new_text", ""))
        if "<StatCard" in content:
            return True, f"{name} with <StatCard> (corrected raw div)"
        return False, f"{name} but no <StatCard>"
    return False, f"got {name!r}, want file_write/edit with <StatCard>"

run_test("DAER02", DAER02_MSGS, check_daer02, "raw metric div warning → rewrite with <StatCard>")

# DAER03: Raw <table> → should rewrite with DataTable
DAER03_MSGS = [
    sys_m(),
    u("Build a support ticket dashboard with ticket stats and an open tickets table."),
    tc_msg("project_init", name="support", template="dashboard"),
    tr_msg("project_init", "Scaffolded with template=dashboard."),
    tc_msg("file_write", path="src/App.tsx", content=(
        "import { Layout, StatCard } from './components'\n"
        "const TICKETS = [{id:'#8042',subject:'Login error',priority:'High'}]\n"
        "export default function App() {\n"
        "  return (\n"
        "    <Layout title='Support' navItems={[]} activeNav='' onNav={()=>{}}>\n"
        "      <StatCard label='Open' value='42' trend='down' />\n"
        "      <table className='w-full mt-4'>\n"
        "        <thead><tr><th>ID</th><th>Subject</th><th>Priority</th></tr></thead>\n"
        "        <tbody>{TICKETS.map(t=>(<tr key={t.id}><td>{t.id}</td><td>{t.subject}</td><td>{t.priority}</td></tr>))}</tbody>\n"
        "      </table>\n"
        "    </Layout>\n"
        "  )\n"
        "}"
    )),
    tr_msg("file_write", "Written: src/App.tsx"),
    tc_msg("shell_exec", command="cd support && npm run build"),
    tr_msg("shell_exec", "Warning: Raw <table> detected. Use <DataTable columns rows /> from './components'."),
]

def check_daer03(name, a, resp):
    if name in ("file_write", "file_edit"):
        content = a.get("content", a.get("new_text", ""))
        if "<DataTable" in content and "<table" not in content:
            return True, f"{name} with <DataTable> (corrected raw table)"
        if "<DataTable" in content:
            return False, f"{name}: <DataTable> present but raw <table> still there"
        return False, f"{name} but no <DataTable>"
    return False, f"got {name!r}, want file_write/edit with <DataTable>"

run_test("DAER03", DAER03_MSGS, check_daer03, "raw <table> warning → rewrite with <DataTable>")

if args.quick:
    pass  # L3 already minimal

# ════════════════════════════════════════════════════════════════
# L4: Hack-Free / Fault probes
# ════════════════════════════════════════════════════════════════
print("L4: Fault probes...")

# DAF01 proxy: does "admin dashboard" prompt → template=dashboard (not react-app)?
def check_daf01(name, a, resp):
    if name != "project_init":
        return False, f"got {name!r}"
    tmpl = a.get("template", "")
    if tmpl == "dashboard":
        return True, "template='dashboard' ✓"
    return False, f"template={tmpl!r} (should be 'dashboard')"

run_test("DAF01", [sys_m(), u("Build an admin dashboard to manage team projects with stats and a table.")],
         check_daf01, "template=dashboard not react-app")

# DAF02 proxy: does file_write include <Layout>?
DAF02_MSGS = [
    sys_m(),
    u("Build a sales management dashboard with deal stats and a pipeline table."),
    tc_msg("project_init", name="sales-mgmt", template="dashboard"),
    tr_msg("project_init", "Scaffolded with template=dashboard. Layout available in ./components."),
]
def check_daf02(name, a, resp):
    if name != "file_write":
        return False, f"got {name!r}, want file_write"
    content = a.get("content", "")
    if "<Layout" in content:
        return True, "<Layout> used ✓"
    return False, "no <Layout> in file_write (used raw aside or none)"

run_test("DAF02", DAF02_MSGS, check_daf02, "file_write uses <Layout>")

# DAF03 proxy: does file_write include <StatCard>?
DAF03_MSGS = [
    sys_m(),
    u("Build a marketing analytics dashboard with campaign stats and a campaigns table."),
    tc_msg("project_init", name="marketing", template="dashboard"),
    tr_msg("project_init", "Scaffolded with template=dashboard."),
]
def check_daf03(name, a, resp):
    if name != "file_write":
        return False, f"got {name!r}, want file_write"
    content = a.get("content", "")
    if "<StatCard" in content:
        return True, "<StatCard> used ✓"
    return False, "no <StatCard> in file_write (used raw div)"

run_test("DAF03", DAF03_MSGS, check_daf03, "file_write uses <StatCard>")

# DAF04 proxy: does file_write include <DataTable> (not raw <table>)?
DAF04_MSGS = [
    sys_m(),
    u("Build a HR admin dashboard with headcount stats and an employees table."),
    tc_msg("project_init", name="hr-admin", template="dashboard"),
    tr_msg("project_init", "Scaffolded with template=dashboard."),
]
def check_daf04(name, a, resp):
    if name != "file_write":
        return False, f"got {name!r}, want file_write"
    content = a.get("content", "")
    has_dt = "<DataTable" in content
    has_raw = "<table" in content
    if has_dt and not has_raw:
        return True, "<DataTable> used (no raw <table>) ✓"
    if has_raw:
        return False, "raw <table> in output (should use <DataTable>)"
    return False, "no <DataTable> in file_write"

run_test("DAF04", DAF04_MSGS, check_daf04, "file_write uses <DataTable> not raw <table>")

# DAF05: does model call undertow before message_result?
DAF05_MSGS = [
    sys_m(),
    u("Build a cloud billing dashboard with cost stats and a services table."),
    tc_msg("project_init", name="cloud-billing", template="dashboard"),
    tr_msg("project_init", "Scaffolded with template=dashboard."),
    tc_msg("file_write", path="src/App.tsx", content=(
        "import { useState } from 'react'\n"
        "import { Layout, StatCard, DataTable } from './components'\n"
        "const NAV=[{label:'Billing',href:'#'}]\n"
        "export default function App(){const [a,sa]=useState('Billing');return(<Layout title='Billing' navItems={NAV} activeNav={a} onNav={sa}><StatCard label='Cost' value='$4,200' trend='down' /><DataTable columns={[]} rows={[]} /></Layout>)}"
    )),
    tr_msg("file_write", "Written: src/App.tsx"),
    tc_msg("shell_exec", command="cd cloud-billing && npm run build"),
    tr_msg("shell_exec", "Build successful. App running at http://localhost:5173"),
]
def check_daf05(name, a, resp):
    if name == "undertow":
        return True, "undertow called before message_result ✓"
    if name == "message_result":
        return False, "message_result before undertow — must screenshot first"
    return False, f"got {name!r}, want undertow"

run_test("DAF05", DAF05_MSGS, check_daf05, "undertow before message_result")

# DAF06: does model only write App.tsx (not main.tsx)?
DAF06_MSGS = [
    sys_m(),
    u("Build a server metrics dashboard with CPU/memory stats and an alerts table."),
    tc_msg("project_init", name="server-metrics", template="dashboard"),
    tr_msg("project_init", "Scaffolded with template=dashboard."),
]
def check_daf06(name, a, resp):
    if name != "file_write":
        return False, f"got {name!r}, want file_write"
    path = a.get("path", "")
    if "App.tsx" in path:
        return True, f"writes App.tsx ✓ (path={path!r})"
    if "main.tsx" in path or "vite.config" in path or "index.html" in path:
        return False, f"writes scaffold file {path!r} (should only write App.tsx)"
    return False, f"unexpected path {path!r}"

run_test("DAF06", DAF06_MSGS, check_daf06, "only writes App.tsx (not main.tsx/vite.config)")


# ════════════════════════════════════════════════════════════════
# Reporting
# ════════════════════════════════════════════════════════════════
layers = {
    "L1 Routing":  [r for r in results if r["id"].startswith("DAT")],
    "L2 Scaffold": [r for r in results if r["id"].startswith("DAS")],
    "L3 Recovery": [r for r in results if r["id"].startswith("DAER")],
    "L4 Hack-Free":[r for r in results if r["id"].startswith("DAF")],
}

POINTS = {"L1 Routing": 5, "L2 Scaffold": 2, "L3 Recovery": 17, "L4 Hack-Free": 10}

now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(f"\n# Dashboard Adapter Eval — {now}")
print(f"**Adapter**: `{ADAPTER}` | **Endpoint**: {BASE}\n")

total_pts, total_max = 0, 0
for layer, tests in layers.items():
    pts = POINTS[layer]
    passed = sum(1 for t in tests)
    passed_count = sum(1 for t in tests if t["pass"])
    earned = sum(pts for t in tests if t["pass"])
    max_pts = len(tests) * pts
    total_pts += earned; total_max += max_pts
    print(f"## {layer}")
    print(f"| ID | Pass | Tool | Note |")
    print(f"|----|------|------|------|")
    for t in tests:
        mark = "✓" if t["pass"] else "✗"
        print(f"| {t['id']} | {mark} | `{t.get('tool','NONE')}` | {t.get('note','')[:60]} |")
    pct = int(100*earned/max_pts) if max_pts else 0
    print(f"\n**{layer}**: {passed_count}/{len(tests)} — {earned}/{max_pts} pts ({pct}%)\n")

total_pct = int(100*total_pts/total_max) if total_max else 0
print(f"\n## TOTAL: {total_pts}/{total_max} ({total_pct}%)")

# Signal analysis
failures = [r for r in results if not r["pass"]]
if failures:
    print("\n## Training Signals")
    for r in failures:
        print(f"- {r['id']} {r['desc']}: got `{r.get('tool','NONE')}` — {r.get('note','')}")

# Save JSON report
out_dir = Path(args.out_dir)
out_dir.mkdir(parents=True, exist_ok=True)
ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
json_path = out_dir / f"eval_report_dashboard_{ts}.json"
with open(json_path, "w") as f:
    json.dump({"adapter": ADAPTER, "endpoint": BASE, "timestamp": ts,
               "total_pts": total_pts, "total_max": total_max, "pct": total_pct,
               "results": results}, f, indent=2)
print(f"\nReport: {json_path}")
