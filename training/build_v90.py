#!/usr/bin/env python3
"""build_v90.py — v89 + 6 error-recovery + reference + plan SFT trajectories.

Targeting eval_report_v9 failures:
  ER02/03/06: type/syntax/import errors → file_edit DIRECTLY (not file_read)
  ER05:       wrong cd path → shell_exec with correct deliverables/ path
  HF02:       visual clone → search_web first (not project_init)
  HF09:       "plan carefully" → plan_update first (not project_init)

These complement DPO v5 pairs with full successful trajectories.
"""
import json, os, sys
from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v90.jsonl"


def tokenize(msgs):
    tok = AutoTokenizer.from_pretrained(MODEL)
    return tok.apply_chat_template(msgs, tools=TOOLS, tokenize=False)


def sys_msg():
    return {"role": "system", "content": SYSTEM_TEXT}

def u(t):
    return {"role": "user", "content": t}

def tc(tool_name, **kw):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"type": "function", "function": {"name": tool_name, "arguments": kw}}
    ]}

def tr(name, content):
    return {"role": "tool", "name": name, "content": content}


# ── ER02: Type error → file_edit immediately ─────────────────────────────────

def er02_recovery():
    """Full trajectory: type error in build output → file_edit directly."""
    return [
        sys_msg(),
        u("Build a search results page with error handling."),
        tc("project_init", name="search-results"),
        tr("project_init", "Scaffolded 'search-results'. Write src/App.tsx."),
        tc("file_write", path="deliverables/search-results/src/App.tsx",
            content="""import { useState } from 'react'
export default function App() {
  const [query, setQuery] = useState('')
  const [error, setError] = useState<string>('')
  const [results, setResults] = useState<string[]>([])
  async function search() {
    try {
      const res = await fetch(`/api/search?q=${query}`)
      const data = await res.json()
      setResults(data.results)
      setError('')
    } catch (e) {
      setError(null)
    }
  }
  return (
    <div className="p-6">
      <input value={query} onChange={e=>setQuery(e.target.value)} className="border p-2 mr-2" />
      <button onClick={search} className="bg-blue-500 text-white px-4 py-2">Search</button>
      {error && <p className="text-red-500 mt-2">{error}</p>}
      <ul className="mt-4">{results.map((r,i)=><li key={i}>{r}</li>)}</ul>
    </div>
  )
}"""),
        tr("file_write", "Written: deliverables/search-results/src/App.tsx"),
        tc("shell_exec", command="cd deliverables/search-results && npm run build"),
        tr("shell_exec", "[shell_exec] Error: src/App.tsx(11,7): Type 'null' is not assignable to type 'string'. setError(null) should be setError('')"),
        # ← Reef: type error — fix directly with file_edit. No file_read.
        tc("file_edit", path="deliverables/search-results/src/App.tsx",
            old_text="      setError(null)",
            new_text="      setError('')"),
        tr("file_edit", "Edited."),
        tc("shell_exec", command="cd deliverables/search-results && npm run build"),
        tr("shell_exec", "Build successful. dist/index.html ready."),
        tc("undertow", url="http://localhost:5173"),
        tr("undertow", "Screenshot: search input, button, results list. Error display works."),
        tc("message_result", text="Search results page with error handling. Type in the search box and hit Search to query /api/search."),
        tr("message_result", "Delivered."),
    ]


# ── ER03: Syntax error → file_edit immediately ───────────────────────────────

