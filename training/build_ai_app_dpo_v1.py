#!/usr/bin/env python3
"""build_ai_app_dpo_v1.py — DPO training data for the ai-app-v1 adapter.

18 pairs (3 per fault, 6 faults):
  AAF01 — template choice: template="ai-app" not "fullstack" or "react-app"
  AAF02 — server first: write server/index.js before App.tsx
  AAF03 — SSE streaming: use EventSource/fetch stream not fetch→JSON
  AAF04 — proxy required: API key belongs in server, never in frontend
  AAF05 — undertow before message_result
  AAF06 — file_edit on error, not file_read
"""
import json, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

OUT = Path("workspace/training_data/ai_app_dpo_v1.jsonl")
TODAY = str(date.today())


def pair(source_bug, chosen, rejected, note):
    return {
        "prompt": f"[AAF probe: {source_bug}]",
        "chosen": chosen,
        "rejected": rejected,
        "source_bug": source_bug,
        "note": note,
        "images": [],
        "date": TODAY,
    }


# ── AAF01: template choice ─────────────────────────────────────────────────────
AAF01_PAIRS = [
    pair("AAF01a",
         chosen='project_init(name="ai-chatbot", template="ai-app")',
         rejected='project_init(name="ai-chatbot", template="fullstack")',
         note="AI chatbot → template=ai-app, not fullstack (no SQLite needed)"),
    pair("AAF01b",
         chosen='project_init(name="writing-assistant", template="ai-app")',
         rejected='project_init(name="writing-assistant", template="react-app")',
         note="Writing assistant → ai-app template, not bare react-app (needs proxy server)"),
    pair("AAF01c",
         chosen='project_init(name="code-reviewer", template="ai-app") # SSE proxy + useChat hook',
         rejected='project_init(name="code-reviewer", template="react-app")  # no server proxy',
         note="Code reviewer → explicit template=ai-app, not react-app (needs SSE proxy server)"),
]

# ── AAF02: server first ────────────────────────────────────────────────────────
AAF02_PAIRS = [
    pair("AAF02a",
         chosen="1. project_init(template='ai-app')\n2. file_write server/index.js  ← proxy first\n3. file_write src/App.tsx",
         rejected="1. project_init(template='ai-app')\n2. file_write src/App.tsx  ← UI first\n3. file_write server/index.js",
         note="Write server/index.js before App.tsx — frontend imports useChat which calls the server"),
    pair("AAF02b",
         chosen="project_init → file_write server/index.js (POST /api/chat SSE endpoint) → file_write src/App.tsx with useChat",
         rejected="project_init → file_write src/App.tsx → file_write server/index.js",
         note="Server-first order: proxy handles auth + streaming; App just calls /api/chat"),
    pair("AAF02c",
         chosen="After project_init: write server/index.js with the LLM API fetch + SSE streaming, then write App.tsx",
         rejected="After project_init: write App.tsx with the chat UI first, then add server/index.js later",
         note="Server must exist before we verify the full streaming pipeline works"),
]

# ── AAF03: SSE streaming ───────────────────────────────────────────────────────
AAF03_PAIRS = [
    pair("AAF03a",
         chosen="Server streams via SSE (res.write 'data: {delta}\\n\\n'). Frontend reads with getReader() loop, appending delta tokens.",
         rejected="Server returns complete JSON response. Frontend does: const data = await res.json(); setResponse(data.content)",
         note="Use SSE streaming — never wait for full response JSON; that defeats streaming UX"),
    pair("AAF03b",
         chosen="const res = await fetch('/api/chat', {method:'POST', body:...})\nconst reader = res.body.getReader()\n// read chunks, parse delta lines",
         rejected="const res = await fetch('/api/chat', {method:'POST', body:...})\nconst {message} = await res.json()\nsetMessages([...messages, {role:'assistant', content:message}])",
         note="Stream token-by-token with getReader(); never await res.json() for LLM responses"),
    pair("AAF03c",
         chosen="useChat hook: appends delta tokens character-by-character as SSE arrives → smooth typing effect",
         rejected="useChat hook: awaits res.json() for full response, then sets content at once → jarring jump from empty to full",
         note="Token-streaming creates the typing effect; batch update via res.json() is jarring"),
]

