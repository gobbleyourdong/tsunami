#!/usr/bin/env python3
"""build_vision_examples.py — SFT examples for the riptide + undertow vision pipeline.

The bet for small-model quality: pure-text reasoning about UI layout fails.
Vision grounding (riptide) + visual QA (undertow VLM-describe) is the force
multiplier that makes a 4B model competitive. These examples teach the
model WHEN to call riptide, HOW to use the returned positions, and HOW
to pair it with undertow for pre-delivery verification.

Scenarios taught:
  V01 — Clone-from-screenshot: user has an image, wants a page that matches
  V02 — Research + clone: "build a landing page like Stripe's" flow
  V03 — Generated reference: generate_image → riptide → build to match
  V04 — Dashboard layout mimic with multiple regions
  V05 — Undertow VLM-describe confirms visual match before delivery
  V06 — Riptide focus hints for specific element extraction
  V07 — Iteration: riptide positions changed → file_edit to fix CSS
  V08 — undertow failure → eddy compare against riptide positions → re-edit

Output: workspace/training_data/e4b_toolcall_train_vision.jsonl (~8 examples)

Usage:
    python3 training/build_vision_examples.py
    # Appended into the training set by the champion builder later.
"""
import json
import os
import sys
from transformers import AutoTokenizer

sys.path.insert(0, os.path.dirname(__file__))
from build_v69 import SYSTEM_TEXT  # reuse existing (we'll override in champion rebuild)

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_vision.jsonl"


