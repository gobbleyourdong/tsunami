#!/usr/bin/env python3
"""build_curator_dpo_v6.py -- DPO v6 for builder adapter.

12 pairs targeting 4 uncovered HF scenarios from eval_hack_free.py:
  HF06: Conversation -> message_chat (not message_info)
  HF07: After scaffold with imports -> file_write components (not message_result)
  HF08: After search results -> build (not search again)
  HF10: After build success -> undertow BEFORE message_result

These complement DPO v4 (HF01/02/04/05) and DPO v5 (ER02/03/05/06).
"""
import json, os, sys
from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/curator_dpo_v6.jsonl"
TODAY = "2026-04-12"


def tok_apply(tok, msgs):
    result = tok.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    return result if isinstance(result, str) else tok.decode(result)

def s():
    return {"role": "system", "content": SYSTEM_TEXT}

def u(t):
    return {"role": "user", "content": t}

def tc(tool_name, **kw):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"type": "function", "function": {"name": tool_name, "arguments": kw}}
    ]}

def tr(tool_name, content):
    return {"role": "tool", "name": tool_name, "content": content}

def pair(prompt_msgs, chosen_msgs, rejected_msgs, fault_id, note):
    return {
        "prompt": prompt_msgs,
        "chosen": chosen_msgs,
        "rejected": rejected_msgs,
        "source_bug": fault_id,
        "note": note,
        "images": [],
        "date": TODAY,
    }


# ── HF06: Conversation -> message_chat (not message_info) ────────────────────

def hf06_pairs():
    """Greeting/question turns -> message_chat with done=True, not message_info."""
    return [
        # 1. Simple greeting -> message_chat
        pair([s(), u("Hello! What can you build?")],
             [tc("message_chat", text="I can build React apps, dashboards, games, REST APIs, Chrome extensions, landing pages, and more. What would you like to make?", done=True)],
             [tc("message_info", text="I can build apps...")],
             "HF06",
             "build: greeting -> message_chat(done=True), not message_info"),

        # 2. General question -> message_chat
        pair([s(), u("Can you explain how React hooks work?")],
             [tc("message_chat", text="React hooks let you use state and lifecycle in function components. useState holds values, useEffect runs after renders, useCallback memoizes functions. What would you like to build with them?", done=True)],
             [tc("message_info", text="React hooks are...")],
             "HF06b",
             "build: knowledge question -> message_chat, not message_info"),

        # 3. Follow-up on existing app (not a build request) -> message_chat
        pair([s(), u("What's the difference between useState and useReducer?")],
             [tc("message_chat", text="useState is for simple values, useReducer for complex state with multiple actions. useReducer is like a mini Redux. Want me to show you both in a demo app?", done=True)],
             [tc("message_info", text="useState vs useReducer...")],
             "HF06c",
             "build: clarification question -> message_chat, not message_info"),
    ]


# ── HF07: After scaffold with components -> file_write App.tsx with imports ───

def hf07_pairs():
    """After scaffold, write App.tsx that imports scaffold components properly."""
    dash_scaffold = tr("project_init",
        "[project_init] Created 'analytics-dashboard' with dashboard scaffold.\n"
        "Pre-built components: Layout, StatCard, ChartCard, DataTable, Modal, Toast.\n"
        "src/App.tsx is a stub — replace it with your app.")
    full_scaffold = tr("project_init",
        "[project_init] Created 'inventory-app' with dashboard scaffold.\n"
        "Pre-built components: Layout, StatCard, DataTable, Modal, Toast.\n"
        "src/App.tsx is a stub — replace it with your app.")

    return [
        # 1. Dashboard scaffold -> file_write App.tsx importing Layout+StatCard+ChartCard
        pair([s(), u("Build a sales analytics dashboard with KPI cards and a revenue chart."),
              tc("project_init", name="analytics-dashboard", template="dashboard"),
              dash_scaffold],
             [tc("file_write", path="deliverables/analytics-dashboard/src/App.tsx",
                 content="import { Layout } from './components/Layout'\nimport { StatCard } from './components/StatCard'\nimport { ChartCard } from './components/ChartCard'\n// ... app code using scaffold components")],
             [tc("message_result", text="Dashboard created!")],
             "HF07",
             "build: after dashboard scaffold -> file_write App.tsx with Layout/StatCard/ChartCard imports"),

        # 2. Dashboard scaffold -> write App.tsx (not file_read to explore first)
        pair([s(), u("Build an inventory management dashboard."),
              tc("project_init", name="inventory-app", template="dashboard"),
              full_scaffold],
             [tc("file_write", path="deliverables/inventory-app/src/App.tsx",
                 content="import { Layout } from './components/Layout'\nimport { StatCard } from './components/StatCard'\nimport { DataTable } from './components/DataTable'\n// inventory app")],
             [tc("file_read", path="deliverables/inventory-app/src/components/Layout.tsx")],
             "HF07b",
             "build: after dashboard scaffold -> file_write directly (not file_read to explore)"),

        # 3. Generic scaffold -> write App.tsx with React imports (not deliver empty stub)
        pair([s(), u("Build a weather tracker with 5-day forecast."),
              tc("project_init", name="weather-tracker"),
              tr("project_init", "[project_init] Created 'weather-tracker'. src/App.tsx is a stub — replace it with your app.")],
             [tc("file_write", path="deliverables/weather-tracker/src/App.tsx",
                 content="import { useState, useEffect } from 'react'\n// weather tracker app with forecast state")],
             [tc("message_result", text="Weather tracker ready!")],
             "HF07c",
             "build: after scaffold -> file_write App.tsx (not deliver stub immediately)"),
    ]


# ── HF08: After search results -> build (not search again) ───────────────────

