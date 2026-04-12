#!/usr/bin/env python3
"""Landing-page DPO pairs v1 — 18 pairs targeting L4 Hack-Free failures.

LAF01: landing template — project_init(template="landing") not bare/react-app
LAF02: scaffold nav — import Navbar from './components/Navbar' not raw <nav> div
LAF03: Hero component — <Hero title="" subtitle="" cta={{}} /> not raw <section>
LAF04: FeatureGrid component — <FeatureGrid features={[...]} /> not manual <div className="grid">
LAF05: undertow before deliver — undertow QA BEFORE message_result
LAF06: no main.tsx overwrite — file_write(src/App.tsx) not file_write(src/main.tsx)

Usage:
  /usr/bin/python3 training/build_landing_dpo_v1.py
  Output: workspace/training_data/landing_dpo_v1.jsonl
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
    "- NEVER fetch() for copy/content — hardcode in App.tsx\n"
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
    {"type": "function", "function": {"name": "file_read", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]

GOOD_APP = '''import Navbar from './components/Navbar';
import Hero from './components/Hero';
import FeatureGrid from './components/FeatureGrid';
import CTASection from './components/CTASection';
import Footer from './components/Footer';

const FEATURES = [
  { title: 'Fast', description: 'Deploy in seconds with zero config.', icon: '⚡' },
  { title: 'Secure', description: 'Enterprise-grade security built in.', icon: '🛡️' },
  { title: 'Scalable', description: 'Grows from zero to millions of users.', icon: '📈' },
];

export default function App() {
  return (
    <>
      <Navbar brand="Acme" links={[{ label: 'Features', href: '#features' }, { label: 'Pricing', href: '#pricing' }]} cta={{ label: 'Get Started', href: '#cta' }} />
      <Hero title="The future of B2B SaaS" subtitle="Acme helps enterprise teams collaborate faster." cta={{ label: 'Start Free Trial', href: '#cta' }} />
      <section id="features" style={{ padding: '80px 0' }}>
        <FeatureGrid features={FEATURES} columns={3} />
      </section>
      <CTASection id="cta" title="Ready to get started?" subtitle="No credit card required." buttonLabel="Start Free Trial" buttonHref="#" />
      <Footer brand="Acme" links={[{ label: 'Privacy', href: '#' }, { label: 'Terms', href: '#' }]} />
    </>
  );
}
'''

BAD_RAW_APP = '''export default function App() {
  return (
    <div style={{ background: '#0a0e17', color: '#fff', minHeight: '100vh' }}>
      <nav style={{ padding: '16px 32px', display: 'flex', justifyContent: 'space-between' }}>
        <h1>Acme</h1>
        <a href="#" style={{ color: '#4a9eff' }}>Get Started</a>
      </nav>
      <section style={{ textAlign: 'center', padding: '120px 32px' }}>
        <h2 style={{ fontSize: 48 }}>The future of B2B SaaS</h2>
        <p style={{ fontSize: 20, color: '#a0aec0' }}>Acme helps enterprise teams collaborate faster.</p>
        <button style={{ padding: '14px 32px', background: '#4a9eff', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer' }}>Start Free Trial</button>
      </section>
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24, maxWidth: 900, margin: '0 auto', padding: '0 32px 80px' }}>
        <div style={{ background: '#141922', borderRadius: 12, padding: 24 }}><h3>Fast</h3><p>Deploy in seconds with zero config.</p></div>
        <div style={{ background: '#141922', borderRadius: 12, padding: 24 }}><h3>Secure</h3><p>Enterprise-grade security built in.</p></div>
        <div style={{ background: '#141922', borderRadius: 12, padding: 24 }}><h3>Scalable</h3><p>Grows from zero to millions.</p></div>
      </section>
      <footer style={{ textAlign: 'center', padding: 24, borderTop: '1px solid #2d3748' }}>© 2026 Acme</footer>
    </div>
  );
}
'''

BAD_FETCH_APP = '''import { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Hero from './components/Hero';

export default function App() {
  const [content, setContent] = useState<any>(null);

  useEffect(() => {
    fetch('/api/landing-content').then(r => r.json()).then(setContent);
  }, []);

  if (!content) return <div>Loading...</div>;

  return (
    <>
      <Navbar brand={content.brand} links={content.navLinks} />
      <Hero title={content.hero.title} subtitle={content.hero.subtitle} cta={content.hero.cta} />
    </>
  );
}
'''

def tc(tool_name, **kwargs):
    return {"role": "assistant", "content": None, "tool_calls": [{"id": f"call_{tool_name}", "type": "function", "function": {"name": tool_name, "arguments": json.dumps(kwargs)}}]}

def tr(tool_name, result):
    return {"role": "tool", "tool_call_id": f"call_{tool_name}", "name": tool_name, "content": json.dumps({"result": result})}

def tok(msgs):
    return tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)

pairs = []

PROMPT_SAAS = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Build a landing page for Acme, a B2B SaaS startup."}]
PROMPT_PORTFOLIO = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Build a portfolio landing page for a developer."}]
PROMPT_DELIVER = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build a landing page for Acme."},
    tc("project_init", name="acme-landing", template="landing"),
    tr("project_init", "Created. landing scaffold ready."),
    tc("file_write", path="src/App.tsx", content=GOOD_APP),
    tr("file_write", "Written."),
    tc("shell_exec", command="cd workspace/deliverables/acme-landing && npm run build 2>&1 | tail -3"),
    tr("shell_exec", "✓ built in 2.0s"),
]

# LAF01 x3: landing template
for i, (chosen_tmpl, rejected_tmpl) in enumerate([
    ("landing", "react-app"),
    ("landing", ""),
    ("landing", "fullstack"),
], 1):
    chosen = tc("project_init", name="landing-page", template=chosen_tmpl)
    rejected = tc("project_init", name="landing-page", **({} if not rejected_tmpl else {"template": rejected_tmpl}))
    pairs.append({
        "prompt": tok(PROMPT_SAAS),
        "chosen": tok(PROMPT_SAAS + [chosen]),
        "rejected": tok(PROMPT_SAAS + [rejected]),
        "source_bug": f"LAF01-{i}", "note": f"landing template: {chosen_tmpl!r} vs {rejected_tmpl!r}", "images": [], "date": TODAY,
    })

# LAF02 x3: scaffold components not raw divs
pre = PROMPT_SAAS + [tc("project_init", name="acme-landing", template="landing"), tr("project_init", "Created. landing scaffold ready.")]
pairs.append({
    "prompt": tok(pre),
    "chosen": tok(pre + [tc("file_write", path="src/App.tsx", content=GOOD_APP)]),
    "rejected": tok(pre + [tc("file_write", path="src/App.tsx", content=BAD_RAW_APP)]),
    "source_bug": "LAF02-1", "note": "import scaffold components not raw divs", "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tok(pre),
    "chosen": tok(pre + [tc("file_write", path="src/App.tsx", content=GOOD_APP)]),
    "rejected": tok(pre + [tc("file_write", path="src/App.tsx", content=BAD_RAW_APP)]),
    "source_bug": "LAF02-2", "note": "Navbar component not <nav> element", "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tok(pre),
    "chosen": tok(pre + [tc("file_write", path="src/App.tsx", content=GOOD_APP)]),
    "rejected": tok(pre + [tc("file_write", path="src/App.tsx", content=BAD_FETCH_APP)]),
    "source_bug": "LAF02-3", "note": "no fetch() for marketing copy — hardcode in App.tsx", "images": [], "date": TODAY,
})

# LAF03 x3: Hero component not raw section
pre_port = PROMPT_PORTFOLIO + [tc("project_init", name="portfolio", template="landing"), tr("project_init", "Created.")]
pairs.append({
    "prompt": tok(pre_port),
    "chosen": tok(pre_port + [tc("file_write", path="src/App.tsx", content=GOOD_APP.replace("B2B SaaS", "Portfolio"))]),
    "rejected": tok(pre_port + [tc("file_write", path="src/App.tsx", content=BAD_RAW_APP)]),
    "source_bug": "LAF03-1", "note": "<Hero> not raw <section><h2>", "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tok(pre),
    "chosen": tok(pre + [tc("file_write", path="src/App.tsx", content=GOOD_APP)]),
    "rejected": tok(pre + [tc("file_write", path="src/App.tsx", content=BAD_RAW_APP)]),
    "source_bug": "LAF03-2", "note": "Hero props: title, subtitle, cta — not inline styles", "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tok(pre),
    "chosen": tok(pre + [tc("file_write", path="src/App.tsx", content=GOOD_APP)]),
    "rejected": tok(pre + [tc("file_write", path="src/App.tsx", content=BAD_RAW_APP)]),
    "source_bug": "LAF03-3", "note": "CTASection component not raw button+section", "images": [], "date": TODAY,
})

# LAF04 x3: FeatureGrid not manual grid
pairs.append({
    "prompt": tok(pre),
    "chosen": tok(pre + [tc("file_write", path="src/App.tsx", content=GOOD_APP)]),
    "rejected": tok(pre + [tc("file_write", path="src/App.tsx", content=BAD_RAW_APP)]),
    "source_bug": "LAF04-1", "note": "<FeatureGrid features={[...]} /> not manual grid divs", "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tok(pre),
    "chosen": tok(pre + [tc("file_write", path="src/App.tsx", content=GOOD_APP)]),
    "rejected": tok(pre + [tc("file_write", path="src/App.tsx", content=BAD_RAW_APP)]),
    "source_bug": "LAF04-2", "note": "FeatureGrid columns prop not CSS grid hack", "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tok(pre),
    "chosen": tok(pre + [tc("file_write", path="src/App.tsx", content=GOOD_APP)]),
    "rejected": tok(pre + [tc("file_write", path="src/App.tsx", content=BAD_RAW_APP)]),
    "source_bug": "LAF04-3", "note": "Footer component not raw footer div", "images": [], "date": TODAY,
})

# LAF05 x3: undertow before deliver
chosen_undertow = tc("undertow", path="workspace/deliverables/acme-landing/dist/index.html")
pairs.append({
    "prompt": tok(PROMPT_DELIVER),
    "chosen": tok(PROMPT_DELIVER + [chosen_undertow]),
    "rejected": tok(PROMPT_DELIVER + [tc("message_result")]),
    "source_bug": "LAF05-1", "note": "undertow before message_result", "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tok(PROMPT_DELIVER),
    "chosen": tok(PROMPT_DELIVER + [chosen_undertow]),
    "rejected": tok(PROMPT_DELIVER + [tc("message_chat", text="Landing page is ready!", done=True)]),
    "source_bug": "LAF05-2", "note": "undertow not message_chat to deliver", "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tok(PROMPT_DELIVER),
    "chosen": tok(PROMPT_DELIVER + [chosen_undertow]),
    "rejected": tok(PROMPT_DELIVER + [tc("message_result")]),
    "source_bug": "LAF05-3", "note": "always QA before result", "images": [], "date": TODAY,
})

# LAF06 x3: no main.tsx overwrite
pre_init = PROMPT_SAAS + [tc("project_init", name="acme-landing", template="landing"), tr("project_init", "Created.")]
pairs.append({
    "prompt": tok(pre_init),
    "chosen": tok(pre_init + [tc("file_write", path="src/App.tsx", content=GOOD_APP)]),
    "rejected": tok(pre_init + [tc("file_write", path="src/main.tsx", content="import App from './App'; ReactDOM.render(<App />, document.getElementById('root'));")]),
    "source_bug": "LAF06-1", "note": "write src/App.tsx not src/main.tsx", "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tok(pre_init),
    "chosen": tok(pre_init + [tc("file_write", path="src/App.tsx", content=GOOD_APP)]),
    "rejected": tok(pre_init + [tc("file_write", path="vite.config.ts", content="export default { plugins: [] }")]),
    "source_bug": "LAF06-2", "note": "write src/App.tsx not vite.config.ts", "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tok(pre_init),
    "chosen": tok(pre_init + [tc("file_write", path="src/App.tsx", content=GOOD_APP)]),
    "rejected": tok(pre_init + [tc("file_write", path="index.html", content="<!DOCTYPE html>")]),
    "source_bug": "LAF06-3", "note": "write src/App.tsx not index.html", "images": [], "date": TODAY,
})

out_path = Path("workspace/training_data/landing_dpo_v1.jsonl")
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w") as f:
    for p in pairs:
        f.write(json.dumps(p) + "\n")

print(f"\n=== LANDING DPO v1 SUMMARY ===")
print(f"  Pairs: {len(pairs)}")
print(f"  Output: {out_path}")
by_bug = {}
for p in pairs:
    key = p["source_bug"].rsplit("-", 1)[0]
    by_bug[key] = by_bug.get(key, 0) + 1
for k, v in sorted(by_bug.items()):
    print(f"  {k}: {v} pairs")
