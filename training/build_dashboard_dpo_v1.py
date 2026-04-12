#!/usr/bin/env python3
"""
build_dashboard_dpo_v1.py — Fire 17 (DPO)

18 DPO pairs (3 per fault type) for the dashboard adapter.

Fault taxonomy:
  DAF01 — wrong template (react-app/dataviz instead of dashboard)
  DAF02 — raw layout (aside/sidebar div instead of <Layout>)
  DAF03 — raw metrics (plain div instead of <StatCard>)
  DAF04 — raw table (<table> instead of <DataTable>)
  DAF05 — no undertow (message_result before screenshot verify)
  DAF06 — wrong files (main.tsx / vite.config / index.html instead of App.tsx only)
"""

from __future__ import annotations
import json, os, datetime
from pathlib import Path
from transformers import AutoTokenizer

MODEL_ID = "google/gemma-4-e4b-it"
OUT_DIR  = Path("workspace/training_data")
OUT_FILE = OUT_DIR / "dashboard_dpo_v1.jsonl"
OUT_DIR.mkdir(parents=True, exist_ok=True)

print("Loading tokenizer...")
tok = AutoTokenizer.from_pretrained(MODEL_ID)
print("Tokenizer loaded.")

TODAY = datetime.date.today().isoformat()

# ── helpers ─────────────────────────────────────────────────────────────────

def tool_call(tool_name: str, **kwargs) -> dict:
    return {"type": "tool_use", "name": tool_name, "input": kwargs}

def tool_result(content: str, tool_use_id: str = "t0") -> dict:
    return {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}

def assistant_turn(*items) -> dict:
    return {"role": "assistant", "content": list(items)}

def user_turn(*items) -> dict:
    content = []
    for item in items:
        if isinstance(item, str):
            content.append({"type": "text", "text": item})
        else:
            content.append(item)
    return {"role": "user", "content": content}

def text(t: str) -> dict:
    return {"type": "text", "text": t}

SYSTEM = """You are Tsunami, a senior full-stack engineer.

You have access to these tools: project_init, file_write, shell_exec, search_web, message_result, undertow.

project_init(name, template) — scaffold new project. Use template="dashboard" for admin/management apps with sidebar nav, StatCards, DataTables.
file_write(path, content) — write source files (App.tsx only; scaffold generates everything else).
shell_exec(cmd) — run commands.
search_web(query) — search for references.
message_result(text) — final user-facing response (requires undertow screenshot first).
undertow(url) — screenshot the live app for visual verification.

Dashboard scaffold components (always import from './components'):
  Layout — sidebar nav shell: <Layout title navItems activeNav onNav>
  StatCard — metric tile: <StatCard label value change trend icon />
  ChartCard — chart wrapper: <ChartCard title><Recharts.../></ChartCard>
  DataTable — sortable table: <DataTable columns rows />
  Modal — overlay: <Modal open onClose title>
  Toast — notification: <Toast message type />
  Badge — status chip: <Badge text color />
  EmptyState — empty content: <EmptyState title message />

Rules:
1. Always use template="dashboard" for admin/management apps (NOT react-app, NOT dataviz).
2. Always use <Layout> for the page shell — never a raw <aside> or sidebar div.
3. Always use <StatCard> for metric tiles — never a raw div with className="stat".
4. Always use <DataTable> for tabular data — never a raw <table>.
5. Always call undertow() before message_result to visually verify.
6. Only write App.tsx — the scaffold generates main.tsx, vite.config.ts, index.html.
"""

def tokenize(msgs: list[dict]) -> list[int]:
    result = tok.apply_chat_template(msgs, add_generation_prompt=False, return_tensors=None)
    return list(result) if not isinstance(result, list) else result

def make_pair(
    prompt_msgs: list[dict],
    chosen_turns: list[dict],
    rejected_turns: list[dict],
    fault: str,
    note: str,
    source: str,
) -> dict:
    base_tok  = tokenize(prompt_msgs)
    cho_msgs  = prompt_msgs + chosen_turns
    rej_msgs  = prompt_msgs + rejected_turns

    return {
        "prompt":      base_tok,
        "chosen":      tokenize(cho_msgs),
        "rejected":    tokenize(rej_msgs),
        "source_bug":  fault,
        "note":        note,
        "source":      source,
        "images":      [],
        "date":        TODAY,
    }


# ═══════════════════════════════════════════════════════════════════════════
# DAF01 — wrong template
# ═══════════════════════════════════════════════════════════════════════════

def daf01_a():
    """E-commerce analytics dashboard — react-app vs dashboard"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Build me an e-commerce analytics dashboard with sales metrics and an orders table."),
    ]
    chosen = [
        assistant_turn(
            text("Starting the dashboard project."),
            tool_call("project_init", name="ecommerce-analytics", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded with template=dashboard. Installed Layout, StatCard, ChartCard, DataTable components.")),
        assistant_turn(
            text("Writing the analytics dashboard."),
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, ChartCard, DataTable } from './components'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

const NAV = [
  { label: 'Dashboard', href: '#dashboard' },
  { label: 'Orders', href: '#orders' },
]

const SALES_DATA = [
  { month: 'Jan', revenue: 42000 }, { month: 'Feb', revenue: 56000 },
  { month: 'Mar', revenue: 61000 }, { month: 'Apr', revenue: 49000 },
]

const ORDER_COLS = [
  { key: 'id', label: 'Order #' }, { key: 'customer', label: 'Customer' },
  { key: 'amount', label: 'Amount' }, { key: 'status', label: 'Status' },
]
const ORDER_ROWS = [
  { id: '#1042', customer: 'Alice Brown', amount: '$320', status: 'Shipped' },
  { id: '#1043', customer: 'Bob Chen',    amount: '$85',  status: 'Pending' },
  { id: '#1044', customer: 'Carol Davis', amount: '$210', status: 'Delivered' },
]

export default function App() {
  const [active, setActive] = useState('Dashboard')
  return (
    <Layout title="E-commerce Analytics" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="Total Revenue" value="$208,000" change="+12%" trend="up" icon="💰" />
        <StatCard label="Orders"        value="1,240"    change="+8%"  trend="up" icon="📦" />
        <StatCard label="Avg Order"     value="$167"     change="-3%"  trend="down" icon="🛒" />
        <StatCard label="Customers"     value="4,320"    change="+5%"  trend="up" icon="👥" />
      </div>
      <ChartCard title="Monthly Revenue">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={SALES_DATA}>
            <XAxis dataKey="month" /><YAxis /><Tooltip />
            <Bar dataKey="revenue" fill="#6366f1" />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
      <DataTable columns={ORDER_COLS} rows={ORDER_ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written: src/App.tsx")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: dashboard renders with sidebar, 4 StatCards, bar chart, orders table.")),
        assistant_turn(tool_call("message_result", text="E-commerce analytics dashboard built: sidebar nav, 4 KPI cards (revenue/orders/avg order/customers), monthly revenue bar chart, and orders DataTable.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            text("Creating the project."),
            tool_call("project_init", name="ecommerce-analytics", template="react-app"),
        ),
        user_turn(tool_result("Scaffolded react-app.")),
        assistant_turn(
            text("Writing the dashboard."),
            tool_call("file_write", path="src/App.tsx", content="""export default function App() {
  return <div className="p-4"><h1>E-commerce Analytics</h1><p>Dashboard here.</p></div>
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="Dashboard created with react-app template.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF01", "dashboard template: use template=dashboard not react-app", "daf01-a")