def er03_recovery():
    """Full trajectory: syntax error → file_edit directly."""
    return [
        sys_msg(),
        u("Build a todo list with done/undone toggle."),
        tc("project_init", name="todo-app"),
        tr("project_init", "Scaffolded 'todo-app'. Write src/App.tsx."),
        tc("file_write", path="deliverables/todo-app/src/App.tsx",
            content="""import { useState } from 'react'
interface Todo { id: number; text: string; done: boolean }
export default function App() {
  const [todos, setTodos] = useState<Todo[]>([
    { id: 1, text: 'Buy groceries', done: false },
    { id: 2, text: 'Walk the dog', done: true },
  ])
  const [input, setInput] = useState('')
  function add() {
    if (!input.trim()) return
    setTodos([...todos, { id: Date.now(), text: input, done: false }])
    setInput('')
  }
  function toggle(id: number) {
    setTodos(todos.map(t => t.id===id ? { ...t, done: !t.done } : t)
  }
  return (
    <div className="max-w-sm mx-auto p-6">
      <h1 className="text-2xl font-bold mb-4">Todos</h1>
      <div className="flex gap-2 mb-4">
        <input value={input} onChange={e=>setInput(e.target.value)} className="border flex-1 p-2" />
        <button onClick={add} className="bg-blue-500 text-white px-4">Add</button>
      </div>
      <ul>{todos.map(t=><li key={t.id} className={t.done?'line-through':''} onClick={()=>toggle(t.id)}>{t.text}</li>)}</ul>
    </div>
  )
}"""),
        tr("file_write", "Written."),
        tc("shell_exec", command="cd deliverables/todo-app && npm run build"),
        tr("shell_exec", "[shell_exec] Error: src/App.tsx(16,3): Expected ')' to close '(' at line 15. setTodos(todos.map(t => t.id===id ? { ...t, done: !t.done } : t)"),
        # ← Reef: missing closing paren — fix directly with file_edit
        tc("file_edit", path="deliverables/todo-app/src/App.tsx",
            old_text="    setTodos(todos.map(t => t.id===id ? { ...t, done: !t.done } : t)\n  }",
            new_text="    setTodos(todos.map(t => t.id===id ? { ...t, done: !t.done } : t))\n  }"),
        tr("file_edit", "Edited."),
        tc("shell_exec", command="cd deliverables/todo-app && npm run build"),
        tr("shell_exec", "Build successful."),
        tc("undertow", url="http://localhost:5173"),
        tr("undertow", "Screenshot: todo list, 2 items, one crossed out. Add input visible."),
        tc("message_result", text="Todo list: type to add items, click to toggle done/undone."),
        tr("message_result", "Delivered."),
    ]


# ── ER06: Unresolved import → file_edit immediately ──────────────────────────

def er06_recovery():
    """Full trajectory: unresolved import → file_edit to fix (not file_read)."""
    return [
        sys_msg(),
        u("Build a chart dashboard using recharts."),
        tc("project_init", name="chart-dashboard"),
        tr("project_init", "Scaffolded 'chart-dashboard'. Write src/App.tsx."),
        tc("file_write", path="deliverables/chart-dashboard/src/App.tsx",
            content="""import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'react-charts'
const DATA = [
  { name: 'Jan', revenue: 4200 }, { name: 'Feb', revenue: 5600 },
  { name: 'Mar', revenue: 3800 }, { name: 'Apr', revenue: 6100 },
]
export default function App() {
  return (
    <div className="p-6">
      <h1 className="text-xl font-bold mb-4">Revenue Dashboard</h1>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={DATA}>
          <XAxis dataKey="name" /><YAxis /><Tooltip />
          <Bar dataKey="revenue" fill="#6366f1" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}"""),
        tr("file_write", "Written."),
        tc("shell_exec", command="cd deliverables/chart-dashboard && npm run build"),
        tr("shell_exec", "[shell_exec] Error: Could not resolve 'react-charts' from src/App.tsx. Did you mean 'recharts'? Update the import."),
        # ← Reef: wrong package name — fix import directly. The error tells us the fix.
        tc("file_edit", path="deliverables/chart-dashboard/src/App.tsx",
            old_text="import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'react-charts'",
            new_text="import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'"),
        tr("file_edit", "Edited."),
        tc("shell_exec", command="cd deliverables/chart-dashboard && npm run build"),
        tr("shell_exec", "Build successful."),
        tc("undertow", url="http://localhost:5173"),
        tr("undertow", "Screenshot: bar chart, 4 months of revenue data, blue bars, axis labels."),
        tc("message_result", text="Revenue dashboard with a Recharts bar chart showing monthly revenue data."),
        tr("message_result", "Delivered."),
    ]


# ── ER05: Wrong path → shell_exec with correct deliverables/ path ─────────────

