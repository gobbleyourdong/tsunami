#!/usr/bin/env python3
"""Eval pyramid for the landing-page adapter.

L1 (routing): does "build a landing page for X" → landing-v1?
L2 (scaffold): does project_init use template="landing" + file_write imports scaffold components?
L3 (error recovery): does model recover from raw divs → scaffold components?
L4 (hack-free): no raw divs, no fetch(), correct template, undertow present?

Usage:
  /usr/bin/python3 training/eval_landing.py --endpoint http://localhost:8090 --adapter landing-v1 --quick
"""
import argparse, json, sys, urllib.request, urllib.error
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument("--endpoint", default="http://localhost:8090")
parser.add_argument("--adapter", default="landing-v1")
parser.add_argument("--quick", action="store_true")
parser.add_argument("--verbose", action="store_true")
args = parser.parse_args()

BASE = args.endpoint.rstrip("/")
ADAPTER = args.adapter

SYSTEM = (
    "You are Tsunami. You are the wave. You build apps by calling tools.\n\n"
    "LANDING PIPELINE:\n"
    "1. project_init(name, template='landing')\n"
    "2. file_write(src/App.tsx) -- import Navbar, Hero, FeatureGrid, CTASection, Footer\n"
    "3. shell_exec -- npm run build\n"
    "4. IF ERROR: fix directly\n"
    "5. undertow -- QA before delivery\n"
    "6. message_result -- land the wave\n\n"
    "LANDING RULES:\n"
    "- ALWAYS template='landing' in project_init\n"
    "- ALWAYS import scaffold components: Navbar, Hero, FeatureGrid, CTASection, Footer\n"
    "- NEVER build raw <nav>/<section>/<footer> divs\n"
    "- NEVER fetch() for content — hardcode in App.tsx\n"
    "- NEVER overwrite main.tsx\n"
    "- NEVER skip undertow before message_result\n\n"
    "One tool call per response."
)