def daf01_b():
    """User management admin — dataviz vs dashboard"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("I need an admin dashboard to manage users with a sidebar and a users table."),
    ]
    chosen = [
        assistant_turn(
            text("Scaffolding admin dashboard."),
            tool_call("project_init", name="user-admin", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded with template=dashboard. Layout, StatCard, DataTable available.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable, Badge } from './components'

const NAV = [{ label: 'Users', href: '#users' }, { label: 'Settings', href: '#settings' }]
const COLS = [
  { key: 'name', label: 'Name' }, { key: 'email', label: 'Email' },
  { key: 'role', label: 'Role' }, { key: 'status', label: 'Status' },
]
const ROWS = [
  { name: 'Alice Brown', email: 'alice@example.com', role: 'Admin', status: 'Active' },
  { name: 'Bob Chen',    email: 'bob@example.com',   role: 'Editor', status: 'Active' },
  { name: 'Carol Davis', email: 'carol@example.com', role: 'Viewer', status: 'Inactive' },
]

export default function App() {
  const [active, setActive] = useState('Users')
  return (
    <Layout title="User Admin" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard label="Total Users" value="124"  change="+3"  trend="up" icon="👥" />
        <StatCard label="Active"      value="118"  change="+2"  trend="up" icon="✅" />
        <StatCard label="Inactive"    value="6"    change="+1"  trend="up" icon="⏸" />
      </div>
      <DataTable columns={COLS} rows={ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written: src/App.tsx")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: sidebar with Users/Settings, 3 StatCards, DataTable of users.")),
        assistant_turn(tool_call("message_result", text="User admin dashboard: sidebar nav, 3 KPI cards, users DataTable.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            text("Admin has charts, so I'll use dataviz."),
            tool_call("project_init", name="user-admin", template="dataviz"),
        ),
        user_turn(tool_result("Scaffolded dataviz.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""export default function App() {
  return <div><h1>User Admin</h1><p>Charts here.</p></div>
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="Admin created.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF01", "dashboard template: use template=dashboard not dataviz", "daf01-b")

def daf01_c():
    """Project tracker — generic react-app vs dashboard"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Make a project management dashboard with task stats and a project list table."),
    ]
    chosen = [
        assistant_turn(
            tool_call("project_init", name="project-tracker", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded with template=dashboard.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable } from './components'

const NAV = [{ label: 'Projects', href: '#' }, { label: 'Tasks', href: '#tasks' }]
const COLS = [
  { key: 'name', label: 'Project' }, { key: 'status', label: 'Status' },
  { key: 'tasks', label: 'Tasks' }, { key: 'due', label: 'Due' },
]
const ROWS = [
  { name: 'Website Rebrand', status: 'Active',  tasks: '12/18', due: 'Mar 30' },
  { name: 'Mobile App',      status: 'Active',  tasks: '5/24',  due: 'Apr 15' },
  { name: 'API Migration',   status: 'On Hold', tasks: '8/10',  due: 'TBD' },
]

export default function App() {
  const [active, setActive] = useState('Projects')
  return (
    <Layout title="Project Tracker" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="Active Projects" value="8"  change="+1" trend="up"   icon="📋" />
        <StatCard label="On Hold"         value="2"  change="0"  trend="up"   icon="⏸" />
        <StatCard label="Completed"       value="14" change="+3" trend="up"   icon="✅" />
        <StatCard label="Overdue"         value="1"  change="+1" trend="down" icon="⚠️" />
      </div>
      <DataTable columns={COLS} rows={ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: sidebar, 4 StatCards, projects DataTable.")),
        assistant_turn(tool_call("message_result", text="Project tracker dashboard: 4 KPI cards and projects table.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            tool_call("project_init", name="project-tracker", template="react-app"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""export default function App() {
  return <div><h1>Projects</h1></div>
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="Project tracker created.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF01", "dashboard template: use template=dashboard not react-app", "daf01-c")

# ═══════════════════════════════════════════════════════════════════════════
# DAF02 — raw layout instead of <Layout>
# ═══════════════════════════════════════════════════════════════════════════

def daf02_a():
    """Raw aside sidebar vs <Layout>"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Build an inventory management dashboard with sidebar nav, stock stats, and a products table."),
    ]
    chosen = [
        assistant_turn(
            tool_call("project_init", name="inventory", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded with template=dashboard.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable } from './components'

const NAV = [{ label: 'Inventory', href: '#' }, { label: 'Suppliers', href: '#suppliers' }]
const COLS = [
  { key: 'sku', label: 'SKU' }, { key: 'name', label: 'Product' },
  { key: 'stock', label: 'Stock' }, { key: 'status', label: 'Status' },
]
const ROWS = [
  { sku: 'WDG-001', name: 'Widget A', stock: 240, status: 'In Stock' },
  { sku: 'WDG-002', name: 'Widget B', stock: 18,  status: 'Low Stock' },
  { sku: 'WDG-003', name: 'Widget C', stock: 0,   status: 'Out of Stock' },
]

export default function App() {
  const [active, setActive] = useState('Inventory')
  return (
    <Layout title="Inventory" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard label="Total Products" value="342"  change="+5"  trend="up"   icon="📦" />
        <StatCard label="Low Stock"      value="24"   change="+3"  trend="down" icon="⚠️" />
        <StatCard label="Out of Stock"   value="8"    change="+2"  trend="down" icon="❌" />
      </div>
      <DataTable columns={COLS} rows={ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: Layout sidebar, 3 StatCards, products DataTable.")),
        assistant_turn(tool_call("message_result", text="Inventory dashboard: sidebar nav, 3 stock KPIs, products table.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            tool_call("project_init", name="inventory", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { StatCard, DataTable } from './components'

export default function App() {
  return (
    <div className="flex">
      <aside className="w-64 bg-gray-800 text-white h-screen p-4">
        <h2 className="font-bold mb-4">Inventory</h2>
        <nav><a href="#" className="block py-1">Products</a></nav>
      </aside>
      <main className="flex-1 p-6">
        <div className="grid grid-cols-3 gap-4 mb-6">
          <StatCard label="Total Products" value="342" trend="up" />
        </div>
        <DataTable columns={[]} rows={[]} />
      </main>
    </div>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="Inventory dashboard with custom sidebar.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF02", "use <Layout> not raw <aside> sidebar", "daf02-a")

def daf02_b():
    """Raw div sidebar vs <Layout>"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Create a finance dashboard with a left sidebar menu, revenue stats and a transactions table."),
    ]
    chosen = [
        assistant_turn(
            tool_call("project_init", name="finance-dashboard", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded with template=dashboard.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable, ChartCard } from './components'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

const NAV = [{ label: 'Overview', href: '#' }, { label: 'Transactions', href: '#tx' }]
const TX_COLS = [
  { key: 'date', label: 'Date' }, { key: 'desc', label: 'Description' },
  { key: 'amount', label: 'Amount' }, { key: 'type', label: 'Type' },
]
const TX_ROWS = [
  { date: '2026-04-10', desc: 'Client Payment', amount: '+$4,200', type: 'Income' },
  { date: '2026-04-09', desc: 'AWS Invoice',    amount: '-$340',   type: 'Expense' },
  { date: '2026-04-08', desc: 'Subscription',   amount: '-$99',    type: 'Expense' },
]
const TREND = [
  { month: 'Jan', revenue: 18000 }, { month: 'Feb', revenue: 22000 },
  { month: 'Mar', revenue: 19500 }, { month: 'Apr', revenue: 24000 },
]

export default function App() {
  const [active, setActive] = useState('Overview')
  return (
    <Layout title="Finance" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard label="Revenue" value="$83,500" change="+9%" trend="up" icon="💰" />
        <StatCard label="Expenses" value="$31,200" change="+4%" trend="down" icon="💸" />
        <StatCard label="Net Profit" value="$52,300" change="+14%" trend="up" icon="📈" />
      </div>
      <ChartCard title="Revenue Trend">
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={TREND}>
            <XAxis dataKey="month" /><YAxis /><Tooltip />
            <Line type="monotone" dataKey="revenue" stroke="#6366f1" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>
      <DataTable columns={TX_COLS} rows={TX_ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: Layout sidebar, 3 KPI cards, line chart, transactions table.")),
        assistant_turn(tool_call("message_result", text="Finance dashboard with sidebar, 3 KPIs, revenue trend chart, transactions table.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            tool_call("project_init", name="finance-dashboard", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""export default function App() {
  return (
    <div style={{ display: 'flex' }}>
      <div style={{ width: 240, background: '#1e293b', color: 'white', padding: 16 }}>
        <div style={{ fontWeight: 'bold', marginBottom: 16 }}>Finance</div>
        <a href="#" style={{ display: 'block', color: 'white' }}>Overview</a>
        <a href="#tx" style={{ display: 'block', color: 'white' }}>Transactions</a>
      </div>
      <main style={{ flex: 1, padding: 24 }}>
        <h1>Revenue: $83,500</h1>
      </main>
    </div>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="Finance dashboard with sidebar.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF02", "use <Layout> not raw sidebar div", "daf02-b")

def daf02_c():
    """No sidebar at all vs <Layout>"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Build a CRM admin dashboard with contacts nav, deal stats and contact list."),
    ]
    chosen = [
        assistant_turn(
            tool_call("project_init", name="crm-admin", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded with template=dashboard.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable } from './components'

const NAV = [
  { label: 'Contacts', href: '#' }, { label: 'Deals', href: '#deals' },
  { label: 'Pipeline', href: '#pipe' },
]
const COLS = [
  { key: 'name', label: 'Name' }, { key: 'company', label: 'Company' },
  { key: 'email', label: 'Email' }, { key: 'stage', label: 'Stage' },
]
const ROWS = [
  { name: 'Alice Brown', company: 'Acme Inc',  email: 'alice@acme.com',  stage: 'Qualified' },
  { name: 'Bob Chen',    company: 'StartupXY', email: 'bob@startupxy.com', stage: 'Proposal' },
  { name: 'Carol Davis', company: 'MegaCorp',  email: 'carol@mega.com',   stage: 'Closed Won' },
]

export default function App() {
  const [active, setActive] = useState('Contacts')
  return (
    <Layout title="CRM" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="Contacts" value="248"   change="+12" trend="up" icon="👥" />
        <StatCard label="Open Deals" value="34"  change="+5"  trend="up" icon="🤝" />
        <StatCard label="Won"        value="19"  change="+3"  trend="up" icon="🏆" />
        <StatCard label="Pipeline"   value="$1.2M" change="+8%" trend="up" icon="💰" />
      </div>
      <DataTable columns={COLS} rows={ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: CRM Layout sidebar, 4 KPI cards, contacts DataTable.")),
        assistant_turn(tool_call("message_result", text="CRM dashboard: sidebar nav, 4 KPI cards, contacts DataTable.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            tool_call("project_init", name="crm-admin", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { StatCard, DataTable } from './components'

export default function App() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">CRM Dashboard</h1>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="Contacts" value="248" trend="up" />
      </div>
      <DataTable columns={[]} rows={[]} />
    </div>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="CRM dashboard without sidebar.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF02", "use <Layout> not layout-less wrapper div", "daf02-c")

# ═══════════════════════════════════════════════════════════════════════════
# DAF03 — raw metric divs instead of <StatCard>
# ═══════════════════════════════════════════════════════════════════════════

def daf03_a():
    """Raw div metrics vs <StatCard>"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Build a marketing analytics dashboard showing campaign impressions, clicks, and conversions with a campaigns table."),
    ]
    chosen = [
        assistant_turn(
            tool_call("project_init", name="marketing-analytics", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded with template=dashboard.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable } from './components'

const NAV = [{ label: 'Campaigns', href: '#' }, { label: 'Audiences', href: '#aud' }]
const COLS = [
  { key: 'campaign', label: 'Campaign' }, { key: 'impr', label: 'Impressions' },
  { key: 'clicks', label: 'Clicks' }, { key: 'ctr', label: 'CTR' },
]
const ROWS = [
  { campaign: 'Spring Sale',    impr: '142,000', clicks: '4,260', ctr: '3.0%' },
  { campaign: 'Product Launch', impr: '98,000',  clicks: '2,940', ctr: '3.0%' },
  { campaign: 'Retargeting',    impr: '45,000',  clicks: '2,250', ctr: '5.0%' },
]

export default function App() {
  const [active, setActive] = useState('Campaigns')
  return (
    <Layout title="Marketing" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard label="Impressions" value="285,000" change="+22%"  trend="up"   icon="👁" />
        <StatCard label="Clicks"      value="9,450"   change="+18%"  trend="up"   icon="🖱" />
        <StatCard label="Conversions" value="1,200"   change="+31%"  trend="up"   icon="✅" />
      </div>
      <DataTable columns={COLS} rows={ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: sidebar, 3 StatCards, campaigns table.")),
        assistant_turn(tool_call("message_result", text="Marketing dashboard: 3 KPI cards (impressions/clicks/conversions) and campaigns table.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            tool_call("project_init", name="marketing-analytics", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { Layout, DataTable } from './components'
import { useState } from 'react'

const NAV = [{ label: 'Campaigns', href: '#' }]

export default function App() {
  const [active, setActive] = useState('Campaigns')
  return (
    <Layout title="Marketing" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-lg p-4 shadow">
          <div className="text-sm text-gray-500">Impressions</div>
          <div className="text-2xl font-bold">285,000</div>
          <div className="text-green-500">+22%</div>
        </div>
        <div className="bg-white rounded-lg p-4 shadow">
          <div className="text-sm text-gray-500">Clicks</div>
          <div className="text-2xl font-bold">9,450</div>
        </div>
      </div>
      <DataTable columns={[]} rows={[]} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="Marketing dashboard with custom stat divs.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF03", "use <StatCard> not raw metric div", "daf03-a")

def daf03_b():
    """Hard-coded number spans vs <StatCard>"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Build an HR dashboard showing headcount, open positions, and time-to-hire metrics."),
    ]
    chosen = [
        assistant_turn(
            tool_call("project_init", name="hr-dashboard", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded with template=dashboard.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable } from './components'

const NAV = [{ label: 'Overview', href: '#' }, { label: 'Positions', href: '#pos' }]
const COLS = [
  { key: 'role', label: 'Role' }, { key: 'dept', label: 'Department' },
  { key: 'posted', label: 'Posted' }, { key: 'applicants', label: 'Applicants' },
]
const ROWS = [
  { role: 'Senior Engineer',   dept: 'Engineering', posted: 'Mar 15', applicants: 42 },
  { role: 'Product Designer',  dept: 'Design',      posted: 'Mar 20', applicants: 28 },
  { role: 'Sales Manager',     dept: 'Sales',       posted: 'Apr 1',  applicants: 15 },
]

export default function App() {
  const [active, setActive] = useState('Overview')
  return (
    <Layout title="HR Dashboard" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="Headcount"    value="312"   change="+8"  trend="up"   icon="👥" />
        <StatCard label="Open Roles"   value="14"    change="+3"  trend="up"   icon="📋" />
        <StatCard label="Time-to-Hire" value="28d"   change="-3d" trend="up"   icon="⏱" />
        <StatCard label="Retention"    value="94.2%" change="+1%" trend="up"   icon="🏆" />
      </div>
      <DataTable columns={COLS} rows={ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: HR Layout sidebar, 4 StatCards, open positions table.")),
        assistant_turn(tool_call("message_result", text="HR dashboard: 4 KPI cards (headcount/roles/time-to-hire/retention) and open positions table.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            tool_call("project_init", name="hr-dashboard", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { Layout, DataTable } from './components'
import { useState } from 'react'
const NAV = [{ label: 'Overview', href: '#' }]
export default function App() {
  const [active, setActive] = useState('Overview')
  return (
    <Layout title="HR Dashboard" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="flex gap-6 mb-6">
        <div><span className="text-3xl font-bold">312</span><p>Headcount</p></div>
        <div><span className="text-3xl font-bold">14</span><p>Open Roles</p></div>
        <div><span className="text-3xl font-bold">28d</span><p>Time-to-Hire</p></div>
      </div>
      <DataTable columns={[]} rows={[]} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="HR dashboard with raw metric spans.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF03", "use <StatCard> not raw metric spans", "daf03-b")

def daf03_c():
    """No metric tiles at all vs <StatCard>"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Build a support ticket dashboard with ticket volume stats and an open tickets table."),
    ]
    chosen = [
        assistant_turn(
            tool_call("project_init", name="support-dashboard", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded with template=dashboard.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable } from './components'

const NAV = [{ label: 'Tickets', href: '#' }, { label: 'Reports', href: '#rep' }]
const COLS = [
  { key: 'id', label: 'Ticket' }, { key: 'subject', label: 'Subject' },
  { key: 'priority', label: 'Priority' }, { key: 'status', label: 'Status' },
]
const ROWS = [
  { id: '#8042', subject: 'Login error',      priority: 'High',   status: 'Open' },
  { id: '#8043', subject: 'Billing question', priority: 'Medium', status: 'Pending' },
  { id: '#8044', subject: 'Feature request',  priority: 'Low',    status: 'Open' },
]

export default function App() {
  const [active, setActive] = useState('Tickets')
  return (
    <Layout title="Support" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="Open"      value="42"  change="+5"  trend="down" icon="📬" />
        <StatCard label="Resolved"  value="128" change="+18" trend="up"   icon="✅" />
        <StatCard label="Avg CSAT"  value="4.7" change="+0.1" trend="up"  icon="⭐" />
        <StatCard label="Avg Time"  value="3.2h" change="-0.5h" trend="up" icon="⏱" />
      </div>
      <DataTable columns={COLS} rows={ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: support sidebar, 4 StatCards, tickets DataTable.")),
        assistant_turn(tool_call("message_result", text="Support dashboard: 4 KPI cards and open tickets table.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            tool_call("project_init", name="support-dashboard", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { Layout, DataTable } from './components'
import { useState } from 'react'
const NAV = [{ label: 'Tickets', href: '#' }]
export default function App() {
  const [active, setActive] = useState('Tickets')
  return (
    <Layout title="Support" navItems={NAV} activeNav={active} onNav={setActive}>
      <h2 className="text-xl font-semibold mb-4">Open Tickets: 42</h2>
      <DataTable columns={[]} rows={[]} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="Support dashboard without StatCards.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF03", "use <StatCard> not inline metric heading", "daf03-c")

# ═══════════════════════════════════════════════════════════════════════════
# DAF04 — raw <table> instead of <DataTable>
# ═══════════════════════════════════════════════════════════════════════════

def daf04_a():
    """Raw HTML table vs <DataTable>"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Create a sales dashboard with a leaderboard table of top reps."),
    ]
    chosen = [
        assistant_turn(
            tool_call("project_init", name="sales-dashboard", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable } from './components'

const NAV = [{ label: 'Leaderboard', href: '#' }, { label: 'Pipeline', href: '#pipe' }]
const COLS = [
  { key: 'rank', label: '#' }, { key: 'rep', label: 'Rep' },
  { key: 'deals', label: 'Deals' }, { key: 'revenue', label: 'Revenue' },
]
const ROWS = [
  { rank: '1', rep: 'Alice Brown', deals: 24, revenue: '$284,000' },
  { rank: '2', rep: 'Bob Chen',    deals: 19, revenue: '$226,000' },
  { rank: '3', rep: 'Carol Davis', deals: 17, revenue: '$198,000' },
]

export default function App() {
  const [active, setActive] = useState('Leaderboard')
  return (
    <Layout title="Sales" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard label="Total Deals"   value="142"    change="+11%" trend="up" icon="🤝" />
        <StatCard label="Revenue"       value="$1.68M" change="+9%"  trend="up" icon="💰" />
        <StatCard label="Quota Attain." value="107%"   change="+7%"  trend="up" icon="🎯" />
      </div>
      <DataTable columns={COLS} rows={ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: sales sidebar, 3 StatCards, leaderboard DataTable.")),
        assistant_turn(tool_call("message_result", text="Sales dashboard: 3 KPI cards and rep leaderboard DataTable.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            tool_call("project_init", name="sales-dashboard", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { Layout, StatCard } from './components'
import { useState } from 'react'
const NAV = [{ label: 'Leaderboard', href: '#' }]
export default function App() {
  const [active, setActive] = useState('Leaderboard')
  return (
    <Layout title="Sales" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard label="Total Deals" value="142" trend="up" />
      </div>
      <table className="w-full border-collapse">
        <thead><tr><th>Rep</th><th>Deals</th><th>Revenue</th></tr></thead>
        <tbody>
          <tr><td>Alice Brown</td><td>24</td><td>$284,000</td></tr>
        </tbody>
      </table>
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="Sales dashboard with raw HTML table.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF04", "use <DataTable> not raw <table>", "daf04-a")

def daf04_b():
    """Mapped <tr> rows vs <DataTable>"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Build a job board admin with listings stats and a job postings table."),
    ]
    chosen = [
        assistant_turn(
            tool_call("project_init", name="job-board-admin", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable } from './components'

const NAV = [{ label: 'Listings', href: '#' }, { label: 'Applications', href: '#apps' }]
const COLS = [
  { key: 'title', label: 'Title' }, { key: 'company', label: 'Company' },
  { key: 'location', label: 'Location' }, { key: 'apps', label: 'Applications' },
]
const ROWS = [
  { title: 'Senior Engineer', company: 'Acme Inc',  location: 'Remote', apps: 42 },
  { title: 'UX Designer',     company: 'DesignCo',  location: 'NYC',    apps: 28 },
  { title: 'Data Analyst',    company: 'DataFirm',  location: 'SF',     apps: 19 },
]

export default function App() {
  const [active, setActive] = useState('Listings')
  return (
    <Layout title="Job Board Admin" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard label="Active Listings" value="148"  change="+12" trend="up"   icon="📋" />
        <StatCard label="Applications"    value="2,340" change="+8%" trend="up"  icon="📩" />
        <StatCard label="Fill Rate"       value="68%"  change="+4%"  trend="up"  icon="✅" />
      </div>
      <DataTable columns={COLS} rows={ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: job board sidebar, 3 StatCards, job postings DataTable.")),
        assistant_turn(tool_call("message_result", text="Job board admin: 3 KPI cards and postings DataTable.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            tool_call("project_init", name="job-board-admin", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { Layout, StatCard } from './components'
import { useState } from 'react'
const JOBS = [
  { title: 'Senior Engineer', company: 'Acme Inc', apps: 42 },
  { title: 'UX Designer', company: 'DesignCo', apps: 28 },
]
const NAV = [{ label: 'Listings', href: '#' }]
export default function App() {
  const [active, setActive] = useState('Listings')
  return (
    <Layout title="Job Board" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-3 gap-4 mb-4">
        <StatCard label="Active Listings" value="148" trend="up" />
      </div>
      <table className="min-w-full">
        <thead><tr className="bg-gray-100"><th>Title</th><th>Company</th><th>Apps</th></tr></thead>
        <tbody>
          {JOBS.map(j => (
            <tr key={j.title}><td>{j.title}</td><td>{j.company}</td><td>{j.apps}</td></tr>
          ))}
        </tbody>
      </table>
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="Job board admin with mapped table rows.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF04", "use <DataTable> not mapped <tr> rows", "daf04-b")

def daf04_c():
    """Unordered list vs <DataTable>"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Create a delivery operations dashboard with delivery stats and a shipments table."),
    ]
    chosen = [
        assistant_turn(
            tool_call("project_init", name="delivery-ops", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable } from './components'

const NAV = [{ label: 'Shipments', href: '#' }, { label: 'Routes', href: '#routes' }]
const COLS = [
  { key: 'id', label: 'Shipment ID' }, { key: 'destination', label: 'Destination' },
  { key: 'carrier', label: 'Carrier' }, { key: 'status', label: 'Status' },
]
const ROWS = [
  { id: 'SHP-1042', destination: 'Chicago, IL', carrier: 'FedEx', status: 'In Transit' },
  { id: 'SHP-1043', destination: 'Austin, TX',  carrier: 'UPS',   status: 'Delivered' },
  { id: 'SHP-1044', destination: 'Seattle, WA', carrier: 'USPS',  status: 'Pending' },
]

export default function App() {
  const [active, setActive] = useState('Shipments')
  return (
    <Layout title="Delivery Ops" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="Active Shipments" value="284"  change="+14" trend="up"   icon="🚚" />
        <StatCard label="Delivered Today"  value="48"   change="+6"  trend="up"   icon="📦" />
        <StatCard label="Delayed"          value="12"   change="+2"  trend="down" icon="⚠️" />
        <StatCard label="On-Time Rate"     value="95.8%" change="+0.3%" trend="up" icon="✅" />
      </div>
      <DataTable columns={COLS} rows={ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: delivery sidebar, 4 StatCards, shipments DataTable.")),
        assistant_turn(tool_call("message_result", text="Delivery ops dashboard: 4 KPI cards, shipments DataTable.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            tool_call("project_init", name="delivery-ops", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { Layout, StatCard } from './components'
import { useState } from 'react'
const SHIPMENTS = [
  { id: 'SHP-1042', dest: 'Chicago', status: 'In Transit' },
  { id: 'SHP-1043', dest: 'Austin',  status: 'Delivered' },
]
const NAV = [{ label: 'Shipments', href: '#' }]
export default function App() {
  const [active, setActive] = useState('Shipments')
  return (
    <Layout title="Delivery Ops" navItems={NAV} activeNav={active} onNav={setActive}>
      <StatCard label="Active Shipments" value="284" trend="up" />
      <ul className="mt-4 space-y-2">
        {SHIPMENTS.map(s => (
          <li key={s.id} className="bg-white p-3 rounded border">{s.id} — {s.dest} — {s.status}</li>
        ))}
      </ul>
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="Delivery dashboard with list items.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF04", "use <DataTable> not unordered list", "daf04-c")

# ═══════════════════════════════════════════════════════════════════════════
# DAF05 — no undertow before message_result
# ═══════════════════════════════════════════════════════════════════════════

def daf05_a():
    """Skip undertow — jump straight to message_result"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Build a cloud cost dashboard with resource spend stats and a services table."),
    ]
    chosen = [
        assistant_turn(
            tool_call("project_init", name="cloud-cost", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable } from './components'

const NAV = [{ label: 'Costs', href: '#' }, { label: 'Budget', href: '#bud' }]
const COLS = [
  { key: 'service', label: 'Service' }, { key: 'cost', label: 'Monthly Cost' },
  { key: 'change', label: 'MoM Change' }, { key: 'owner', label: 'Owner' },
]
const ROWS = [
  { service: 'EC2',    cost: '$4,200', change: '+8%',  owner: 'Infra' },
  { service: 'RDS',    cost: '$1,800', change: '+3%',  owner: 'Infra' },
  { service: 'S3',     cost: '$340',   change: '+12%', owner: 'Platform' },
]

export default function App() {
  const [active, setActive] = useState('Costs')
  return (
    <Layout title="Cloud Costs" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard label="Total Spend"  value="$6,340"  change="+7%"  trend="down" icon="☁" />
        <StatCard label="Budget Left"  value="$1,660"  change="-7%"  trend="down" icon="💰" />
        <StatCard label="Cost/User"    value="$1.84"   change="+2%"  trend="down" icon="👤" />
      </div>
      <DataTable columns={COLS} rows={ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: cloud cost sidebar, 3 StatCards, services DataTable.")),
        assistant_turn(tool_call("message_result", text="Cloud cost dashboard: 3 KPI cards and services table.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            tool_call("project_init", name="cloud-cost", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable } from './components'
const NAV = [{ label: 'Costs', href: '#' }]
export default function App() {
  const [active, setActive] = useState('Costs')
  return (
    <Layout title="Cloud Costs" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard label="Total Spend" value="$6,340" trend="down" />
      </div>
      <DataTable columns={[]} rows={[]} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="Cloud cost dashboard done — no screenshot taken.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF05", "always call undertow() before message_result", "daf05-a")

def daf05_b():
    """Shell check instead of undertow"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Build a server monitoring dashboard with uptime stats and an alerts table."),
    ]
    chosen = [
        assistant_turn(
            tool_call("project_init", name="server-monitor", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable } from './components'

const NAV = [{ label: 'Overview', href: '#' }, { label: 'Alerts', href: '#alerts' }]
const COLS = [
  { key: 'server', label: 'Server' }, { key: 'alert', label: 'Alert' },
  { key: 'severity', label: 'Severity' }, { key: 'time', label: 'Time' },
]
const ROWS = [
  { server: 'web-01', alert: 'CPU > 90%',         severity: 'Critical', time: '14:32' },
  { server: 'db-01',  alert: 'Slow query detected', severity: 'Warning',  time: '14:18' },
  { server: 'api-02', alert: 'Memory > 80%',        severity: 'Warning',  time: '13:55' },
]

export default function App() {
  const [active, setActive] = useState('Overview')
  return (
    <Layout title="Server Monitor" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="Servers Online" value="24"  change="0"   trend="up"   icon="🖥" />
        <StatCard label="Alerts"         value="3"   change="+2"  trend="down" icon="🚨" />
        <StatCard label="Avg CPU"        value="42%" change="+5%" trend="down" icon="⚙" />
        <StatCard label="Avg Uptime"     value="99.8%" change="+0.1%" trend="up" icon="✅" />
      </div>
      <DataTable columns={COLS} rows={ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: server monitor sidebar, 4 StatCards, alerts DataTable.")),
        assistant_turn(tool_call("message_result", text="Server monitoring dashboard: 4 KPI cards, active alerts table.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            tool_call("project_init", name="server-monitor", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { Layout } from './components'
import { useState } from 'react'
export default function App() {
  const [active, setActive] = useState('Overview')
  return <Layout title="Server Monitor" navItems={[]} activeNav={active} onNav={setActive}><p>Loading...</p></Layout>
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(
            text("Checking that the server starts."),
            tool_call("shell_exec", cmd="curl -s http://localhost:5173 | head -5"),
        ),
        user_turn(tool_result("<html>Vite dev server OK</html>")),
        assistant_turn(tool_call("message_result", text="Server monitoring dashboard started — checked via curl.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF05", "undertow screenshot not shell curl before message_result", "daf05-b")

def daf05_c():
    """No verification at all — just writes then delivers"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Build a content moderation dashboard with moderation queue stats and flagged posts table."),
    ]
    chosen = [
        assistant_turn(
            tool_call("project_init", name="content-mod", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable } from './components'

const NAV = [{ label: 'Queue', href: '#' }, { label: 'History', href: '#hist' }]
const COLS = [
  { key: 'post', label: 'Post' }, { key: 'user', label: 'User' },
  { key: 'reason', label: 'Flag Reason' }, { key: 'status', label: 'Status' },
]
const ROWS = [
  { post: '#84291', user: 'user_392',  reason: 'Spam',       status: 'Pending' },
  { post: '#84287', user: 'user_1204', reason: 'Harassment', status: 'Under Review' },
  { post: '#84280', user: 'user_856',  reason: 'Misinformation', status: 'Pending' },
]

export default function App() {
  const [active, setActive] = useState('Queue')
  return (
    <Layout title="Content Mod" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="Pending"     value="142"  change="+18"  trend="down" icon="⏳" />
        <StatCard label="Reviewed Today" value="84" change="+12" trend="up"   icon="✅" />
        <StatCard label="Escalated"   value="7"    change="+2"   trend="down" icon="🚨" />
        <StatCard label="False Positives" value="3%" change="-1%" trend="up"  icon="📊" />
      </div>
      <DataTable columns={COLS} rows={ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: content mod sidebar, 4 StatCards, flagged posts DataTable.")),
        assistant_turn(tool_call("message_result", text="Content moderation dashboard: 4 KPI cards, flagged posts table.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            tool_call("project_init", name="content-mod", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { Layout, StatCard } from './components'
import { useState } from 'react'
const NAV = [{ label: 'Queue', href: '#' }]
export default function App() {
  const [a, sa] = useState('Queue')
  return <Layout title="Mod" navItems={NAV} activeNav={a} onNav={sa}><StatCard label="Pending" value="142" trend="down" /></Layout>
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="Content moderation dashboard — no visual verification done.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF05", "always undertow() before message_result, no skipping", "daf05-c")

# ═══════════════════════════════════════════════════════════════════════════
# DAF06 — writing main.tsx / vite.config / index.html instead of App.tsx only
# ═══════════════════════════════════════════════════════════════════════════

def daf06_a():
    """Writing main.tsx alongside App.tsx"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Build a SaaS billing dashboard with MRR stats and subscriptions table."),
    ]
    chosen = [
        assistant_turn(
            tool_call("project_init", name="billing-dashboard", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable } from './components'

const NAV = [{ label: 'Billing', href: '#' }, { label: 'Customers', href: '#cust' }]
const COLS = [
  { key: 'customer', label: 'Customer' }, { key: 'plan', label: 'Plan' },
  { key: 'mrr', label: 'MRR' }, { key: 'status', label: 'Status' },
]
const ROWS = [
  { customer: 'Acme Inc',   plan: 'Pro',        mrr: '$299', status: 'Active' },
  { customer: 'StartupXY',  plan: 'Business',   mrr: '$599', status: 'Active' },
  { customer: 'MegaCorp',   plan: 'Enterprise', mrr: '$1,999', status: 'Active' },
]

export default function App() {
  const [active, setActive] = useState('Billing')
  return (
    <Layout title="Billing" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="MRR"         value="$28,400" change="+6%"  trend="up" icon="💰" />
        <StatCard label="ARR"         value="$340,800" change="+6%" trend="up" icon="📈" />
        <StatCard label="Churn Rate"  value="2.1%"    change="-0.3%" trend="up" icon="🔄" />
        <StatCard label="Subscribers" value="142"     change="+8"   trend="up" icon="👥" />
      </div>
      <DataTable columns={COLS} rows={ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written: src/App.tsx")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: billing sidebar, 4 StatCards, subscriptions DataTable.")),
        assistant_turn(tool_call("message_result", text="SaaS billing dashboard: 4 KPI cards, subscriptions DataTable.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            tool_call("project_init", name="billing-dashboard", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/main.tsx", content="""import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)"""),
        ),
        user_turn(tool_result("Written: src/main.tsx")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { Layout } from './components'
import { useState } from 'react'
export default function App() {
  const [a, sa] = useState('Billing')
  return <Layout title="Billing" navItems={[]} activeNav={a} onNav={sa}><p>Billing dashboard</p></Layout>
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="Billing dashboard with main.tsx.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF06", "only write App.tsx; scaffold generates main.tsx, vite.config, index.html", "daf06-a")

def daf06_b():
    """Writing vite.config.ts"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Create an API monitoring dashboard with latency stats and endpoint health table."),
    ]
    chosen = [
        assistant_turn(
            tool_call("project_init", name="api-monitor", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable } from './components'

const NAV = [{ label: 'Endpoints', href: '#' }, { label: 'Alerts', href: '#alerts' }]
const COLS = [
  { key: 'endpoint', label: 'Endpoint' }, { key: 'p50', label: 'P50 ms' },
  { key: 'p99', label: 'P99 ms' }, { key: 'status', label: 'Status' },
]
const ROWS = [
  { endpoint: 'GET /api/users',    p50: '42ms',  p99: '180ms', status: 'Healthy' },
  { endpoint: 'POST /api/orders',  p50: '84ms',  p99: '340ms', status: 'Degraded' },
  { endpoint: 'GET /api/products', p50: '28ms',  p99: '110ms', status: 'Healthy' },
]

export default function App() {
  const [active, setActive] = useState('Endpoints')
  return (
    <Layout title="API Monitor" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="Total Req/s"  value="2,840"  change="+12%" trend="up"   icon="📡" />
        <StatCard label="Error Rate"   value="0.12%"  change="-0.04%" trend="up" icon="⚠️" />
        <StatCard label="P50 Latency"  value="48ms"   change="+3ms" trend="down" icon="⚡" />
        <StatCard label="Uptime"       value="99.97%" change="+0.01%" trend="up" icon="✅" />
      </div>
      <DataTable columns={COLS} rows={ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written: src/App.tsx")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: API monitor sidebar, 4 StatCards, endpoints table.")),
        assistant_turn(tool_call("message_result", text="API monitoring dashboard: 4 KPI cards, endpoint health table.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            tool_call("project_init", name="api-monitor", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="vite.config.ts", content="""import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({ plugins: [react()] })"""),
        ),
        user_turn(tool_result("Written: vite.config.ts")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { Layout } from './components'
import { useState } from 'react'
export default function App() {
  const [a, sa] = useState('Endpoints')
  return <Layout title="API Monitor" navItems={[]} activeNav={a} onNav={sa}><p>Endpoints here.</p></Layout>
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="API monitor with vite.config.ts.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF06", "only write App.tsx; do not write vite.config.ts", "daf06-b")

def daf06_c():
    """Writing index.html"""
    prompt = [
        {"role": "system", "content": SYSTEM},
        user_turn("Build a CI/CD pipeline dashboard with build stats and a runs history table."),
    ]
    chosen = [
        assistant_turn(
            tool_call("project_init", name="cicd-dashboard", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { useState } from 'react'
import { Layout, StatCard, DataTable } from './components'

const NAV = [{ label: 'Pipelines', href: '#' }, { label: 'Deployments', href: '#dep' }]
const COLS = [
  { key: 'pipeline', label: 'Pipeline' }, { key: 'branch', label: 'Branch' },
  { key: 'status', label: 'Status' }, { key: 'duration', label: 'Duration' },
]
const ROWS = [
  { pipeline: 'frontend',  branch: 'main',         status: 'Passed',  duration: '3m 12s' },
  { pipeline: 'backend',   branch: 'feature/auth',  status: 'Failed',  duration: '1m 48s' },
  { pipeline: 'ml-train',  branch: 'main',          status: 'Running', duration: '12m 04s' },
]

export default function App() {
  const [active, setActive] = useState('Pipelines')
  return (
    <Layout title="CI/CD" navItems={NAV} activeNav={active} onNav={setActive}>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="Total Runs"    value="284"    change="+22"   trend="up"   icon="🔄" />
        <StatCard label="Pass Rate"     value="94.0%"  change="+1.2%" trend="up"   icon="✅" />
        <StatCard label="Avg Duration"  value="4m 20s" change="-15s"  trend="up"   icon="⏱" />
        <StatCard label="Deployments"   value="18"     change="+3"    trend="up"   icon="🚀" />
      </div>
      <DataTable columns={COLS} rows={ROWS} />
    </Layout>
  )
}"""),
        ),
        user_turn(tool_result("Written: src/App.tsx")),
        assistant_turn(tool_call("undertow", url="http://localhost:5173")),
        user_turn(tool_result("Screenshot: CI/CD sidebar, 4 StatCards, pipeline runs table.")),
        assistant_turn(tool_call("message_result", text="CI/CD dashboard: 4 KPI cards, pipeline runs table.")),
        user_turn(tool_result("Delivered.")),
    ]
    rejected = [
        assistant_turn(
            tool_call("project_init", name="cicd-dashboard", template="dashboard"),
        ),
        user_turn(tool_result("Scaffolded.")),
        assistant_turn(
            tool_call("file_write", path="index.html", content="""<!doctype html>
<html lang="en">
  <head><meta charset="UTF-8" /><title>CI/CD Dashboard</title></head>
  <body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body>
</html>"""),
        ),
        user_turn(tool_result("Written: index.html")),
        assistant_turn(
            tool_call("file_write", path="src/App.tsx", content="""import { Layout } from './components'
import { useState } from 'react'
export default function App() {
  const [a, sa] = useState('Pipelines')
  return <Layout title="CI/CD" navItems={[]} activeNav={a} onNav={sa}><p>Builds here.</p></Layout>
}"""),
        ),
        user_turn(tool_result("Written.")),
        assistant_turn(tool_call("message_result", text="CI/CD dashboard with index.html.")),
        user_turn(tool_result("Delivered.")),
    ]
    return make_pair(prompt, chosen, rejected,
        "DAF06", "only write App.tsx; do not write index.html", "daf06-c")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

BUILDERS = [
    daf01_a, daf01_b, daf01_c,
    daf02_a, daf02_b, daf02_c,
    daf03_a, daf03_b, daf03_c,
    daf04_a, daf04_b, daf04_c,
    daf05_a, daf05_b, daf05_c,
    daf06_a, daf06_b, daf06_c,
]

pairs = [b() for b in BUILDERS]
with OUT_FILE.open("w") as f:
    for p in pairs:
        f.write(json.dumps(p) + "\n")

print(f"\n=== DASHBOARD DPO v1 SUMMARY ===")
print(f"  Pairs: {len(pairs)}")
print(f"  Output: {OUT_FILE}")
for p in pairs:
    print(f"  {p['source']:12s}  {p['source_bug']}  — {p['note']}")