def er05_recovery():
    """Full trajectory: wrong cd path → shell_exec with correct path."""
    return [
        sys_msg(),
        u("Build a pomodoro timer app."),
        tc("project_init", name="pomodoro-timer"),
        tr("project_init", "Scaffolded 'pomodoro-timer' in deliverables/pomodoro-timer."),
        tc("file_write", path="deliverables/pomodoro-timer/src/App.tsx",
            content="""import { useState, useEffect, useRef } from 'react'
const WORK = 25 * 60, BREAK = 5 * 60
export default function App() {
  const [mode, setMode] = useState<'work'|'break'>('work')
  const [time, setTime] = useState(WORK)
  const [running, setRunning] = useState(false)
  const intervalRef = useRef<number|null>(null)
  useEffect(() => {
    if (running) {
      intervalRef.current = setInterval(() => {
        setTime(t => {
          if (t <= 1) {
            setMode(m => m === 'work' ? 'break' : 'work')
            return mode === 'work' ? BREAK : WORK
          }
          return t - 1
        })
      }, 1000)
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [running, mode])
  const mm = String(Math.floor(time/60)).padStart(2,'0')
  const ss = String(time%60).padStart(2,'0')
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white">
      <h1 className="text-2xl font-bold mb-2">{mode === 'work' ? 'Focus' : 'Break'}</h1>
      <div className="text-8xl font-mono mb-8">{mm}:{ss}</div>
      <div className="flex gap-4">
        <button onClick={()=>setRunning(r=>!r)} className="px-6 py-3 bg-indigo-600 rounded-lg text-lg">
          {running ? 'Pause' : 'Start'}
        </button>
        <button onClick={()=>{setRunning(false);setTime(WORK);setMode('work')}}
          className="px-6 py-3 bg-gray-600 rounded-lg text-lg">Reset</button>
      </div>
    </div>
  )
}"""),
        tr("file_write", "Written."),
        tc("shell_exec", command="cd pomodoro-timer && npm run build"),
        tr("shell_exec", "[shell_exec] Error: No such file or directory: pomodoro-timer. Projects are in deliverables/. Try: cd deliverables/pomodoro-timer && npm run build"),
        # ← Reef: wrong path — re-run with correct deliverables/ prefix
        tc("shell_exec", command="cd deliverables/pomodoro-timer && npm run build"),
        tr("shell_exec", "Build successful."),
        tc("undertow", url="http://localhost:5173"),
        tr("undertow", "Screenshot: dark background, large 25:00 countdown, Focus label, Start and Reset buttons."),
        tc("message_result", text="Pomodoro timer: 25-min work sessions, 5-min breaks. Start/Pause/Reset controls. Dark UI."),
        tr("message_result", "Delivered."),
    ]


# ── HF02: Visual/reference clone → search_web first ────────────────────────���─

def hf02_research():
    """Full trajectory: 'like X' prompt → search_web first."""
    return [
        sys_msg(),
        u("Build a budget tracker app styled like Mint.com — clean categories, spending breakdown, budget bars."),
        # Visual clone signal: "like Mint.com" → search for reference first
        tc("search_web", query="Mint.com budget tracker UI design categories spending breakdown"),
        tr("search_web", "Mint.com: color-coded spending categories (housing, food, entertainment), circular budget ring, monthly trend bars, alert badges for over-budget. Clean card layout, green/red color coding."),
        tc("project_init", name="budget-tracker"),
        tr("project_init", "Scaffolded 'budget-tracker'. Write src/App.tsx."),
        tc("file_write", path="deliverables/budget-tracker/src/App.tsx",
            content="""import { useState } from 'react'
const CATEGORIES = [
  { name: 'Housing',       budget: 1500, spent: 1500, color: '#6366f1' },
  { name: 'Food',          budget: 600,  spent: 420,  color: '#22c55e' },
  { name: 'Transport',     budget: 300,  spent: 340,  color: '#ef4444' },
  { name: 'Entertainment', budget: 200,  spent: 95,   color: '#f59e0b' },
  { name: 'Health',        budget: 150,  spent: 80,   color: '#06b6d4' },
]
export default function App() {
  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Budget Overview — April 2026</h1>
      <div className="grid gap-4 max-w-2xl">
        {CATEGORIES.map(c => {
          const pct = Math.min(100, Math.round(c.spent / c.budget * 100))
          const over = c.spent > c.budget
          return (
            <div key={c.name} className="bg-white rounded-xl p-4 shadow-sm">
              <div className="flex justify-between items-center mb-2">
                <span className="font-medium text-gray-800">{c.name}</span>
                <span className={over ? 'text-red-500 font-medium' : 'text-gray-600'}>
                  ${c.spent} <span className="text-gray-400">/ ${c.budget}</span>
                </span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all"
                  style={{ width: `${pct}%`, background: over ? '#ef4444' : c.color }} />
              </div>
              {over && <p className="text-red-500 text-xs mt-1">⚠ Over budget by ${c.spent - c.budget}</p>}
            </div>
          )
        })}
      </div>
    </div>
  )
}"""),
        tr("file_write", "Written."),
        tc("shell_exec", command="cd deliverables/budget-tracker && npm run build"),
        tr("shell_exec", "Build successful."),
        tc("undertow", url="http://localhost:5173"),
        tr("undertow", "Screenshot: Mint-style budget tracker. 5 category cards with color-coded budget bars. Transport shows red over-budget warning. Clean card layout on gray background."),
        tc("message_result", text="Budget tracker inspired by Mint.com: 5 spending categories with budget progress bars, over-budget warnings in red, color-coded by category."),
        tr("message_result", "Delivered."),
    ]