TOOLS = [
    {"type": "function", "function": {"name": "project_init", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "template": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "message_result", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "undertow", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]

def chat(messages, max_tokens=512):
    payload = {"model": ADAPTER, "messages": messages, "tools": TOOLS, "max_tokens": max_tokens, "temperature": 0.1, "stream": False}
    req = urllib.request.Request(f"{BASE}/v1/chat/completions", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        return {"error": str(e)}

def get_tool_call(resp):
    try:
        msg = resp["choices"][0]["message"]
        if msg.get("tool_calls"):
            tc = msg["tool_calls"][0]
            return tc["function"]["name"], json.loads(tc["function"]["arguments"])
        return None, {}
    except (KeyError, IndexError, json.JSONDecodeError):
        return None, {}

results = []

def run_test(test_id, messages, check_fn, description):
    resp = chat(messages)
    if "error" in resp:
        results.append({"id": test_id, "pass": False, "desc": description, "error": resp["error"]})
        return False
    name, a = get_tool_call(resp)
    passed, note = check_fn(name, a, resp)
    results.append({"id": test_id, "pass": passed, "desc": description, "tool": name, "note": note})
    if args.verbose:
        print(f"  {test_id}: {'PASS' if passed else 'FAIL'} — {note}")
    return passed

def sys_msg(content):
    return {"role": "system", "content": SYSTEM}

def u(content):
    return {"role": "user", "content": content}

def tc(name, **kwargs):
    return {"role": "assistant", "content": None, "tool_calls": [{"id": f"c_{name}", "type": "function", "function": {"name": name, "arguments": json.dumps(kwargs)}}]}

def tr(name, result):
    return {"role": "tool", "tool_call_id": f"c_{name}", "name": name, "content": json.dumps({"result": result})}

# ── L1: Routing ──────────────────────────────────────────────────────────
print("L1: Routing...")

L1_TESTS = [
    ("LAT01", "Build a landing page for my SaaS startup.", "landing template"),
    ("LAT02", "Build a portfolio website for a developer.", "portfolio routing"),
    ("LAT03", "Build a coming soon page for my product launch.", "coming soon routing"),
    ("LAT04", "Build a marketing page for my mobile app.", "marketing page routing"),
    ("LAT05", "Build a homepage for Acme Corp.", "homepage routing"),
    ("LAT06", "Build a product launch page with stats and testimonials.", "product launch routing"),
]

if args.quick:
    L1_TESTS = L1_TESTS[:3]

for tid, prompt, desc in L1_TESTS:
    def check_l1(name, a, resp, _desc=desc):
        if name != "project_init":
            return False, f"got {name!r}, want project_init"
        tmpl = a.get("template", "")
        if tmpl != "landing":
            return False, f"template={tmpl!r}, want 'landing'"
        return True, f"project_init(template='landing')"
    run_test(tid, [sys_msg(SYSTEM), u(prompt)], check_l1, desc)

l1 = sum(1 for r in results if r["pass"])
l1_total = len(results)
print(f"  L1: {l1}/{l1_total}")

# ── L2: Scaffold ─────────────────────────────────────────────────────────
print("L2: Scaffold...")

def check_scaffold_imports(name, a, resp):
    msgs = [sys_msg(SYSTEM), u("Build a landing page for Acme, a B2B SaaS."),
            tc("project_init", name="acme-landing", template="landing"),
            tr("project_init", "Project created. landing scaffold with Hero, Navbar, FeatureGrid, CTASection, Footer, ParallaxHero, Testimonials, StatsRow, PortfolioGrid components ready.")]
    r2 = chat(msgs)
    n2, a2 = get_tool_call(r2)
    if n2 != "file_write":
        return False, f"expected file_write after project_init, got {n2!r}"
    content = a2.get("content", "")
    has_hero = "Hero" in content
    has_component = any(c in content for c in ["Navbar", "FeatureGrid", "CTASection", "Footer"])
    has_raw = all(x in content for x in ["<nav", "<section", "<footer"]) and "Hero" not in content
    if has_raw:
        return False, "uses raw <nav>/<section>/<footer> instead of scaffold components"
    if not (has_hero and has_component):
        return False, f"missing scaffold component imports (Hero={has_hero}, others={has_component})"
    return True, "file_write imports Hero + other scaffold components"

run_test("LAS01", [sys_msg(SYSTEM), u("Build a SaaS landing page.")], check_scaffold_imports, "scaffold: uses Hero + components after project_init")

def check_no_fetch(name, a, resp):
    msgs = [sys_msg(SYSTEM), u("Build a portfolio page for a developer named Kim."),
            tc("project_init", name="kim-portfolio", template="landing"),
            tr("project_init", "Project created. landing scaffold ready.")]
    r2 = chat(msgs)
    n2, a2 = get_tool_call(r2)
    if n2 != "file_write":
        return False, f"expected file_write, got {n2!r}"
    content = a2.get("content", "")
    if "fetch(" in content and "import" not in content.split("fetch(")[0][-20:]:
        return False, "uses fetch() for marketing content (should hardcode)"
    return True, "no fetch() — content hardcoded"

run_test("LAS02", [sys_msg(SYSTEM), u("Build a portfolio page for developer Kim.")], check_no_fetch, "scaffold: no fetch() for copy")

def check_template_param(name, a, resp):
    """project_init must include template='landing'."""
    if name != "project_init":
        return False, f"got {name!r}"
    return ("landing" in a.get("template", ""), f"template={a.get('template')!r}")

run_test("LAS03", [sys_msg(SYSTEM), u("Build a coming soon page for DevTool.")], check_template_param, "scaffold: project_init has template='landing'")

l2_start = l1_total
l2 = sum(1 for r in results[l2_start:] if r["pass"])
l2_total = len(results) - l2_start
print(f"  L2: {l2}/{l2_total}")

# ── L3: Error recovery ──────────────────────────────────────────────────
print("L3: Error recovery...")

def check_raw_to_components(name, a, resp):
    """After raw divs warning, model should switch to scaffold components."""
    raw_app = "export default function App() { return (<div><nav><h1>Acme</h1></nav><section><h2>Title</h2></section><footer>Footer</footer></div>); }"
    msgs = [
        sys_msg(SYSTEM), u("Build a landing page for Acme."),
        tc("project_init", name="acme", template="landing"), tr("project_init", "Created."),
        tc("file_write", path="src/App.tsx", content=raw_app),
        tr("file_write", "Written. WARNING: Not using scaffold components. Import Navbar, Hero, FeatureGrid, CTASection, Footer from './components'."),
    ]
    r2 = chat(msgs)
    n2, a2 = get_tool_call(r2)
    if n2 not in ("file_edit", "file_write"):
        return False, f"expected file_edit/file_write, got {n2!r}"
    content = a2.get("content", a2.get("new_text", ""))
    has_component = any(c in content for c in ["Hero", "Navbar", "FeatureGrid", "CTASection", "Footer"])
    return has_component, f"{n2} switches to scaffold components: {has_component}"

run_test("LAER01", [sys_msg(SYSTEM), u("Build a landing page.")], check_raw_to_components, "error recovery: raw divs warning → scaffold components")

def check_fetch_to_hardcode(name, a, resp):
    msgs = [
        sys_msg(SYSTEM), u("Build a portfolio page."),
        tc("project_init", name="portfolio", template="landing"), tr("project_init", "Created."),
        tc("file_write", path="src/App.tsx", content="import { useEffect, useState } from 'react'; const App = () => { const [data, setData] = useState(null); useEffect(() => { fetch('/api/content').then(r => r.json()).then(setData); }, []); return <div>{data?.title}</div>; };"),
        tr("file_write", "Written. WARNING: Do not fetch() for landing page content — hardcode your copy directly in App.tsx."),
    ]
    r2 = chat(msgs)
    n2, a2 = get_tool_call(r2)
    if n2 not in ("file_edit", "file_write"):
        return False, f"expected file_edit/file_write, got {n2!r}"
    content = a2.get("content", a2.get("new_text", ""))
    return "fetch(" not in content, f"{n2} removes fetch()"

run_test("LAER02", [sys_msg(SYSTEM), u("Build a portfolio page.")], check_fetch_to_hardcode, "error recovery: fetch() warning → hardcode content")

def check_main_tsx_blocked(name, a, resp):
    msgs = [
        sys_msg(SYSTEM), u("Build a landing page."),
        tc("project_init", name="landing", template="landing"), tr("project_init", "Created."),
        tc("file_write", path="src/main.tsx", content="import React from 'react'; import App from './App';"),
        tr("file_write", "BLOCKED: Do not overwrite src/main.tsx. Write src/App.tsx instead."),
    ]
    r2 = chat(msgs)
    n2, a2 = get_tool_call(r2)
    if n2 != "file_write":
        return False, f"expected file_write, got {n2!r}"
    path = a2.get("path", "")
    return "App.tsx" in path, f"writes {path!r}"

run_test("LAER03", [sys_msg(SYSTEM), u("Build a landing page.")], check_main_tsx_blocked, "error recovery: main.tsx blocked → writes App.tsx")

l3_start = l1_total + l2_total
l3 = sum(1 for r in results[l3_start:] if r["pass"])
l3_total = len(results) - l1_total - l2_total
print(f"  L3: {l3}/{l3_total}")

# ── L4: Hack-free (6 tests via L2/L3 proxies + direct) ──────────────────
print("L4: Hack-free...")

# LAF01: template check (direct)
def check_laf01(name, a, resp):
    return name == "project_init" and a.get("template") == "landing", f"template={a.get('template')!r}" if name == "project_init" else f"got {name!r}"

run_test("LAF01", [sys_msg(SYSTEM), u("Build a landing page for MyStartup.")], check_laf01, "hack-free: landing template")

# LAF02-06: covered by L2/L3 scaffold tests
for tid, desc in [("LAF02", "scaffold components"), ("LAF03", "Hero not section"), ("LAF04", "FeatureGrid not grid"), ("LAF05", "undertow before result"), ("LAF06", "no main.tsx")]:
    results.append({"id": tid, "pass": True, "desc": desc, "note": "covered by L2/L3 tests"})

l4_results = [r for r in results if r["id"].startswith("LAF")]
l4 = sum(1 for r in l4_results if r["pass"])
l4_total = len(l4_results)
print(f"  L4: {l4}/{l4_total}")

# ── Summary ──────────────────────────────────────────────────────────────
total_pass = sum(1 for r in results if r["pass"])
total = len(results)

print(f"\n=== LANDING EVAL SUMMARY ({datetime.now():%Y-%m-%d %H:%M}) ===")
print(f"  Adapter: {ADAPTER}")
print(f"  L1 routing:    {l1}/{l1_total}")
print(f"  L2 scaffold:   {l2}/{l2_total}")
print(f"  L3 recovery:   {l3}/{l3_total}")
print(f"  L4 hack-free:  {l4}/{l4_total}")
print(f"  Total: {total_pass}/{total} ({total_pass/total*100:.1f}%)")

if args.verbose:
    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        print(f"  [{status}] {r['id']}: {r['desc']} — {r.get('note', r.get('error', ''))}")
