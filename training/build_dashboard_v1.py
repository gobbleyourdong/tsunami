#!/usr/bin/env python3
"""Dashboard SFT examples v1 — 6 training examples for the dashboard adapter.

Uses scaffolds/dashboard/ (Vite + React + Layout + StatCard + ChartCard + DataTable + Modal).
Pipeline: project_init(template="dashboard") → file_write(src/App.tsx) → build → undertow → result.

DA01: E-commerce analytics — Layout + StatCards + ChartCard (BarChart) + DataTable
DA02: User management admin — Layout + DataTable + Modal for user details
DA03: Project tracker — Layout + StatCards + DataTable with status badges
DA04: SaaS metrics — Layout + multiple StatCards + ChartCards (Line + Bar)
DA05: Error recovery — raw divs → Layout + StatCard pattern
DA06: Conversational routing

Usage:
  /usr/bin/python3 training/build_dashboard_v1.py
  Output: workspace/training_data/dashboard_sft_v1.jsonl
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
    "DASHBOARD PIPELINE:\n"
    "1. project_init(name, template='dashboard')\n"
    "2. file_write(src/App.tsx) -- import Layout, StatCard, ChartCard, DataTable from './components'\n"
    "3. shell_exec -- npm run build\n"
    "4. IF ERROR: fix directly\n"
    "5. undertow -- QA before delivery\n"
    "6. message_result -- land the wave\n\n"
    "DASHBOARD RULES:\n"
    "- ALWAYS template='dashboard' in project_init\n"
    "- ALWAYS use <Layout> for sidebar nav — NEVER raw <aside>/<sidebar> divs\n"
    "- ALWAYS use <StatCard> for metric values — NEVER raw stat divs\n"
    "- ALWAYS use <DataTable> for tabular data — NEVER raw <table>\n"
    "- ALWAYS use <ChartCard> as chart wrapper — use Recharts inside it\n"
    "- NEVER fetch() for mock/demo data — hardcode or useState\n"
    "- NEVER overwrite main.tsx\n"
    "- NEVER skip undertow before message_result\n\n"
    "NEVER skip the break. One tool call per response. Be brief."
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

DA01_APP = '''import { useState } from 'react';
import { Layout, StatCard, ChartCard, DataTable } from './components';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

const NAV = [
  { id: 'overview', label: 'Overview', icon: '📊', section: 'Main' },
  { id: 'orders', label: 'Orders', icon: '🛒', section: 'Main' },
  { id: 'settings', label: 'Settings', icon: '⚙️', section: 'Config' },
];

const REVENUE_DATA = [
  { month: 'Jan', revenue: 12400 }, { month: 'Feb', revenue: 18300 },
  { month: 'Mar', revenue: 15200 }, { month: 'Apr', revenue: 22100 },
  { month: 'May', revenue: 28900 }, { month: 'Jun', revenue: 31500 },
];

const ORDERS = [
  { id: 'ORD-001', customer: 'Alice Johnson', amount: '$234.50', status: 'Delivered', date: '2026-04-10' },
  { id: 'ORD-002', customer: 'Bob Smith', amount: '$89.00', status: 'Processing', date: '2026-04-11' },
  { id: 'ORD-003', customer: 'Carol White', amount: '$412.75', status: 'Shipped', date: '2026-04-12' },
  { id: 'ORD-004', customer: 'Dave Brown', amount: '$67.25', status: 'Pending', date: '2026-04-12' },
];

const COLS = [
  { key: 'id', label: 'Order ID' },
  { key: 'customer', label: 'Customer' },
  { key: 'amount', label: 'Amount' },
  { key: 'status', label: 'Status' },
  { key: 'date', label: 'Date' },
];

export default function App() {
  const [active, setActive] = useState('overview');

  return (
    <Layout title="E-Commerce" navItems={NAV} activeNav={active} onNav={setActive}>
      <h2 style={{ marginBottom: 24 }}>Overview</h2>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 32 }}>
        <StatCard label="Total Revenue" value="$128,450" change="+18.2%" trend="up" icon="💰" />
        <StatCard label="Orders" value="2,341" change="+5.7%" trend="up" icon="🛒" />
        <StatCard label="Customers" value="1,203" change="+12.3%" trend="up" icon="👤" />
        <StatCard label="Avg Order Value" value="$54.87" change="-2.1%" trend="down" icon="📦" />
      </div>

      <ChartCard title="Monthly Revenue" subtitle="Last 6 months" height={280}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={REVENUE_DATA}>
            <XAxis dataKey="month" tick={{ fill: '#718096', fontSize: 12 }} />
            <YAxis tick={{ fill: '#718096', fontSize: 12 }} />
            <Tooltip contentStyle={{ background: '#1a1f2e', border: '1px solid #2d3748', color: '#e2e8f0' }} />
            <Bar dataKey="revenue" fill="#4a9eff" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <div style={{ marginTop: 32 }}>
        <h3 style={{ marginBottom: 16 }}>Recent Orders</h3>
        <DataTable columns={COLS} rows={ORDERS} />
      </div>
    </Layout>
  );
}
'''

DA02_APP = '''import { useState } from 'react';
import { Layout, DataTable, Modal, Badge } from './components';

const NAV = [
  { id: 'users', label: 'Users', icon: '👥', section: 'Management' },
  { id: 'roles', label: 'Roles', icon: '🔑', section: 'Management' },
  { id: 'logs', label: 'Audit Logs', icon: '📋', section: 'Security' },
];

const USERS = [
  { id: 1, name: 'Alice Johnson', email: 'alice@acme.com', role: 'Admin', status: 'Active', joined: '2025-01-15' },
  { id: 2, name: 'Bob Smith', email: 'bob@acme.com', role: 'Editor', status: 'Active', joined: '2025-03-20' },
  { id: 3, name: 'Carol White', email: 'carol@acme.com', role: 'Viewer', status: 'Inactive', joined: '2025-06-01' },
  { id: 4, name: 'Dave Brown', email: 'dave@acme.com', role: 'Editor', status: 'Active', joined: '2026-01-10' },
];

const COLS = [
  { key: 'name', label: 'Name' },
  { key: 'email', label: 'Email' },
  { key: 'role', label: 'Role' },
  { key: 'status', label: 'Status' },
  { key: 'joined', label: 'Joined' },
];

export default function App() {
  const [active, setActive] = useState('users');
  const [selected, setSelected] = useState<typeof USERS[0] | null>(null);

  return (
    <Layout title="Admin" navItems={NAV} activeNav={active} onNav={setActive}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2>Users</h2>
        <Badge>{USERS.length} total</Badge>
      </div>

      <DataTable
        columns={COLS}
        rows={USERS}
        onRowClick={(row) => setSelected(row as typeof USERS[0])}
      />

      {selected && (
        <Modal title={`User: ${selected.name}`} onClose={() => setSelected(null)}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div><strong>Email:</strong> {selected.email}</div>
            <div><strong>Role:</strong> {selected.role}</div>
            <div><strong>Status:</strong> {selected.status}</div>
            <div><strong>Joined:</strong> {selected.joined}</div>
          </div>
        </Modal>
      )}
    </Layout>
  );
}
'''

DA03_APP = '''import { useState } from 'react';
import { Layout, StatCard, DataTable, Badge } from './components';

const NAV = [
  { id: 'projects', label: 'Projects', icon: '📁', section: 'Work' },
  { id: 'tasks', label: 'Tasks', icon: '✅', section: 'Work' },
  { id: 'team', label: 'Team', icon: '👥', section: 'Work' },
];

const PROJECTS = [
  { name: 'Website Redesign', owner: 'Alice', status: 'In Progress', tasks: 24, done: 18, due: '2026-05-01' },
  { name: 'Mobile App', owner: 'Bob', status: 'Planning', tasks: 12, done: 3, due: '2026-06-15' },
  { name: 'API Integration', owner: 'Carol', status: 'Completed', tasks: 8, done: 8, due: '2026-04-01' },
  { name: 'Data Pipeline', owner: 'Dave', status: 'Blocked', tasks: 16, done: 5, due: '2026-04-30' },
];

const COLS = [
  { key: 'name', label: 'Project' },
  { key: 'owner', label: 'Owner' },
  { key: 'status', label: 'Status' },
  { key: 'tasks', label: 'Tasks' },
  { key: 'done', label: 'Done' },
  { key: 'due', label: 'Due Date' },
];

export default function App() {
  const [active, setActive] = useState('projects');
  const total = PROJECTS.length;
  const inProgress = PROJECTS.filter(p => p.status === 'In Progress').length;
  const completed = PROJECTS.filter(p => p.status === 'Completed').length;
  const blocked = PROJECTS.filter(p => p.status === 'Blocked').length;

  return (
    <Layout title="Project Tracker" navItems={NAV} activeNav={active} onNav={setActive}>
      <h2 style={{ marginBottom: 24 }}>Projects</h2>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 32 }}>
        <StatCard label="Total Projects" value={total} icon="📁" />
        <StatCard label="In Progress" value={inProgress} trend="up" icon="🔄" />
        <StatCard label="Completed" value={completed} trend="up" icon="✅" />
        <StatCard label="Blocked" value={blocked} trend="down" icon="🚫" />
      </div>

      <DataTable columns={COLS} rows={PROJECTS} />
    </Layout>
  );
}
'''

DA04_APP = '''import { Layout, StatCard, ChartCard } from './components';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

const NAV = [
  { id: 'metrics', label: 'Metrics', icon: '📈', section: 'Analytics' },
  { id: 'revenue', label: 'Revenue', icon: '💰', section: 'Analytics' },
  { id: 'churn', label: 'Churn', icon: '📉', section: 'Analytics' },
];

const MRR_DATA = [
  { month: 'Nov', mrr: 42000 }, { month: 'Dec', mrr: 48500 }, { month: 'Jan', mrr: 53200 },
  { month: 'Feb', mrr: 59800 }, { month: 'Mar', mrr: 67100 }, { month: 'Apr', mrr: 74500 },
];

const CHURN_DATA = [
  { month: 'Nov', rate: 3.2 }, { month: 'Dec', rate: 2.8 }, { month: 'Jan', rate: 2.5 },
  { month: 'Feb', rate: 2.1 }, { month: 'Mar', rate: 1.9 }, { month: 'Apr', rate: 1.7 },
];

const TOOLTIP_STYLE = { background: '#1a1f2e', border: '1px solid #2d3748', color: '#e2e8f0' };

export default function App() {
  return (
    <Layout title="SaaS Metrics" navItems={NAV} activeNav="metrics">
      <h2 style={{ marginBottom: 24 }}>Key Metrics</h2>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 32 }}>
        <StatCard label="MRR" value="$74,500" change="+11.0%" trend="up" icon="💰" />
        <StatCard label="ARR" value="$894K" change="+42.8% YoY" trend="up" icon="📅" />
        <StatCard label="Active Users" value="3,241" change="+8.4%" trend="up" icon="👤" />
        <StatCard label="Churn Rate" value="1.7%" change="-0.2pp" trend="up" icon="🔄" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        <ChartCard title="Monthly Recurring Revenue" subtitle="Last 6 months" height={250}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={MRR_DATA}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2d3748" />
              <XAxis dataKey="month" tick={{ fill: '#718096', fontSize: 12 }} />
              <YAxis tick={{ fill: '#718096', fontSize: 12 }} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Line type="monotone" dataKey="mrr" stroke="#4a9eff" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Monthly Churn Rate (%)" subtitle="Lower is better" height={250}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={CHURN_DATA}>
              <XAxis dataKey="month" tick={{ fill: '#718096', fontSize: 12 }} />
              <YAxis tick={{ fill: '#718096', fontSize: 12 }} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Bar dataKey="rate" fill="#e53e3e" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </Layout>
  );
}
'''

DA05_BAD_APP = '''export default function App() {
  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#0a0e17' }}>
      <aside style={{ width: 220, background: '#141922', padding: 16 }}>
        <h2>Dashboard</h2>
        <ul><li>Overview</li><li>Users</li></ul>
      </aside>
      <main style={{ flex: 1, padding: 32 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
          <div style={{ background: '#1a1f2e', borderRadius: 8, padding: 16 }}>
            <p>Total Users</p><h3>1,234</h3>
          </div>
          <div style={{ background: '#1a1f2e', borderRadius: 8, padding: 16 }}>
            <p>Revenue</p><h3>$45,678</h3>
          </div>
          <div style={{ background: '#1a1f2e', borderRadius: 8, padding: 16 }}>
            <p>Orders</p><h3>892</h3>
          </div>
        </div>
      </main>
    </div>
  );
}
'''

def tc(tool_name, **kwargs):
    return {"role": "assistant", "content": None, "tool_calls": [{"id": f"call_{tool_name}", "type": "function", "function": {"name": tool_name, "arguments": json.dumps(kwargs)}}]}

def tr(tool_name, result):
    return {"role": "tool", "tool_call_id": f"call_{tool_name}", "name": tool_name, "content": json.dumps({"result": result})}

examples = []

# DA01: E-commerce analytics
da01 = [
    {"role": "user", "content": "Build an e-commerce analytics dashboard. Sidebar nav, 4 stat cards (revenue/orders/customers/avg order), monthly revenue bar chart, and orders table."},
    tc("project_init", name="ecommerce-dashboard", template="dashboard"),
    tr("project_init", "Project 'ecommerce-dashboard' created. dashboard scaffold with Layout, StatCard, ChartCard, DataTable, Modal, Toast, Badge, EmptyState ready."),
    tc("file_write", path="src/App.tsx", content=DA01_APP),
    tr("file_write", "Written: src/App.tsx"),
    tc("shell_exec", command="cd workspace/deliverables/ecommerce-dashboard && npm run build 2>&1 | tail -5"),
    tr("shell_exec", "dist/index.html 1.9kB\ndist/assets/index-BxKp9q1a.js 237.4kB\n✓ built in 2.3s"),
    tc("undertow", path="workspace/deliverables/ecommerce-dashboard/dist/index.html"),
    tr("undertow", "PASS: Layout sidebar with nav. 4 StatCards with values. BarChart in ChartCard. DataTable with order rows."),
    tc("message_result"),
    tr("message_result", "delivered"),
]
examples.append({"source": "DA01-ecommerce-analytics", "messages": da01, "date": TODAY})

# DA02: User management admin
da02 = [
    {"role": "user", "content": "Build an admin dashboard for user management. Sidebar nav (Users/Roles/Audit Logs), users table, click a row to open a details modal."},
    tc("project_init", name="admin-dashboard", template="dashboard"),
    tr("project_init", "Project 'admin-dashboard' created. dashboard scaffold ready."),
    tc("file_write", path="src/App.tsx", content=DA02_APP),
    tr("file_write", "Written: src/App.tsx"),
    tc("shell_exec", command="cd workspace/deliverables/admin-dashboard && npm run build 2>&1 | tail -5"),
    tr("shell_exec", "dist/index.html 1.8kB\ndist/assets/index-CyMp3r2b.js 229.1kB\n✓ built in 2.1s"),
    tc("undertow", path="workspace/deliverables/admin-dashboard/dist/index.html"),
    tr("undertow", "PASS: Layout with sidebar nav. DataTable shows users. Modal component present."),
    tc("message_result"),
    tr("message_result", "delivered"),
]
examples.append({"source": "DA02-user-management", "messages": da02, "date": TODAY})

# DA03: Project tracker
da03 = [
    {"role": "user", "content": "Build a project management dashboard. 4 stat cards showing project counts by status, and a projects table with name/owner/status/tasks."},
    tc("project_init", name="project-dashboard", template="dashboard"),
    tr("project_init", "Project 'project-dashboard' created. dashboard scaffold ready."),
    tc("file_write", path="src/App.tsx", content=DA03_APP),
    tr("file_write", "Written: src/App.tsx"),
    tc("shell_exec", command="cd workspace/deliverables/project-dashboard && npm run build 2>&1 | tail -5"),
    tr("shell_exec", "dist/index.html 1.7kB\ndist/assets/index-DzQp1s3c.js 224.7kB\n✓ built in 2.0s"),
    tc("undertow", path="workspace/deliverables/project-dashboard/dist/index.html"),
    tr("undertow", "PASS: Layout sidebar. 4 StatCards. DataTable with project data."),
    tc("message_result"),
    tr("message_result", "delivered"),
]
examples.append({"source": "DA03-project-tracker", "messages": da03, "date": TODAY})

# DA04: SaaS metrics
da04 = [
    {"role": "user", "content": "Build a SaaS metrics dashboard. 4 KPI cards (MRR/ARR/users/churn), line chart for MRR trend, bar chart for churn rate."},
    tc("project_init", name="saas-metrics", template="dashboard"),
    tr("project_init", "Project 'saas-metrics' created. dashboard scaffold ready."),
    tc("file_write", path="src/App.tsx", content=DA04_APP),
    tr("file_write", "Written: src/App.tsx"),
    tc("shell_exec", command="cd workspace/deliverables/saas-metrics && npm run build 2>&1 | tail -5"),
    tr("shell_exec", "dist/index.html 1.9kB\ndist/assets/index-EzQm2t4d.js 245.3kB\n✓ built in 2.4s"),
    tc("undertow", path="workspace/deliverables/saas-metrics/dist/index.html"),
    tr("undertow", "PASS: Layout sidebar. 4 StatCards. LineChart for MRR in ChartCard. BarChart for churn in ChartCard."),
    tc("message_result"),
    tr("message_result", "delivered"),
]
examples.append({"source": "DA04-saas-metrics", "messages": da04, "date": TODAY})

# DA05: Error recovery — raw divs → Layout + StatCard
da05 = [
    {"role": "user", "content": "Build an analytics dashboard with sidebar and stat cards."},
    tc("project_init", name="analytics-dashboard", template="dashboard"),
    tr("project_init", "Project 'analytics-dashboard' created. dashboard scaffold ready."),
    tc("file_write", path="src/App.tsx", content=DA05_BAD_APP),
    tr("file_write", "Written: src/App.tsx. WARNING: Not using dashboard scaffold components. Import and use Layout (for sidebar), StatCard (for metrics), ChartCard, DataTable instead of raw <aside>, <div> grids."),
    # Recovery: fix to scaffold
    tc("file_write", path="src/App.tsx", content=DA03_APP),
    tr("file_write", "Written: src/App.tsx"),
    tc("shell_exec", command="cd workspace/deliverables/analytics-dashboard && npm run build 2>&1 | tail -5"),
    tr("shell_exec", "dist/index.html 1.7kB\ndist/assets/index-FxQn3u5e.js 224.1kB\n✓ built in 2.0s"),
    tc("undertow", path="workspace/deliverables/analytics-dashboard/dist/index.html"),
    tr("undertow", "PASS: Layout and StatCard components confirmed. Scaffold components used correctly."),
    tc("message_result"),
    tr("message_result", "delivered"),
]
examples.append({"source": "DA05-error-recovery", "messages": da05, "date": TODAY})

# DA06: Conversational
da06 = [
    {"role": "user", "content": "What kinds of dashboards can you build?"},
    tc("message_chat", text="I build admin/analytics dashboards using the dashboard scaffold with these components:\n\n• **Layout** — sidebar nav with active state, sections, responsive\n• **StatCard** — metric cards with value, change %, trend up/down indicator\n• **ChartCard** — chart wrapper for Recharts (LineChart, BarChart, PieChart, etc.)\n• **DataTable** — sortable/filterable table with row click support\n• **Modal** — modal dialog for detail views\n• **Toast** — toast notifications (success/error/info)\n• **Badge**, **EmptyState**, **Card** — utilities\n\nUse cases: analytics dashboards, admin panels, project trackers, SaaS metrics, CRM views, monitoring dashboards.\n\nKey difference from data-viz: dashboards have a **sidebar nav** for multi-section navigation. Data-viz is a single chart page.", done=True),
    tr("message_chat", "sent"),
]
examples.append({"source": "DA06-conversational", "messages": da06, "date": TODAY})

# Write output
out_path = Path("workspace/training_data/dashboard_sft_v1.jsonl")
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w") as f:
    for ex in examples:
        msgs_text = tokenizer.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)
        record = {"prompt": msgs_text, "completion": "", "source": ex["source"], "date": ex["date"]}
        f.write(json.dumps(record) + "\n")

print(f"\n=== DASHBOARD SFT v1 SUMMARY ===")
print(f"  Examples: {len(examples)}")
print(f"  Output: {out_path}")
for ex in examples:
    print(f"  {ex['source']}: {len(ex['messages'])} messages")
