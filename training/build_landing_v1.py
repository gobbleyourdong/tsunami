#!/usr/bin/env python3
"""Landing-page SFT examples v1 — 6 training examples for the landing-page adapter.

Uses scaffolds/landing/ (Vite + React + Navbar + Hero + FeatureGrid + CTASection + Footer).
Pipeline: project_init(template="landing") → file_write(src/App.tsx) → build → undertow → result.

LA01: SaaS landing — Navbar + Hero + FeatureGrid + CTASection + Footer
LA02: Portfolio page — Hero + PortfolioGrid + Footer
LA03: Product launch — ParallaxHero + StatsRow + Testimonials + CTASection
LA04: Coming soon — Hero + CTASection (email capture)
LA05: Error recovery — raw divs → scaffold components
LA06: Conversational routing — capability explanation

Usage:
  /usr/bin/python3 training/build_landing_v1.py
  Output: workspace/training_data/landing_sft_v1.jsonl
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
    "- undertow: QA. ALWAYS verify before delivering.\n"
    "- break: compile. shell_exec build after EVERY file_write.\n"
    "- reef: error. Fix directly.\n\n"
    "LANDING-PAGE PIPELINE (marketing / portfolio / product pages follow this EXACTLY):\n"
    "1. project_init(name, template='landing')\n"
    "2. file_write(src/App.tsx) -- import Navbar, Hero, FeatureGrid, CTASection, Footer, etc.\n"
    "3. shell_exec -- npm run build\n"
    "4. IF ERROR: fix directly\n"
    "5. undertow -- QA before delivery\n"
    "6. message_result -- land the wave\n\n"
    "LANDING RULES:\n"
    "- ALWAYS template='landing' in project_init\n"
    "- ALWAYS import scaffold components: Navbar, Hero, FeatureGrid, CTASection, Footer\n"
    "- NEVER build a raw <nav>/<section>/<footer> instead of the scaffold components\n"
    "- NEVER fetch() for marketing content -- all copy is hardcoded in App.tsx\n"
    "- NEVER overwrite main.tsx, vite.config.ts, or index.css\n"
    "- NEVER skip undertow before message_result\n\n"
    "NEVER skip the break. NEVER deliver without building. One tool call per response. Be brief."
)

TOOLS = [
    {"type": "function", "function": {"name": "project_init", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "template": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "message_result", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "search_web", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "undertow", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "file_read", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]

LA01_APP = '''import Navbar from './components/Navbar';
import Hero from './components/Hero';
import FeatureGrid from './components/FeatureGrid';
import CTASection from './components/CTASection';
import Footer from './components/Footer';

const FEATURES = [
  { title: 'Ship Faster', description: 'Auto-scaffold any app in seconds. No boilerplate, no config.', icon: '🚀' },
  { title: 'AI-Powered', description: 'Intelligent code generation that learns from your patterns.', icon: '🤖' },
  { title: 'Full-Stack Ready', description: 'React + Express + SQLite out of the box. One command.', icon: '🔧' },
  { title: 'Deploy Anywhere', description: 'Export to Docker, Vercel, or bare metal — your choice.', icon: '☁️' },
  { title: 'Type Safe', description: 'End-to-end TypeScript with strict mode. Zero runtime surprises.', icon: '🛡️' },
  { title: 'Open Source', description: 'MIT licensed. Fork it, extend it, own it.', icon: '🌐' },
];

export default function App() {
  return (
    <>
      <Navbar
        brand="Tsunami"
        links={[
          { label: 'Features', href: '#features' },
          { label: 'Docs', href: '#docs' },
          { label: 'Pricing', href: '#pricing' },
        ]}
        cta={{ label: 'Get Started', href: '#cta' }}
      />

      <Hero
        title="Build web apps at the speed of thought"
        subtitle="Tsunami scaffolds, codes, and ships production-ready React apps — guided by AI, powered by your intent."
        cta={{ label: 'Start for free', href: '#cta' }}
        gradient="radial-gradient(ellipse at 60% 0%, #0d2a4e 0%, #0a0e17 60%)"
      />

      <section id="features" style={{ padding: '80px 0' }}>
        <FeatureGrid features={FEATURES} columns={3} />
      </section>

      <CTASection
        id="cta"
        title="Ready to ride the wave?"
        subtitle="Join thousands of developers shipping faster with Tsunami."
        buttonLabel="Start Building Free"
        buttonHref="https://tsunami.dev/signup"
      />

      <Footer
        brand="Tsunami"
        links={[
          { label: 'Docs', href: '#' },
          { label: 'GitHub', href: '#' },
          { label: 'Privacy', href: '#' },
          { label: 'Terms', href: '#' },
        ]}
      />
    </>
  );
}
'''

LA02_APP = '''import Hero from './components/Hero';
import PortfolioGrid from './components/PortfolioGrid';
import Footer from './components/Footer';

const PROJECTS = [
  { title: 'E-Commerce Platform', description: 'Full-stack React + Node + Stripe integration for 50k monthly orders.', tags: ['React', 'Node.js', 'Stripe'], image: '', href: '#' },
  { title: 'Real-Time Dashboard', description: 'WebSocket-powered analytics for live IoT sensor data.', tags: ['WebSocket', 'D3.js', 'AWS'], image: '', href: '#' },
  { title: 'Mobile App', description: 'Cross-platform React Native app — 4.8 stars, 100k+ downloads.', tags: ['React Native', 'Firebase', 'Redux'], image: '', href: '#' },
  { title: 'AI Writing Tool', description: 'GPT-4 powered writing assistant with custom fine-tuning pipeline.', tags: ['Python', 'OpenAI', 'FastAPI'], image: '', href: '#' },
  { title: 'DevOps Automation', description: 'CI/CD pipeline that reduced deploy time from 45min to 4min.', tags: ['Kubernetes', 'Terraform', 'GitHub Actions'], image: '', href: '#' },
  { title: 'Open Source CLI', description: 'Rust CLI tool with 2k GitHub stars for developer productivity.', tags: ['Rust', 'CLI', 'Open Source'], image: '', href: '#' },
];

export default function App() {
  return (
    <>
      <Hero
        title="Alex Chen — Full-Stack Engineer"
        subtitle="I build performant, user-centric web and mobile applications. 8 years shipping products used by millions."
        cta={{ label: 'Get in touch', href: 'mailto:alex@example.com' }}
      />

      <section style={{ padding: '80px 32px', maxWidth: 1200, margin: '0 auto' }}>
        <h2 style={{ textAlign: 'center', marginBottom: 48, fontSize: 32 }}>Selected Work</h2>
        <PortfolioGrid items={PROJECTS} />
      </section>

      <Footer
        brand="Alex Chen"
        links={[
          { label: 'GitHub', href: 'https://github.com' },
          { label: 'LinkedIn', href: 'https://linkedin.com' },
          { label: 'Resume', href: '#' },
        ]}
      />
    </>
  );
}
'''

LA03_APP = '''import ParallaxHero from './components/ParallaxHero';
import StatsRow from './components/StatsRow';
import Testimonials from './components/Testimonials';
import CTASection from './components/CTASection';
import Footer from './components/Footer';

const STATS = [
  { value: '4.9', label: 'App Store Rating', suffix: '★' },
  { value: '250', label: 'Active Users', suffix: 'K+' },
  { value: '98', label: 'Uptime SLA', suffix: '%' },
  { value: '< 50', label: 'Avg Response', suffix: 'ms' },
];

const TESTIMONIALS = [
  { name: 'Sarah M.', role: 'Product Manager @ Stripe', body: 'Switched our whole team to Orbit. The offline sync alone saved us hours per week.', avatar: '' },
  { name: 'James K.', role: 'Founder @ YC W24', body: "We shipped our MVP in 3 days using Orbit's scaffolding. Couldn't recommend it more.", avatar: '' },
  { name: 'Priya N.', role: 'iOS Lead @ Shopify', body: 'Best mobile app tooling I\'ve used in 10 years. The DX is miles ahead of the competition.', avatar: '' },
];

export default function App() {
  return (
    <>
      <ParallaxHero
        title="Orbit — Work, synced."
        subtitle="The mobile-first productivity app that works everywhere, even offline. Available on iOS and Android."
        cta={{ label: 'Download Free', href: '#download' }}
        backgroundImage=""
      />

      <section style={{ padding: '64px 0', background: 'var(--surface)' }}>
        <StatsRow stats={STATS} />
      </section>

      <section style={{ padding: '80px 32px', maxWidth: 1000, margin: '0 auto' }}>
        <h2 style={{ textAlign: 'center', marginBottom: 48, fontSize: 32 }}>What users are saying</h2>
        <Testimonials items={TESTIMONIALS} />
      </section>

      <CTASection
        id="download"
        title="Start for free today"
        subtitle="No credit card required. Cancel anytime."
        buttonLabel="Download Orbit"
        buttonHref="https://apps.apple.com"
      />

      <Footer brand="Orbit" links={[{ label: 'Privacy', href: '#' }, { label: 'Terms', href: '#' }, { label: 'Support', href: '#' }]} />
    </>
  );
}
'''

LA04_APP = '''import Hero from './components/Hero';
import CTASection from './components/CTASection';
import Footer from './components/Footer';
import { useState } from 'react';

export default function App() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);

  return (
    <>
      <Hero
        title="Something big is coming."
        subtitle="We're building the next generation developer tool. Be the first to know when we launch."
        gradient="radial-gradient(ellipse at 50% 30%, #1a0a3e 0%, #0a0e17 60%)"
      >
        <div style={{ marginTop: 32, display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
          {submitted ? (
            <p style={{ color: 'var(--accent)', fontSize: 18 }}>✓ You're on the list — we'll be in touch!</p>
          ) : (
            <>
              <input
                type="email"
                placeholder="your@email.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                style={{ padding: '10px 16px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)', fontSize: 16, minWidth: 260 }}
              />
              <button
                onClick={() => email.includes('@') && setSubmitted(true)}
                style={{ padding: '10px 24px', borderRadius: 8, background: 'var(--accent)', color: '#fff', border: 'none', cursor: 'pointer', fontSize: 16, fontWeight: 600 }}
              >
                Notify Me
              </button>
            </>
          )}
        </div>
      </Hero>

      <CTASection
        title="Launching Q3 2026"
        subtitle="Follow our progress — we ship in the open."
        buttonLabel="Follow on X"
        buttonHref="https://x.com"
      />

      <Footer brand="SomethingBig" links={[{ label: 'Blog', href: '#' }, { label: 'Contact', href: '#' }]} />
    </>
  );
}
'''

LA05_BAD_APP = '''export default function App() {
  return (
    <div style={{ fontFamily: 'sans-serif', background: '#0a0e17', color: '#fff', minHeight: '100vh' }}>
      <nav style={{ padding: '16px 32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ margin: 0, fontSize: 24 }}>Acme Corp</h1>
        <a href="#" style={{ color: '#4a9eff', textDecoration: 'none' }}>Get Started</a>
      </nav>
      <section style={{ textAlign: 'center', padding: '120px 32px' }}>
        <h2 style={{ fontSize: 48 }}>The future of work</h2>
        <p style={{ fontSize: 20, color: '#a0aec0' }}>Acme makes your team more productive, together.</p>
        <button style={{ padding: '14px 32px', background: '#4a9eff', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 18 }}>Start Free Trial</button>
      </section>
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24, maxWidth: 900, margin: '0 auto', padding: '0 32px 80px' }}>
        <div style={{ background: '#141922', borderRadius: 12, padding: 24 }}><h3>Fast</h3><p>Deploy in seconds</p></div>
        <div style={{ background: '#141922', borderRadius: 12, padding: 24 }}><h3>Secure</h3><p>Enterprise-grade</p></div>
        <div style={{ background: '#141922', borderRadius: 12, padding: 24 }}><h3>Scale</h3><p>Grows with you</p></div>
      </section>
      <footer style={{ textAlign: 'center', padding: 24, borderTop: '1px solid #2d3748', color: '#718096' }}>
        © 2026 Acme Corp
      </footer>
    </div>
  );
}
'''

def tc(tool_name, **kwargs):
    return {"role": "assistant", "content": None, "tool_calls": [{"id": f"call_{tool_name}", "type": "function", "function": {"name": tool_name, "arguments": json.dumps(kwargs)}}]}

def tr(tool_name, result):
    return {"role": "tool", "tool_call_id": f"call_{tool_name}", "name": tool_name, "content": json.dumps({"result": result})}

examples = []

# LA01: SaaS landing
la01 = [
    {"role": "user", "content": "Build a landing page for my developer tool startup 'Tsunami'. Needs a hero, features section, CTA, and footer."},
    tc("project_init", name="tsunami-landing", template="landing"),
    tr("project_init", "Project 'tsunami-landing' created. landing scaffold with Navbar, Hero, FeatureGrid, CTASection, Footer, ParallaxHero, Testimonials, StatsRow, PortfolioGrid components ready."),
    tc("file_write", path="src/App.tsx", content=LA01_APP),
    tr("file_write", "Written: src/App.tsx"),
    tc("shell_exec", command="cd workspace/deliverables/tsunami-landing && npm run build 2>&1 | tail -5"),
    tr("shell_exec", "dist/index.html 1.8kB\ndist/assets/index-BxKp9q1a.js 184.2kB\n✓ built in 2.1s"),
    tc("undertow", path="workspace/deliverables/tsunami-landing/dist/index.html"),
    tr("undertow", "PASS: Navbar with links visible. Hero title present. FeatureGrid shows 6 cards. CTASection with button. Footer with links."),
    tc("message_result"),
    tr("message_result", "delivered"),
]
examples.append({"source": "LA01-saas-landing", "messages": la01, "date": TODAY})

# LA02: Portfolio
la02 = [
    {"role": "user", "content": "Build a portfolio site for a software engineer named Alex Chen. Show projects in a grid, hero intro, and footer with social links."},
    tc("project_init", name="alex-portfolio", template="landing"),
    tr("project_init", "Project 'alex-portfolio' created. landing scaffold ready."),
    tc("file_write", path="src/App.tsx", content=LA02_APP),
    tr("file_write", "Written: src/App.tsx"),
    tc("shell_exec", command="cd workspace/deliverables/alex-portfolio && npm run build 2>&1 | tail -5"),
    tr("shell_exec", "dist/index.html 1.6kB\ndist/assets/index-CyMp3r2b.js 177.3kB\n✓ built in 1.9s"),
    tc("undertow", path="workspace/deliverables/alex-portfolio/dist/index.html"),
    tr("undertow", "PASS: Hero title shows name. PortfolioGrid shows 6 project cards with tags. Footer with social links."),
    tc("message_result"),
    tr("message_result", "delivered"),
]
examples.append({"source": "LA02-portfolio", "messages": la02, "date": TODAY})

# LA03: Product launch with stats + testimonials
la03 = [
    {"role": "user", "content": "Build a product launch page for 'Orbit', a mobile productivity app. Include stats, testimonials, a download CTA."},
    tc("project_init", name="orbit-launch", template="landing"),
    tr("project_init", "Project 'orbit-launch' created. landing scaffold ready."),
    tc("file_write", path="src/App.tsx", content=LA03_APP),
    tr("file_write", "Written: src/App.tsx"),
    tc("shell_exec", command="cd workspace/deliverables/orbit-launch && npm run build 2>&1 | tail -5"),
    tr("shell_exec", "dist/index.html 1.7kB\ndist/assets/index-DzQp1s3c.js 192.1kB\n✓ built in 2.0s"),
    tc("undertow", path="workspace/deliverables/orbit-launch/dist/index.html"),
    tr("undertow", "PASS: ParallaxHero visible. StatsRow shows 4 stats. Testimonials section with 3 cards. CTASection download button."),
    tc("message_result"),
    tr("message_result", "delivered"),
]
examples.append({"source": "LA03-product-launch", "messages": la03, "date": TODAY})

# LA04: Coming soon
la04 = [
    {"role": "user", "content": "Build a coming soon page for a developer tool called 'SomethingBig'. Collect email signups, show launch date Q3 2026."},
    tc("project_init", name="coming-soon", template="landing"),
    tr("project_init", "Project 'coming-soon' created. landing scaffold ready."),
    tc("file_write", path="src/App.tsx", content=LA04_APP),
    tr("file_write", "Written: src/App.tsx"),
    tc("shell_exec", command="cd workspace/deliverables/coming-soon && npm run build 2>&1 | tail -5"),
    tr("shell_exec", "dist/index.html 1.4kB\ndist/assets/index-EzQm2t4d.js 159.8kB\n✓ built in 1.8s"),
    tc("undertow", path="workspace/deliverables/coming-soon/dist/index.html"),
    tr("undertow", "PASS: Hero with email input visible. Submit button present. CTASection shows launch date. Footer visible."),
    tc("message_result"),
    tr("message_result", "delivered"),
]
examples.append({"source": "LA04-coming-soon", "messages": la04, "date": TODAY})

# LA05: Error recovery — raw divs → scaffold components
la05 = [
    {"role": "user", "content": "Build a landing page for a B2B SaaS called 'Acme Corp'."},
    tc("project_init", name="acme-landing", template="landing"),
    tr("project_init", "Project 'acme-landing' created. landing scaffold ready."),
    tc("file_write", path="src/App.tsx", content=LA05_BAD_APP),
    tr("file_write", "Written: src/App.tsx. WARNING: App.tsx is not using the scaffold components (Navbar, Hero, FeatureGrid, CTASection, Footer). Import and use these instead of raw <nav>, <section>, <footer> divs."),
    # Recovery: fix to scaffold components
    tc("file_write", path="src/App.tsx", content=LA01_APP.replace("Tsunami", "Acme Corp").replace("tsunami.dev", "acmecorp.com").replace("Build web apps at the speed of thought", "Enterprise productivity, reimagined").replace("Tsunami scaffolds, codes, and ships production-ready React apps — guided by AI, powered by your intent.", "Acme Corp helps enterprise teams collaborate, automate, and deliver — faster than ever before.")),
    tr("file_write", "Written: src/App.tsx"),
    tc("shell_exec", command="cd workspace/deliverables/acme-landing && npm run build 2>&1 | tail -5"),
    tr("shell_exec", "dist/index.html 1.8kB\ndist/assets/index-FxQn3u5e.js 183.9kB\n✓ built in 2.0s"),
    tc("undertow", path="workspace/deliverables/acme-landing/dist/index.html"),
    tr("undertow", "PASS: Navbar component used. Hero component with title. FeatureGrid with cards. CTASection. Footer. Scaffold components correctly imported."),
    tc("message_result"),
    tr("message_result", "delivered"),
]
examples.append({"source": "LA05-error-recovery", "messages": la05, "date": TODAY})

# LA06: Conversational
la06 = [
    {"role": "user", "content": "What kinds of landing pages can you build?"},
    tc("message_chat", text="I build landing pages with pre-built scaffold components:\n\n• **Navbar** — responsive nav with brand, links, mobile menu\n• **Hero** — large headline, subtitle, CTA button with gradient background\n• **ParallaxHero** — hero with parallax scroll effect\n• **FeatureGrid** — animated 2/3/4-column feature cards with scroll-trigger\n• **StatsRow** — horizontal stats (users, uptime, ratings)\n• **Testimonials** — customer quote cards\n• **PortfolioGrid** — project showcase with tags\n• **CTASection** — conversion section with glassmorphism effect\n• **Footer** — links + social icons\n\nUse cases: SaaS landing pages, developer portfolios, product launches, coming soon pages, marketing microsites.\n\nAll dark-mode by default, fully responsive. Want me to build one?", done=True),
    tr("message_chat", "sent"),
]
examples.append({"source": "LA06-conversational", "messages": la06, "date": TODAY})

# Write output
out_path = Path("workspace/training_data/landing_sft_v1.jsonl")
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w") as f:
    for ex in examples:
        msgs_text = tokenizer.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)
        record = {"prompt": msgs_text, "completion": "", "source": ex["source"], "date": ex["date"]}
        f.write(json.dumps(record) + "\n")

print(f"\n=== LANDING SFT v1 SUMMARY ===")
print(f"  Examples: {len(examples)}")
print(f"  Output: {out_path}")
for ex in examples:
    print(f"  {ex['source']}: {len(ex['messages'])} messages")