def hf08_pairs():
    """After search returns results, use them to build (don't search the same query again)."""
    return [
        # 1. After research results -> project_init to start building
        pair([s(), u("Research React state management and build a demo app."),
              tc("search_web", query="react state management 2026"),
              tr("search_web", "Results: 1. Zustand (lightweight, 3KB), 2. Jotai (atomic state, React Suspense), 3. Redux Toolkit (full-featured, best for large apps). Zustand is most popular for mid-size apps in 2026.")],
             [tc("project_init", name="state-management-demo")],
             [tc("search_web", query="react state management libraries comparison")],
             "HF08",
             "build: after search results -> project_init to build (not search again)"),

        # 2. After search with good results -> use the top result's API (not search for more)
        pair([s(), u("Build a currency converter using a live exchange rate API."),
              tc("search_web", query="free currency exchange rate API 2026"),
              tr("search_web", "Results: 1. exchangerate-api.com (free tier, no key needed), 2. open.er-api.com (open, CORS friendly), 3. fixer.io (requires key). Best free option: open.er-api.com/v6/latest/USD")],
             [tc("project_init", name="currency-converter")],
             [tc("search_web", query="best free currency API no signup")],
             "HF08b",
             "build: after search with specific API result -> project_init (not another search)"),

        # 3. After research -> write code using what was found (not re-search)
        pair([s(), u("Build a Notion-inspired note editor — look up what makes Notion's editor distinctive."),
              tc("search_web", query="Notion editor distinctive features block-based editing"),
              tr("search_web", "Notion uses block-based editing: / to insert blocks (text/heading/todo/toggle/code), drag handles to reorder, inline @mentions. Key UX: blocks snap to position, hover reveals handle."),
              tc("project_init", name="notion-editor"),
              tr("project_init", "[project_init] Created 'notion-editor'. Write src/App.tsx.")],
             [tc("file_write", path="deliverables/notion-editor/src/App.tsx",
                 content="// Block-based editor inspired by Notion\n// Blocks: text, heading, todo, toggle — type / to insert\nimport { useState } from 'react'\n// ... editor implementation")],
             [tc("search_web", query="Notion editor block types API")],
             "HF08c",
             "build: after research + scaffold -> file_write (not more searching)"),
    ]


# ── HF10: undertow BEFORE message_result ─────────────────────────────────────

def hf10_pairs():
    """After build success, always call undertow before message_result."""
    def build_prefix(app_name, content="// app"):
        return [
            s(),
            u(f"Build a {app_name}."),
            tc("project_init", name=app_name.replace(" ", "-")),
            tr("project_init", f"[project_init] Created '{app_name.replace(' ', '-')}'. Write src/App.tsx."),
            tc("file_write", path=f"deliverables/{app_name.replace(' ', '-')}/src/App.tsx",
               content=f"import {{ useState }} from 'react'\n// {app_name}\nexport default function App() {{ return <div>{app_name}</div> }}"),
            tr("file_write", "Written."),
            tc("shell_exec", command=f"cd deliverables/{app_name.replace(' ', '-')} && npm run build"),
            tr("shell_exec", "[shell_exec] Build successful. dist/index.html ready."),
        ]

    return [
        # 1. After build success -> undertow (not message_result)
        pair(build_prefix("timer app"),
             [tc("undertow", url="http://localhost:5173")],
             [tc("message_result", text="Timer app ready!")],
             "HF10",
             "build: after successful build -> undertow BEFORE message_result"),

        # 2. After build success -> undertow (not another shell_exec)
        pair(build_prefix("markdown editor"),
             [tc("undertow", url="http://localhost:5173")],
             [tc("shell_exec", command="cd deliverables/markdown-editor && npm run build")],
             "HF10b",
             "build: after successful build -> undertow (not another build)"),

        # 3. After undertow screenshot -> message_result (not loop back)
        pair(build_prefix("calculator") + [
                tc("undertow", url="http://localhost:5173"),
                tr("undertow", "Screenshot: calculator with number pad, operators (+,-,×,÷), display showing 0."),
             ],
             [tc("message_result", text="Calculator app with number pad and basic operations. Click digits and operators, = to calculate.")],
             [tc("undertow", url="http://localhost:5173")],
             "HF10c",
             "build: after undertow with screenshot -> message_result (not another undertow)"),
    ]


def main():
    print("Loading tokenizer...")
    tok = AutoTokenizer.from_pretrained(MODEL)
    print("Tokenizer loaded.")

    all_pairs = []
    for fn in [hf06_pairs, hf07_pairs, hf08_pairs, hf10_pairs]:
        pairs = fn()
        for p in pairs:
            p["prompt"] = tok_apply(tok, p["prompt"])
            p["chosen"] = tok_apply(tok, p["chosen"])
            p["rejected"] = tok_apply(tok, p["rejected"])
        all_pairs.extend(pairs)
        print(f"  {fn.__name__}: {len(pairs)} pairs")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for p in all_pairs:
            f.write(json.dumps(p) + "\n")

    print(f"\nTotal: {len(all_pairs)} DPO pairs")
    print(f"Wrote to {OUT_PATH}")

    # Combine with v5
    prev_path = "workspace/training_data/curator_dpo_combined_v5.jsonl"
    combined_path = "workspace/training_data/curator_dpo_combined_v6.jsonl"
    prev = []
    if os.path.exists(prev_path):
        with open(prev_path) as f:
            prev = [json.loads(l) for l in f if l.strip()]
    combined = prev + all_pairs
    with open(combined_path, "w") as f:
        for p in combined:
            f.write(json.dumps(p) + "\n")
    print(f"Combined_v6: {len(combined)} pairs -> {combined_path}")


if __name__ == "__main__":
    main()
