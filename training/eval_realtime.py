#!/usr/bin/env python3
"""Realtime adapter eval — L1-L4.

Tests the gemma-4-e4b realtime-v1 adapter against WebSocket-specific patterns:
  - server/index.js before App.tsx
  - useWebSocket hook (not fetch/axios)
  - realtime template param
  - undertow before deliver
  - custom message types (not REST patterns)

Usage:
  python training/eval_realtime.py --endpoint http://localhost:8090 --adapter realtime-v1 --quick
"""
import argparse
import asyncio
import json
import logging
import re
import time
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("eval_realtime")

RT_SYSTEM = """You are Tsunami. You are the wave. You build real-time apps by calling tools.

## Realtime Pipeline (every build follows this EXACTLY)

1. project_init(name, template="realtime") -- create project from realtime scaffold
2. file_write(server/index.js) -- WebSocket server with rooms and message handlers
3. file_write(src/App.tsx) -- React frontend using useWebSocket hook
4. shell_exec -- run npm run build
5. IF ERROR: fix directly with file_edit
6. undertow -- QA before delivery
7. message_result -- land the wave

## WebSocket Message Protocol
Client → Server: {"type": "message", "text": "hello"} | {"type": "join", "room": "general"} | {"type": "set_username", "username": "alice"}
Server → Client: {"type": "connected", "room": "lobby", "username": "user-abc", "history": [...], "users": 3}

## Available Components
useWebSocket: const { connected, send, lastMessage } = useWebSocket({ url: 'ws://localhost:3001', onMessage })
ChatFeed: <ChatFeed messages={msgs} currentUser="alice" />
ChatInput: <ChatInput onSend={text => send({type:"message",text})} />
PresenceDot: <PresenceDot connected={connected} userCount={userCount} />

## Rules
- NEVER use fetch() or REST for real-time data -- use WebSocket send/receive
- ALWAYS write server/index.js BEFORE src/App.tsx
- server/index.js uses WebSocketServer from 'ws'
- One tool call per response. Be brief.
"""

RT_TOOLS = [
    {"type": "function", "function": {
        "name": "project_init",
        "description": "Create a project from the scaffold library.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "template": {"type": "string"}}, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "file_write",
        "description": "Create or overwrite a file with full content.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "file_edit",
        "description": "Make targeted modifications to an existing file.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]},
    }},
    {"type": "function", "function": {
        "name": "shell_exec",
        "description": "Run a shell command and return its output.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "undertow",
        "description": "QA-test an HTML file in a headless browser before delivery.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "message_result",
        "description": "Deliver final outcome and end the task.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "message_chat",
        "description": "Talk to the user. done=true ends, done=false continues.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]},
    }},
]

# ---------------------------------------------------------------------------
# L1 Format
# ---------------------------------------------------------------------------
RT_FORMAT_PROMPTS = [
    {"id": "RTT01", "prompt": "Build a real-time chat app with WebSocket",
     "expected": "project_init"},
    {"id": "RTT02", "prompt": "Build a live collaborative whiteboard that syncs across users",
     "expected": "project_init"},
    {"id": "RTT03", "prompt": "Build a chat app with typing indicators and online presence",
     "expected": "project_init"},
    {"id": "RTT04", "prompt": "What is the WebSocket message protocol used in the realtime scaffold?",
     "expected": "message_chat"},
    {"id": "RTT05", "prompt": "Build a live polling app where votes update in real-time",
     "expected": "project_init"},
    {"id": "RTT06", "prompt": "Build a multi-room live chat with a sidebar",
     "expected": "project_init"},
]

# ---------------------------------------------------------------------------
# L2 Scaffold
# ---------------------------------------------------------------------------
RT_SCAFFOLD_PROMPTS = [
    {"id": "RTS01", "prompt": "Build a real-time notification feed for server alerts"},
    {"id": "RTS02", "prompt": "Build a collaborative todo list with live sync"},
    {"id": "RTS03", "prompt": "Build a live chat app with WebSocket rooms"},
]