# ── AAF04: proxy required ──────────────────────────────────────────────────────
AAF04_PAIRS = [
    pair("AAF04a",
         chosen="server/index.js: Authorization: `Bearer ${process.env.OPENAI_API_KEY}` — key stays in server .env",
         rejected="src/App.tsx: fetch('https://api.openai.com/v1/chat/completions', { headers: { Authorization: 'Bearer sk-...' } })",
         note="API key must live in server .env — never hardcode in React/browser code (exposed to all users)"),
    pair("AAF04b",
         chosen="Frontend calls POST /api/chat (our Express proxy). Server adds Authorization header. Key never reaches browser.",
         rejected="Frontend calls OpenAI directly from React: fetch('https://api.openai.com/...', {headers:{Authorization: `Bearer ${import.meta.env.VITE_OPENAI_KEY}`}})",
         note="VITE_ env vars are bundled into client JS — anyone can read the key from source"),
    pair("AAF04c",
         chosen="Architecture: React → POST /api/chat → Express proxy (has key) → OpenAI API",
         rejected="Architecture: React → OpenAI API directly (key in VITE_ env var or hardcoded)",
         note="The proxy is not optional — it's the security boundary that keeps the API key server-side"),
]

# ── AAF05: undertow before message_result ─────────────────────────────────────
AAF05_PAIRS = [
    pair("AAF05a",
         chosen="npm run build ✓ → undertow() → [screenshot: streaming chat works] → message_result(done=True)",
         rejected="npm run build ✓ → message_result('AI chatbot is ready', done=True)  # no visual verification",
         note="Always undertow() after build for AI apps — verify streaming chat actually renders tokens"),
    pair("AAF05b",
         chosen="shell_exec('npm run build') → undertow → message_result → done",
         rejected="shell_exec('npm run build') → message_result → done  # visual QA skipped",
         note="Skip undertow = deliver without QA; streaming bugs are invisible from build output alone"),
    pair("AAF05c",
         chosen="Build success → undertow() confirms UI looks right → message_result summarizes what was built",
         rejected="Build success → immediately message_result without checking UI",
         note="Streaming chat UI needs visual check — empty screen or broken SSE won't show in build logs"),
]

# ── AAF06: file_edit on error ──────────────────────────────────────────────────
AAF06_PAIRS = [
    pair("AAF06a",
         chosen="Build fails: 'Cannot find module dotenv' line 3 → file_edit(package.json, add dotenv dep) → npm install → npm run build",
         rejected="Build fails: 'Cannot find module dotenv' → file_read(server/index.js) → file_read(package.json) → ...",
         note="Missing module error with clear cause → file_edit directly, no re-reading files first"),
    pair("AAF06b",
         chosen="TypeError: res.body.getReader is not a function (line 45) → file_edit(src/hooks/useChat.ts, fix getReader call)",
         rejected="TypeError: res.body.getReader is not a function → file_read(src/hooks/useChat.ts) to 'investigate'",
         note="Runtime error with line number → file_edit the specific line, don't file_read first"),
    pair("AAF06c",
         chosen="SyntaxError: Unexpected token '<' at server/index.js:12 → file_edit to fix the JSX in a .js file (rename or remove JSX)",
         rejected="SyntaxError in server/index.js → file_read to understand the problem before editing",
         note="Syntax error with line info is self-explanatory — edit immediately"),
]


def main():
    all_pairs = AAF01_PAIRS + AAF02_PAIRS + AAF03_PAIRS + AAF04_PAIRS + AAF05_PAIRS + AAF06_PAIRS
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for p in all_pairs:
            f.write(json.dumps(p) + "\n")
    print(f"Wrote {len(all_pairs)} pairs to {OUT}")
    for p in all_pairs:
        print(f"  {p['source_bug']}: {p['note'][:65]}")


if __name__ == "__main__":
    main()