# Minimal 11-tool schema (matches live lite registry).
TOOLS = [
    {"type": "function", "function": {"name": "project_init", "description": "Create project from scaffold library.",
        "parameters": {"type": "OBJECT", "properties": {"name": {"type": "STRING"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Create/overwrite file.",
        "parameters": {"type": "OBJECT", "properties": {"path": {"type": "STRING"}, "content": {"type": "STRING"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_read", "description": "Read file content.",
        "parameters": {"type": "OBJECT", "properties": {"path": {"type": "STRING"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Modify existing file.",
        "parameters": {"type": "OBJECT", "properties": {"path": {"type": "STRING"}, "old_text": {"type": "STRING"}, "new_text": {"type": "STRING"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run shell command.",
        "parameters": {"type": "OBJECT", "properties": {"command": {"type": "STRING"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "Search the web (for reference images).",
        "parameters": {"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "undertow", "description": "QA-test HTML in headless browser with VLM describe.",
        "parameters": {"type": "OBJECT", "properties": {"path": {"type": "STRING"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "riptide", "description": "Extract element positions from a reference image. Returns ratio-based CSS positioning.",
        "parameters": {"type": "OBJECT", "properties": {"image_path": {"type": "STRING"}, "focus": {"type": "STRING"}}, "required": ["image_path"]}}},
    {"type": "function", "function": {"name": "generate_image", "description": "Generate image from text description.",
        "parameters": {"type": "OBJECT", "properties": {"prompt": {"type": "STRING"}, "path": {"type": "STRING"}}, "required": ["prompt", "path"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final outcome.",
        "parameters": {"type": "OBJECT", "properties": {"text": {"type": "STRING"}}}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to user. done=true ends task.",
        "parameters": {"type": "OBJECT", "properties": {"text": {"type": "STRING"}, "done": {"type": "BOOLEAN"}}, "required": ["text"]}}},
]


def _sys():
    return {"role": "system", "content": SYSTEM_TEXT}


def _user(text):
    return {"role": "user", "content": text}


def _tool_call(name, args):
    return {"role": "assistant", "content": "",
            "tool_calls": [{"type": "function", "function": {"name": name, "arguments": args}}]}


def _tool_resp(name, result):
    return {"role": "tool", "name": name, "content": result}


# ---------------------------------------------------------------------------
# V01 — Clone from user-provided screenshot
# ---------------------------------------------------------------------------
def v01_clone_from_screenshot():
    return [
        _sys(),
        _user("Clone this dashboard design from /tmp/dashboard_ref.png — a sidebar on the left with nav, top bar with search, main content with 3 stat cards and a chart."),
        _tool_call("project_init", {"name": "dashboard-clone"}),
        _tool_resp("project_init", "Created workspace/deliverables/dashboard-clone/ from dashboard scaffold."),
        _tool_call("riptide", {"image_path": "/tmp/dashboard_ref.png",
                                "focus": "sidebar, top bar, stat cards, chart region — return percentages"}),
        _tool_resp("riptide",
            "sidebar: left=0% top=0% width=18% height=100%\n"
            "topbar: left=18% top=0% width=82% height=8%\n"
            "stat_cards: left=20% top=12% width=76% height=15%\n"
            "chart: left=20% top=30% width=76% height=55%"),
        _tool_call("file_write", {
            "path": "workspace/deliverables/dashboard-clone/src/App.tsx",
            "content": (
                "import { Card } from './components/ui';\n"
                "export default function App() {\n"
                "  return (\n"
                "    <div className='relative w-screen h-screen bg-slate-900'>\n"
                "      <aside className='absolute' style={{left:'0%',top:'0%',width:'18%',height:'100%'}}>Nav</aside>\n"
                "      <header className='absolute' style={{left:'18%',top:'0%',width:'82%',height:'8%'}}>Search</header>\n"
                "      <section className='absolute grid grid-cols-3 gap-3' style={{left:'20%',top:'12%',width:'76%',height:'15%'}}>\n"
                "        <Card>Stat 1</Card><Card>Stat 2</Card><Card>Stat 3</Card>\n"
                "      </section>\n"
                "      <section className='absolute' style={{left:'20%',top:'30%',width:'76%',height:'55%'}}>\n"
                "        <Card>Chart</Card>\n"
                "      </section>\n"
                "    </div>\n"
                "  );\n"
                "}\n"
            )}),
        _tool_resp("file_write", "wrote 780 bytes to workspace/deliverables/dashboard-clone/src/App.tsx"),
        _tool_call("shell_exec", {"command": "cd workspace/deliverables/dashboard-clone && npm run build"}),
        _tool_resp("shell_exec", "vite v5.0.0 building for production...\n✓ built in 1.8s"),
        _tool_call("undertow", {"path": "workspace/deliverables/dashboard-clone/dist/index.html"}),
        _tool_resp("undertow", "Screenshot describes: 'A dashboard with a sidebar on the left, top search bar, three stat cards, and a chart region below.' Matches reference. PASS."),
        _tool_call("message_result", {"text": "Dashboard clone built to match /tmp/dashboard_ref.png — sidebar, top bar, stat cards, and chart at grounded positions."}),
    ]


# ---------------------------------------------------------------------------
# V02 — Research + clone: "like Stripe's landing page"
# ---------------------------------------------------------------------------
def v02_research_clone():
    return [
        _sys(),
        _user("Build a landing page that looks like Stripe's — hero section, feature grid, pricing."),
        _tool_call("search_web", {"query": "Stripe landing page layout 2026 hero feature grid screenshot"}),
        _tool_resp("search_web", "Found reference images. Saved: /tmp/stripe_landing_ref.png (hero centered with big headline, 3-column feature grid below, pricing table at bottom)."),
        _tool_call("project_init", {"name": "stripe-like-landing"}),
        _tool_resp("project_init", "Created workspace/deliverables/stripe-like-landing/ from react-app scaffold."),
        _tool_call("riptide", {"image_path": "/tmp/stripe_landing_ref.png",
                                "focus": "hero, feature grid, pricing — percentages"}),
        _tool_resp("riptide",
            "hero: left=0% top=0% width=100% height=45%\n"
            "feature_grid: left=10% top=48% width=80% height=25% (3 columns)\n"
            "pricing: left=10% top=76% width=80% height=22%"),
        _tool_call("file_write", {
            "path": "workspace/deliverables/stripe-like-landing/src/App.tsx",
            "content": (
                "import { Card, Button } from './components/ui';\n"
                "export default function App() {\n"
                "  return (\n"
                "    <div className='relative w-full min-h-screen'>\n"
                "      <section className='flex flex-col items-center justify-center' style={{height:'45vh'}}>\n"
                "        <h1 className='text-5xl font-bold'>Infrastructure for payments</h1>\n"
                "        <Button className='mt-6'>Start now</Button>\n"
                "      </section>\n"
                "      <section className='grid grid-cols-3 gap-6 px-20' style={{marginTop:'3vh'}}>\n"
                "        <Card>Fast</Card><Card>Secure</Card><Card>Global</Card>\n"
                "      </section>\n"
                "      <section className='grid grid-cols-3 gap-6 px-20' style={{marginTop:'3vh'}}>\n"
                "        <Card>Starter</Card><Card>Pro</Card><Card>Enterprise</Card>\n"
                "      </section>\n"
                "    </div>\n"
                "  );\n"
                "}\n"
            )}),
        _tool_resp("file_write", "wrote 780 bytes"),
        _tool_call("shell_exec", {"command": "cd workspace/deliverables/stripe-like-landing && npm run build"}),
        _tool_resp("shell_exec", "✓ built in 1.2s"),
        _tool_call("undertow", {"path": "workspace/deliverables/stripe-like-landing/dist/index.html"}),
        _tool_resp("undertow", "Describes: 'Landing page with centered hero, 3-column feature grid, and pricing cards below.' Matches reference layout. PASS."),
        _tool_call("message_result", {"text": "Stripe-style landing page built with riptide-grounded hero, feature grid, and pricing layout."}),
    ]


# ---------------------------------------------------------------------------
# V03 — Generated reference: generate_image → riptide → build
# ---------------------------------------------------------------------------
def v03_generated_reference():
    return [
        _sys(),
        _user("Build a music player UI. I don't have a reference — generate one first and match it."),
        _tool_call("project_init", {"name": "music-player"}),
        _tool_resp("project_init", "Created workspace/deliverables/music-player/."),
        _tool_call("generate_image", {
            "prompt": "minimalist music player UI, dark theme, album art on left, track list on right, playback controls at bottom center",
            "path": "workspace/deliverables/music-player/reference.png"}),
        _tool_resp("generate_image", "Generated workspace/deliverables/music-player/reference.png (1024x768)."),
        _tool_call("riptide", {"image_path": "workspace/deliverables/music-player/reference.png",
                                "focus": "album art, track list, playback controls"}),
        _tool_resp("riptide",
            "album_art: left=5% top=10% width=35% height=60%\n"
            "track_list: left=45% top=10% width=50% height=60%\n"
            "playback_controls: left=25% top=80% width=50% height=15%"),
        _tool_call("file_write", {
            "path": "workspace/deliverables/music-player/src/App.tsx",
            "content": (
                "import { Card, Button } from './components/ui';\n"
                "export default function App() {\n"
                "  return (\n"
                "    <div className='relative w-screen h-screen bg-slate-950 text-white'>\n"
                "      <div className='absolute' style={{left:'5%',top:'10%',width:'35%',height:'60%'}}>\n"
                "        <Card className='h-full'>Album Art</Card>\n"
                "      </div>\n"
                "      <div className='absolute overflow-y-auto' style={{left:'45%',top:'10%',width:'50%',height:'60%'}}>\n"
                "        <Card>Track 1</Card><Card>Track 2</Card><Card>Track 3</Card>\n"
                "      </div>\n"
                "      <div className='absolute flex justify-center items-center gap-4' style={{left:'25%',top:'80%',width:'50%',height:'15%'}}>\n"
                "        <Button>⏮</Button><Button>▶</Button><Button>⏭</Button>\n"
                "      </div>\n"
                "    </div>\n"
                "  );\n"
                "}\n"
            )}),
        _tool_resp("file_write", "wrote 820 bytes"),
        _tool_call("shell_exec", {"command": "cd workspace/deliverables/music-player && npm run build"}),
        _tool_resp("shell_exec", "✓ built in 1.5s"),
        _tool_call("undertow", {"path": "workspace/deliverables/music-player/dist/index.html"}),
        _tool_resp("undertow", "Describes: 'Music player UI with album art on left, track list right, playback controls centered at bottom.' Matches generated reference. PASS."),
        _tool_call("message_result", {"text": "Music player UI built from generated reference — album art, track list, and playback controls grounded via riptide."}),
    ]


# ---------------------------------------------------------------------------
# V04 — Undertow VLM-describe catches placeholder, forces re-edit with riptide
# ---------------------------------------------------------------------------
def v04_undertow_catches_placeholder():
    return [
        _sys(),
        _user("Clone the Twitter compose modal from /tmp/twitter_compose.png — profile pic, textarea, media buttons, tweet button."),
        _tool_call("project_init", {"name": "twitter-compose-clone"}),
        _tool_resp("project_init", "Created workspace/deliverables/twitter-compose-clone/."),
        _tool_call("riptide", {"image_path": "/tmp/twitter_compose.png",
                                "focus": "profile avatar, textarea, media buttons row, tweet button"}),
        _tool_resp("riptide",
            "avatar: left=3% top=5% width=8% height=10%\n"
            "textarea: left=14% top=5% width=83% height=45%\n"
            "media_buttons: left=14% top=55% width=50% height=10%\n"
            "tweet_button: left=80% top=55% width=17% height=10%"),
        _tool_call("file_write", {
            "path": "workspace/deliverables/twitter-compose-clone/src/App.tsx",
            "content": (
                "import { Button, Avatar } from './components/ui';\n"
                "import { useState } from 'react';\n"
                "export default function App() {\n"
                "  const [text, setText] = useState('');\n"
                "  return (\n"
                "    <div className='relative w-[600px] h-[400px] bg-white p-4'>\n"
                "      <Avatar className='absolute' style={{left:'3%',top:'5%',width:'8%',height:'10%'}} />\n"
                "      <textarea value={text} onChange={e=>setText(e.target.value)} placeholder=\"What's happening?\"\n"
                "        className='absolute border-0 text-xl outline-none resize-none'\n"
                "        style={{left:'14%',top:'5%',width:'83%',height:'45%'}} />\n"
                "      <div className='absolute flex gap-2' style={{left:'14%',top:'55%',width:'50%',height:'10%'}}>\n"
                "        <Button size='icon'>📷</Button><Button size='icon'>🎬</Button><Button size='icon'>📊</Button>\n"
                "      </div>\n"
                "      <Button className='absolute bg-blue-500 text-white rounded-full'\n"
                "        style={{left:'80%',top:'55%',width:'17%',height:'10%'}}>Tweet</Button>\n"
                "    </div>\n"
                "  );\n"
                "}\n"
            )}),
        _tool_resp("file_write", "wrote 1240 bytes"),
        _tool_call("shell_exec", {"command": "cd workspace/deliverables/twitter-compose-clone && npm run build"}),
        _tool_resp("shell_exec", "✓ built in 1.1s"),
        _tool_call("undertow", {"path": "workspace/deliverables/twitter-compose-clone/dist/index.html"}),
        _tool_resp("undertow", "Describes: 'Modal with avatar top-left, large textarea spanning most of area, three icon buttons bottom-left, blue Tweet button bottom-right.' Matches reference. PASS."),
        _tool_call("message_result", {"text": "Twitter compose clone built with riptide-grounded positions for avatar, textarea, media buttons, and Tweet button."}),
    ]


# ---------------------------------------------------------------------------
# V05 — Riptide mismatch → file_edit to fix
# ---------------------------------------------------------------------------
def v05_iterative_fix():
    return [
        _sys(),
        _user("I sent you /tmp/hero_ref.png — build a hero section that matches it. Big headline centered, subtext below, single CTA button."),
        _tool_call("project_init", {"name": "hero-section"}),
        _tool_resp("project_init", "Created workspace/deliverables/hero-section/."),
        _tool_call("riptide", {"image_path": "/tmp/hero_ref.png",
                                "focus": "headline, subtext, CTA button"}),
        _tool_resp("riptide",
            "headline: left=15% top=30% width=70% height=15%\n"
            "subtext: left=20% top=47% width=60% height=10%\n"
            "cta: left=42% top=62% width=16% height=8%"),
        _tool_call("file_write", {
            "path": "workspace/deliverables/hero-section/src/App.tsx",
            "content": (
                "import { Button } from './components/ui';\n"
                "export default function App() {\n"
                "  return (\n"
                "    <div className='relative w-screen h-screen bg-gradient-to-br from-slate-900 to-slate-700'>\n"
                "      <h1 className='absolute text-6xl font-bold text-center text-white'\n"
                "          style={{left:'15%',top:'30%',width:'70%',height:'15%'}}>Build faster</h1>\n"
                "      <p className='absolute text-xl text-center text-slate-300'\n"
                "         style={{left:'20%',top:'47%',width:'60%',height:'10%'}}>The platform for modern teams.</p>\n"
                "      <Button className='absolute'\n"
                "              style={{left:'42%',top:'62%',width:'16%',height:'8%'}}>Get started</Button>\n"
                "    </div>\n"
                "  );\n"
                "}\n"
            )}),
        _tool_resp("file_write", "wrote 720 bytes"),
        _tool_call("shell_exec", {"command": "cd workspace/deliverables/hero-section && npm run build"}),
        _tool_resp("shell_exec", "✓ built in 1.0s"),
        _tool_call("undertow", {"path": "workspace/deliverables/hero-section/dist/index.html"}),
        _tool_resp("undertow", "Describes: 'Hero with centered headline, subtext, and a single CTA button in a dark gradient background.' Matches reference proportions. PASS."),
        _tool_call("message_result", {"text": "Hero section built matching /tmp/hero_ref.png — headline, subtext, and CTA positioned via riptide."}),
    ]


# ---------------------------------------------------------------------------
# V06 — Undertow FAIL: missing button handler → file_edit to add it → pass
# ---------------------------------------------------------------------------
def v06_undertow_fail_missing_handler():
    return [
        _sys(),
        _user("Build a counter app with + and − buttons that update a number."),
        _tool_call("project_init", {"name": "counter-app"}),
        _tool_resp("project_init", "Created workspace/deliverables/counter-app/."),
        _tool_call("file_write", {
            "path": "workspace/deliverables/counter-app/src/App.tsx",
            "content": (
                "import { Button } from './components/ui';\n"
                "import { useState } from 'react';\n"
                "export default function App() {\n"
                "  const [count, setCount] = useState(0);\n"
                "  return (\n"
                "    <div className='flex flex-col items-center justify-center h-screen gap-4'>\n"
                "      <h1 className='text-6xl'>{count}</h1>\n"
                "      <div className='flex gap-2'>\n"
                "        <Button id='dec'>−</Button>\n"
                "        <Button id='inc'>+</Button>\n"
                "      </div>\n"
                "    </div>\n"
                "  );\n"
                "}\n"
            )}),
        _tool_resp("file_write", "wrote 420 bytes"),
        _tool_call("shell_exec", {"command": "cd workspace/deliverables/counter-app && npm run build"}),
        _tool_resp("shell_exec", "✓ built in 0.9s"),
        _tool_call("undertow", {"path": "workspace/deliverables/counter-app/dist/index.html"}),
        _tool_resp("undertow", "FAIL: clicked button#inc and button#dec — neither changed the displayed number. Buttons have no onClick handlers."),
        _tool_call("file_edit", {
            "path": "workspace/deliverables/counter-app/src/App.tsx",
            "old_text": "        <Button id='dec'>−</Button>\n        <Button id='inc'>+</Button>",
            "new_text": "        <Button id='dec' onClick={() => setCount(c => c - 1)}>−</Button>\n        <Button id='inc' onClick={() => setCount(c => c + 1)}>+</Button>",
        }),
        _tool_resp("file_edit", "modified 2 lines in App.tsx"),
        _tool_call("shell_exec", {"command": "cd workspace/deliverables/counter-app && npm run build"}),
        _tool_resp("shell_exec", "✓ built in 0.9s"),
        _tool_call("undertow", {"path": "workspace/deliverables/counter-app/dist/index.html"}),
        _tool_resp("undertow", "PASS: clicked button#inc → 0→1. Clicked button#dec → 1→0. Counter works."),
        _tool_call("message_result", {"text": "Counter app built — + and − buttons increment/decrement the displayed count."}),
    ]


# ---------------------------------------------------------------------------
# V07 — Undertow FAIL: VLM describes missing element → file_edit to add it
# ---------------------------------------------------------------------------
def v07_undertow_fail_missing_element():
    return [
        _sys(),
        _user("Build a dashboard with a header, 3 stat cards, and a chart below them."),
        _tool_call("project_init", {"name": "stats-dash"}),
        _tool_resp("project_init", "Created workspace/deliverables/stats-dash/."),
        _tool_call("file_write", {
            "path": "workspace/deliverables/stats-dash/src/App.tsx",
            "content": (
                "import { Card } from './components/ui';\n"
                "export default function App() {\n"
                "  return (\n"
                "    <div className='p-6'>\n"
                "      <h1 className='text-3xl mb-4'>Dashboard</h1>\n"
                "      <div className='grid grid-cols-3 gap-4'>\n"
                "        <Card>Users: 1.2k</Card>\n"
                "        <Card>Revenue: $4.5k</Card>\n"
                "        <Card>Sessions: 342</Card>\n"
                "      </div>\n"
                "    </div>\n"
                "  );\n"
                "}\n"
            )}),
        _tool_resp("file_write", "wrote 380 bytes"),
        _tool_call("shell_exec", {"command": "cd workspace/deliverables/stats-dash && npm run build"}),
        _tool_resp("shell_exec", "✓ built in 1.0s"),
        _tool_call("undertow", {"path": "workspace/deliverables/stats-dash/dist/index.html"}),
        _tool_resp("undertow", "FAIL: screenshot describes 'a dashboard header with three stat cards below it.' Missing the chart the user requested — no chart element rendered."),
        _tool_call("file_edit", {
            "path": "workspace/deliverables/stats-dash/src/App.tsx",
            "old_text": "        <Card>Sessions: 342</Card>\n      </div>\n    </div>",
            "new_text": (
                "        <Card>Sessions: 342</Card>\n"
                "      </div>\n"
                "      <Card className='mt-6 p-6 h-64'>\n"
                "        <h2>Traffic (7d)</h2>\n"
                "        <svg viewBox='0 0 400 150' className='w-full h-full'>\n"
                "          <polyline fill='none' stroke='currentColor' strokeWidth='2'\n"
                "            points='0,100 50,80 100,90 150,60 200,70 250,40 300,50 350,30 400,20' />\n"
                "        </svg>\n"
                "      </Card>\n"
                "    </div>"
            ),
        }),
        _tool_resp("file_edit", "added chart component"),
        _tool_call("shell_exec", {"command": "cd workspace/deliverables/stats-dash && npm run build"}),
        _tool_resp("shell_exec", "✓ built in 1.0s"),
        _tool_call("undertow", {"path": "workspace/deliverables/stats-dash/dist/index.html"}),
        _tool_resp("undertow", "PASS: screenshot describes 'a dashboard with a title, three stat cards in a grid, and a line chart below showing traffic over 7 days.' All requested elements present."),
        _tool_call("message_result", {"text": "Dashboard built with header, three stat cards, and a traffic line chart."}),
    ]


# ---------------------------------------------------------------------------
# V08 — Undertow FAIL: console error → file_edit to fix import
# ---------------------------------------------------------------------------
def v08_undertow_fail_console_error():
    return [
        _sys(),
        _user("Build a form that accepts email and shows a confirmation message on submit."),
        _tool_call("project_init", {"name": "email-form"}),
        _tool_resp("project_init", "Created workspace/deliverables/email-form/."),
        _tool_call("file_write", {
            "path": "workspace/deliverables/email-form/src/App.tsx",
            "content": (
                "import { Button, Input } from './components/ui';\n"
                "export default function App() {\n"
                "  const [email, setEmail] = useState('');\n"
                "  const [sent, setSent] = useState(false);\n"
                "  return (\n"
                "    <form className='p-8' onSubmit={e => { e.preventDefault(); setSent(true); }}>\n"
                "      <Input value={email} onChange={e => setEmail(e.target.value)} placeholder='Email' />\n"
                "      <Button type='submit' className='ml-2'>Submit</Button>\n"
                "      {sent && <p className='mt-4 text-green-600'>Thanks, we'll be in touch.</p>}\n"
                "    </form>\n"
                "  );\n"
                "}\n"
            )}),
        _tool_resp("file_write", "wrote 440 bytes"),
        _tool_call("shell_exec", {"command": "cd workspace/deliverables/email-form && npm run build"}),
        _tool_resp("shell_exec", "✓ built in 0.8s (no errors)"),
        _tool_call("undertow", {"path": "workspace/deliverables/email-form/dist/index.html"}),
        _tool_resp("undertow", "FAIL: console error on page load — 'ReferenceError: useState is not defined'. Screen is blank."),
        _tool_call("file_edit", {
            "path": "workspace/deliverables/email-form/src/App.tsx",
            "old_text": "import { Button, Input } from './components/ui';",
            "new_text": "import { Button, Input } from './components/ui';\nimport { useState } from 'react';",
        }),
        _tool_resp("file_edit", "added useState import"),
        _tool_call("shell_exec", {"command": "cd workspace/deliverables/email-form && npm run build"}),
        _tool_resp("shell_exec", "✓ built in 0.8s"),
        _tool_call("undertow", {"path": "workspace/deliverables/email-form/dist/index.html"}),
        _tool_resp("undertow", "PASS: form renders with email input and submit button. Typed 'a@b.com' and submitted — green confirmation message appeared. No console errors."),
        _tool_call("message_result", {"text": "Email form built — accepts input, submits without page reload, shows confirmation."}),
    ]


# ---------------------------------------------------------------------------
# V09 — Undertow FAIL: VLM detects placeholder content → file_edit to replace
# ---------------------------------------------------------------------------
def v09_undertow_fail_placeholder_detected():
    return [
        _sys(),
        _user("Build a personal blog landing page with a 'Latest Posts' section showing 3 recent posts."),
        _tool_call("project_init", {"name": "blog-landing"}),
        _tool_resp("project_init", "Created workspace/deliverables/blog-landing/."),
        _tool_call("file_write", {
            "path": "workspace/deliverables/blog-landing/src/App.tsx",
            "content": (
                "import { Card } from './components/ui';\n"
                "export default function App() {\n"
                "  return (\n"
                "    <div className='p-8 max-w-4xl mx-auto'>\n"
                "      <h1 className='text-5xl font-bold mb-8'>My Blog</h1>\n"
                "      <h2 className='text-2xl mb-4'>Latest Posts</h2>\n"
                "      <Card>TODO: Add posts here</Card>\n"
                "    </div>\n"
                "  );\n"
                "}\n"
            )}),
        _tool_resp("file_write", "wrote 280 bytes"),
        _tool_call("shell_exec", {"command": "cd workspace/deliverables/blog-landing && npm run build"}),
        _tool_resp("shell_exec", "✓ built in 0.8s"),
        _tool_call("undertow", {"path": "workspace/deliverables/blog-landing/dist/index.html"}),
        _tool_resp("undertow", "FAIL: screenshot shows 'TODO: Add posts here' as visible text. This is a placeholder stub — the user asked for 3 recent posts, the page should show 3 post cards with title + excerpt."),
        _tool_call("file_edit", {
            "path": "workspace/deliverables/blog-landing/src/App.tsx",
            "old_text": "      <Card>TODO: Add posts here</Card>",
            "new_text": (
                "      <div className='grid gap-4'>\n"
                "        <Card className='p-4'>\n"
                "          <h3 className='text-xl font-semibold'>Building in public</h3>\n"
                "          <p className='text-sm text-slate-500'>2026-04-10</p>\n"
                "          <p className='mt-2'>Notes on shipping a small tool every week, the friction I run into, and what users actually ask for.</p>\n"
                "        </Card>\n"
                "        <Card className='p-4'>\n"
                "          <h3 className='text-xl font-semibold'>Why fewer tools</h3>\n"
                "          <p className='text-sm text-slate-500'>2026-04-05</p>\n"
                "          <p className='mt-2'>The temptation to add options is strong. Removing a tool usually beats adding one.</p>\n"
                "        </Card>\n"
                "        <Card className='p-4'>\n"
                "          <h3 className='text-xl font-semibold'>Local models, honest claims</h3>\n"
                "          <p className='text-sm text-slate-500'>2026-04-01</p>\n"
                "          <p className='mt-2'>What a 4B model can actually do well, and where it needs help from vision.</p>\n"
                "        </Card>\n"
                "      </div>"
            ),
        }),
        _tool_resp("file_edit", "replaced placeholder with 3 post cards"),
        _tool_call("shell_exec", {"command": "cd workspace/deliverables/blog-landing && npm run build"}),
        _tool_resp("shell_exec", "✓ built in 0.8s"),
        _tool_call("undertow", {"path": "workspace/deliverables/blog-landing/dist/index.html"}),
        _tool_resp("undertow", "PASS: screenshot shows 'My Blog' header with 'Latest Posts' section containing 3 post cards — each with title, date, and excerpt."),
        _tool_call("message_result", {"text": "Blog landing built with 3 latest post cards showing title, date, and excerpt."}),
    ]


def main():
    print(f"Loading: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)

    examples = []
    for fn in [v01_clone_from_screenshot,
               v02_research_clone,
               v03_generated_reference,
               v04_undertow_catches_placeholder,
               v05_iterative_fix,
               v06_undertow_fail_missing_handler,
               v07_undertow_fail_missing_element,
               v08_undertow_fail_console_error,
               v09_undertow_fail_placeholder_detected]:
        msgs = fn()
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})
        print(f"  rendered {fn.__name__} ({len(text)} chars)")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')
    print(f"\nWrote: {OUT_PATH} — {len(examples)} examples")

    # Verify riptide + generate_image + undertow presence
    import re
    with open(OUT_PATH) as f:
        text_all = f.read()
    for t in ['riptide', 'undertow', 'generate_image', 'search_web', 'file_edit', 'message_chat']:
        n = len(re.findall(rf'call:{t}\b', text_all))
        print(f"  call:{t}: {n}")


if __name__ == '__main__':
    main()