# ---------------------------------------------------------------------------
# L3 Error Recovery
# ---------------------------------------------------------------------------
RT_ERROR_SCENARIOS = [
    {
        "id": "RTER01", "name": "fetch-instead-of-websocket",
        "messages": [
            {"role": "system", "content": RT_SYSTEM},
            {"role": "user", "content": "Build a live notification feed"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "notif-feed", "template": "realtime"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'notif-feed' from realtime scaffold. Write server/index.js then src/App.tsx."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "server/index.js", "content": "// ws server"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "fetch('/api/notifications').then(r=>r.json()).then(setData)"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c4", "type": "function", "function": {
                    "name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/notif-feed && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c4",
             "content": "[shell_exec] Warning: fetch('/api/notifications') will fail — this is a WebSocket-only server. Use useWebSocket hook instead."},
        ],
        "expected_tool": "file_edit",
        "reject_tools": ["message_chat", "message_result", "project_init"],
    },
    {
        "id": "RTER02", "name": "missing-ws-package",
        "messages": [
            {"role": "system", "content": RT_SYSTEM},
            {"role": "user", "content": "Build a live chat app"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "live-chat", "template": "realtime"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'live-chat' from realtime scaffold. Write server/index.js then src/App.tsx."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "server/index.js", "content": "import { WebSocketServer } from 'ws'"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "// app"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c4", "type": "function", "function": {
                    "name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/live-chat && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c4",
             "content": "[shell_exec] Error: Cannot find module 'ws'. Run: npm install ws"},
        ],
        "expected_tool": "shell_exec",
        "content_check": "ws",
        "reject_tools": ["message_chat", "message_result"],
    },
    {
        "id": "RTER03", "name": "ts-type-error",
        "messages": [
            {"role": "system", "content": RT_SYSTEM},
            {"role": "user", "content": "Build a collaborative todo list"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "collab-todos", "template": "realtime"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'collab-todos'. Write server/index.js then src/App.tsx."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "server/index.js", "content": "// server"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "// app"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c4", "type": "function", "function": {
                    "name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/collab-todos && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c4",
             "content": "[shell_exec] Error: src/App.tsx(12,18): TS2345: Argument of type 'string' is not assignable to parameter of type 'number'."},
        ],
        "expected_tool": "file_edit",
        "reject_tools": ["message_chat", "message_result", "project_init"],
    },
]