# ── HF09: "Plan carefully" → plan_update first ─────────────────────────────���─

def hf09_plan():
    """Full trajectory: complex multi-system request → plan_update first."""
    return [
        sys_msg(),
        u("Build a project management tool with a Kanban board, task details modal, team member assignment, and deadline tracking. Plan carefully before building."),
        # Complex + "plan carefully" → plan_update first
        tc("plan_update",
            goal="Project management tool: Kanban + task modal + assignments + deadlines",
            phases=[
                {"phase": 1, "action": "project_init", "note": "Scaffold react-app"},
                {"phase": 2, "action": "file_write App.tsx", "note": "Board with 3 columns (Todo/In Progress/Done), drag-to-move cards"},
                {"phase": 3, "action": "file_write TaskModal.tsx", "note": "Modal with title, desc, assignee dropdown, deadline date picker"},
                {"phase": 4, "action": "shell_exec build + undertow QA"},
            ]),
        tr("plan_update", "Plan saved."),
        tc("project_init", name="project-manager"),
        tr("project_init", "Scaffolded 'project-manager'. Write src/App.tsx."),
        tc("file_write", path="deliverables/project-manager/src/App.tsx",
            content="""import { useState } from 'react'
import TaskModal from './TaskModal'
interface Task { id:number; title:string; assignee:string; deadline:string; col:'todo'|'doing'|'done' }
const INIT:Task[] = [
  { id:1, title:'Design system setup',   assignee:'Alice', deadline:'2026-04-20', col:'done' },
  { id:2, title:'API integration',       assignee:'Bob',   deadline:'2026-04-25', col:'doing' },
  { id:3, title:'Write unit tests',      assignee:'Carol', deadline:'2026-04-30', col:'todo' },
  { id:4, title:'Deploy to staging',     assignee:'Alice', deadline:'2026-05-01', col:'todo' },
]
const COLS:{key:Task['col'],label:string}[] = [
  {key:'todo',label:'To Do'},{key:'doing',label:'In Progress'},{key:'done',label:'Done'}
]
const MEMBERS = ['Alice','Bob','Carol','Dave']
export default function App() {
  const [tasks, setTasks] = useState<Task[]>(INIT)
  const [selected, setSelected] = useState<Task|null>(null)
  const [drag, setDrag] = useState<number|null>(null)
  function moveTask(id:number, col:Task['col']) {
    setTasks(ts=>ts.map(t=>t.id===id?{...t,col}:t))
  }
  function updateTask(updated:Task) {
    setTasks(ts=>ts.map(t=>t.id===updated.id?updated:t))
    setSelected(null)
  }
  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      <h1 className="text-2xl font-bold mb-6">Project Board</h1>
      <div className="grid grid-cols-3 gap-4">
        {COLS.map(col=>(
          <div key={col.key} className="bg-gray-800 rounded-xl p-4 min-h-64"
            onDragOver={e=>e.preventDefault()}
            onDrop={()=>{ if(drag!==null)moveTask(drag,col.key); setDrag(null) }}>
            <h2 className="font-semibold mb-3 text-gray-300">{col.label}
              <span className="ml-2 text-xs bg-gray-700 px-2 py-0.5 rounded-full">
                {tasks.filter(t=>t.col===col.key).length}
              </span>
            </h2>
            {tasks.filter(t=>t.col===col.key).map(task=>(
              <div key={task.id} draggable
                onDragStart={()=>setDrag(task.id)}
                onClick={()=>setSelected(task)}
                className="bg-gray-700 rounded-lg p-3 mb-2 cursor-pointer hover:bg-gray-600">
                <p className="font-medium">{task.title}</p>
                <div className="flex justify-between text-xs text-gray-400 mt-1">
                  <span>👤 {task.assignee}</span>
                  <span>📅 {task.deadline}</span>
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
      {selected && <TaskModal task={selected} members={MEMBERS} onSave={updateTask} onClose={()=>setSelected(null)} />}
    </div>
  )
}"""),
        tr("file_write", "Written: src/App.tsx"),
        tc("file_write", path="deliverables/project-manager/src/TaskModal.tsx",
            content="""interface Task { id:number; title:string; assignee:string; deadline:string; col:'todo'|'doing'|'done' }
interface Props { task:Task; members:string[]; onSave:(t:Task)=>void; onClose:()=>void }
export default function TaskModal({ task, members, onSave, onClose }:Props) {
  const [title, setTitle] = useState(task.title)
  const [assignee, setAssignee] = useState(task.assignee)
  const [deadline, setDeadline] = useState(task.deadline)
  import { useState } from 'react'
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-gray-800 rounded-2xl p-6 w-96" onClick={e=>e.stopPropagation()}>
        <h2 className="text-lg font-bold mb-4">Edit Task</h2>
        <label className="block mb-3">
          <span className="text-gray-400 text-sm">Title</span>
          <input value={title} onChange={e=>setTitle(e.target.value)}
            className="block w-full mt-1 bg-gray-700 border border-gray-600 rounded-lg p-2 text-white" />
        </label>
        <label className="block mb-3">
          <span className="text-gray-400 text-sm">Assignee</span>
          <select value={assignee} onChange={e=>setAssignee(e.target.value)}
            className="block w-full mt-1 bg-gray-700 border border-gray-600 rounded-lg p-2 text-white">
            {members.map(m=><option key={m}>{m}</option>)}
          </select>
        </label>
        <label className="block mb-4">
          <span className="text-gray-400 text-sm">Deadline</span>
          <input type="date" value={deadline} onChange={e=>setDeadline(e.target.value)}
            className="block w-full mt-1 bg-gray-700 border border-gray-600 rounded-lg p-2 text-white" />
        </label>
        <div className="flex gap-3">
          <button onClick={()=>onSave({...task,title,assignee,deadline})}
            className="flex-1 bg-indigo-600 hover:bg-indigo-700 rounded-lg py-2 font-medium">Save</button>
          <button onClick={onClose}
            className="flex-1 bg-gray-600 hover:bg-gray-500 rounded-lg py-2">Cancel</button>
        </div>
      </div>
    </div>
  )
}"""),
        tr("file_write", "Written: src/TaskModal.tsx"),
        tc("shell_exec", command="cd deliverables/project-manager && npm run build"),
        tr("shell_exec", "Build successful."),
        tc("undertow", url="http://localhost:5173"),
        tr("undertow", "Screenshot: 3-column Kanban board, dark theme. Cards show task, assignee, and deadline. One card selected, showing edit modal with assignee dropdown and date picker."),
        tc("message_result", text="Project management board: Kanban with To Do/In Progress/Done columns, drag-and-drop cards, click any card to edit title/assignee/deadline in a modal."),
        tr("message_result", "Delivered."),
    ]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading tokenizer...")
    tok = AutoTokenizer.from_pretrained(MODEL)
    print("Tokenizer loaded.")

    # Load existing v89 examples
    v89_examples = []
    v89_path = "workspace/training_data/e4b_toolcall_train_v89.jsonl"
    if os.path.exists(v89_path):
        with open(v89_path) as f:
            v89_examples = [json.loads(l) for l in f if l.strip()]
    print(f"Loaded {len(v89_examples)} examples from v89")

    # Build new examples
    new_builders = [
        er02_recovery,
        er03_recovery,
        er06_recovery,
        er05_recovery,
        hf02_research,
        hf09_plan,
    ]

    new_examples = []
    for fn in new_builders:
        msgs = fn()
        text = tok.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        new_examples.append({"text": text, "source": fn.__name__})
        print(f"  {fn.__name__}: {len(msgs)} messages → {len(text)} chars")

    all_examples = v89_examples + new_examples

    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in all_examples:
            f.write(json.dumps(ex) + "\n")

    print(f"\nTotal: {len(all_examples)} examples ({len(v89_examples)} from v89 + {len(new_examples)} new)")
    print(f"Wrote to {OUT_PATH}")

if __name__ == "__main__":
    main()