# ---------------------------------------------------------------------------
# L4 Hack-Free
# ---------------------------------------------------------------------------
RT_HACK_SCENARIOS = [
    {
        "id": "RTF01", "hack": "realtime template param",
        "desc": "project_init must include template='realtime'",
        "messages": [
            {"role": "system", "content": RT_SYSTEM},
            {"role": "user", "content": "Build a live chat app with WebSocket"},
        ],
        "expected_tool": "project_init",
        "content_checks": {"contains_any": ["realtime"]},
        "reject_tools": ["message_chat"],
    },
    {
        "id": "RTF02", "hack": "server first",
        "desc": "After project_init, first file_write is server/index.js",
        "messages": [
            {"role": "system", "content": RT_SYSTEM},
            {"role": "user", "content": "Build a real-time collaborative whiteboard"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "whiteboard", "template": "realtime"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'whiteboard' from realtime scaffold. Write server/index.js then src/App.tsx."},
        ],
        "expected_tool": "file_write",
        "content_checks": {"contains_any": ["server/index.js"]},
        "reject_tools": ["message_result", "shell_exec"],
    },
    {
        "id": "RTF03", "hack": "useWebSocket not fetch",
        "desc": "App.tsx must use useWebSocket, not fetch() or axios",
        "messages": [
            {"role": "system", "content": RT_SYSTEM},
            {"role": "user", "content": "Build a live notification feed"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "notif-feed", "template": "realtime"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'notif-feed' from realtime scaffold. Write server/index.js then src/App.tsx."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "server/index.js", "content": "// ws server"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
        ],
        "expected_tool": "file_write",
        "content_checks": {
            "contains_any": ["useWebSocket"],
            "not_contains": ["fetch('/api", 'fetch("/api', "axios.get"],
        },
        "reject_tools": ["message_result"],
    },
    {
        "id": "RTF04", "hack": "undertow before deliver",
        "desc": "After successful build → undertow, not message_result",
        "messages": [
            {"role": "system", "content": RT_SYSTEM},
            {"role": "user", "content": "Build a live chat app"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "live-chat", "template": "realtime"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'live-chat' from realtime scaffold."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "server/index.js", "content": "// server"})}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c3", "type": "function", "function": {
                    "name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "// app"})}}
            ]},
            {"role": "tool", "tool_call_id": "c3", "content": "[file_write] Written."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c4", "type": "function", "function": {
                    "name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/live-chat && npm run build"})}}
            ]},
            {"role": "tool", "tool_call_id": "c4", "content": "[shell_exec] Build succeeded. dist/ ready."},
        ],
        "expected_tool": "undertow",
        "reject_tools": ["message_result"],
    },
    {
        "id": "RTF05", "hack": "WS server uses 'ws' library",
        "desc": "server/index.js should use WebSocketServer from 'ws', not express-ws or socket.io",
        "messages": [
            {"role": "system", "content": RT_SYSTEM},
            {"role": "user", "content": "Build a multi-room chat app"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "multi-chat", "template": "realtime"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'multi-chat' from realtime scaffold. Write server/index.js then src/App.tsx."},
        ],
        "expected_tool": "file_write",
        "content_checks": {
            "contains_any": ["WebSocketServer", "from 'ws'", 'from "ws"'],
            "not_contains": ["socket.io", "express-ws"],
        },
        "reject_tools": ["message_result", "shell_exec"],
    },
    {
        "id": "RTF06", "hack": "no main.tsx overwrite",
        "desc": "After project_init → server/index.js, never main.tsx",
        "messages": [
            {"role": "system", "content": RT_SYSTEM},
            {"role": "user", "content": "Build a live collaborative todos app"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "project_init", "arguments": json.dumps({"name": "collab-todos", "template": "realtime"})}}
            ]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[project_init] Created 'collab-todos' from realtime scaffold. Write server/index.js then src/App.tsx."},
        ],
        "expected_tool": "file_write",
        "content_checks": {
            "not_contains": ["main.tsx", "vite.config.ts"],
        },
        "reject_tools": ["message_result"],
    },
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def _call(client, endpoint, adapter, messages, timeout=300.0):
    payload = {
        "model": "tsunami",
        "messages": messages,
        "tools": RT_TOOLS,
        "max_tokens": 512,
        "temperature": 0.0,
    }
    if adapter and adapter != "none":
        payload["adapter"] = adapter
    r = await client.post(f"{endpoint}/v1/chat/completions", json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _get_tool_name(resp):
    choices = resp.get("choices", [])
    if not choices:
        return None
    msg = choices[0].get("message", {})
    tc = msg.get("tool_calls", [])
    if tc:
        return tc[0].get("function", {}).get("name")
    m = re.search(r'"name"\s*:\s*"(\w+)"', msg.get("content", ""))
    return m.group(1) if m else None


def _get_tool_args(resp):
    choices = resp.get("choices", [])
    if not choices:
        return {}
    msg = choices[0].get("message", {})
    tc = msg.get("tool_calls", [])
    if tc:
        raw = tc[0].get("function", {}).get("arguments", "{}")
        try:
            return json.loads(raw)
        except Exception:
            return {"_raw": raw}
    return {}


# ---------------------------------------------------------------------------
# Level runners
# ---------------------------------------------------------------------------

async def run_l1(client, endpoint, adapter, quick):
    passed, total = 0, 0
    for p in RT_FORMAT_PROMPTS:
        msgs = [{"role": "system", "content": RT_SYSTEM}, {"role": "user", "content": p["prompt"]}]
        try:
            resp = await _call(client, endpoint, adapter, msgs)
            tool = _get_tool_name(resp)
            ok = tool == p["expected"]
            log.info(f"  L1 {p['id']}: {'PASS' if ok else 'FAIL'} — got={tool!r} want={p['expected']!r}")
            if ok:
                passed += 1
        except Exception as e:
            log.error(f"  L1 {p['id']}: ERROR — {e}")
        total += 1
        if quick and total >= 3:
            break
    return passed, total


async def run_l2(client, endpoint, adapter, quick):
    """project_init(template=realtime) → file_write(server/index.js)"""
    passed, total = 0, 0
    for p in RT_SCAFFOLD_PROMPTS:
        msgs = [{"role": "system", "content": RT_SYSTEM}, {"role": "user", "content": p["prompt"]}]
        try:
            resp1 = await _call(client, endpoint, adapter, msgs)
            t1 = _get_tool_name(resp1)
            a1 = _get_tool_args(resp1)
            ok1 = t1 == "project_init" and "realtime" in json.dumps(a1)

            if ok1:
                name = a1.get("name", "app")
                msgs2 = msgs + [
                    {"role": "assistant", "content": "", "tool_calls": [
                        {"id": "l2c1", "type": "function", "function": {
                            "name": "project_init", "arguments": json.dumps(a1)}}
                    ]},
                    {"role": "tool", "tool_call_id": "l2c1",
                     "content": f"[project_init] Created '{name}' from realtime scaffold. Write server/index.js then src/App.tsx."},
                ]
                resp2 = await _call(client, endpoint, adapter, msgs2)
                t2 = _get_tool_name(resp2)
                a2 = _get_tool_args(resp2)
                ok2 = t2 == "file_write" and "server" in a2.get("path", "").lower()
                ok = ok1 and ok2
                log.info(f"  L2 {p['id']}: {'PASS' if ok else 'FAIL'} — t1={t1!r}(rt={ok1}) t2={t2!r}(server={ok2})")
            else:
                ok = False
                log.info(f"  L2 {p['id']}: FAIL — t1={t1!r} (no realtime template)")
            if ok:
                passed += 1
        except Exception as e:
            log.error(f"  L2 {p['id']}: ERROR — {e}")
        total += 1
        if quick and total >= 2:
            break
    return passed, total


async def run_l3(client, endpoint, adapter, quick):
    passed, total = 0, 0
    for s in RT_ERROR_SCENARIOS:
        try:
            resp = await _call(client, endpoint, adapter, s["messages"])
            tool = _get_tool_name(resp)
            args = _get_tool_args(resp)
            ok = tool == s["expected_tool"]
            if ok and "content_check" in s:
                ok = s["content_check"].lower() in json.dumps(args).lower()
            if tool in s.get("reject_tools", []):
                ok = False
            log.info(f"  L3 {s['id']}: {'PASS' if ok else 'FAIL'} — got={tool!r} want={s['expected_tool']!r}")
            if ok:
                passed += 1
        except Exception as e:
            log.error(f"  L3 {s['id']}: ERROR — {e}")
        total += 1
        if quick and total >= 2:
            break
    return passed, total


async def run_l4(client, endpoint, adapter, quick):
    passed, total = 0, 0
    for s in RT_HACK_SCENARIOS:
        try:
            resp = await _call(client, endpoint, adapter, s["messages"])
            tool = _get_tool_name(resp)
            args = _get_tool_args(resp)
            ok = tool == s["expected_tool"]
            if ok and tool in s.get("reject_tools", []):
                ok = False
            if ok and s.get("content_checks"):
                checks = s["content_checks"]
                cstr = json.dumps(args)
                if "contains_any" in checks:
                    ok = ok and any(c.lower() in cstr.lower() for c in checks["contains_any"])
                if "not_contains" in checks:
                    ok = ok and all(c not in cstr for c in checks["not_contains"])
            log.info(f"  L4 {s['id']}: {'PASS' if ok else 'FAIL'} — tool={tool!r} [{s['hack']}]")
            if ok:
                passed += 1
        except Exception as e:
            log.error(f"  L4 {s['id']}: ERROR — {e}")
        total += 1
        if quick and total >= 4:
            break
    return passed, total


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="http://localhost:8090")
    ap.add_argument("--adapter", default="realtime-v1")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    log.info(f"eval_realtime — endpoint={args.endpoint} adapter={args.adapter} quick={args.quick}")

    async with httpx.AsyncClient() as client:
        l1p, l1t = await run_l1(client, args.endpoint, args.adapter, args.quick)
        l2p, l2t = await run_l2(client, args.endpoint, args.adapter, args.quick)
        l3p, l3t = await run_l3(client, args.endpoint, args.adapter, args.quick)
        l4p, l4t = await run_l4(client, args.endpoint, args.adapter, args.quick)

    total_p = l1p + l2p + l3p + l4p
    total_t = l1t + l2t + l3t + l4t
    print(f"\n=== REALTIME EVAL RESULTS ===")
    print(f"  L1 Format:          {l1p}/{l1t}")
    print(f"  L2 Scaffold:        {l2p}/{l2t}")
    print(f"  L3 Error Recovery:  {l3p}/{l3t}")
    print(f"  L4 Hack-Free:       {l4p}/{l4t}")
    print(f"  TOTAL:              {total_p}/{total_t}  ({total_p/max(total_t,1)*100:.1f}%)")

    out = {
        "adapter": args.adapter, "quick": args.quick,
        "l1": f"{l1p}/{l1t}", "l2": f"{l2p}/{l2t}",
        "l3": f"{l3p}/{l3t}", "l4": f"{l4p}/{l4t}",
        "total": f"{total_p}/{total_t}",
        "pct": round(total_p / max(total_t, 1), 3),
    }
    out_path = Path("workspace/eval_results") / f"realtime_{args.adapter}_{int(time.time())}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    log.info(f"Results saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
