#!/usr/bin/env python3
"""Form-app SFT examples v1 — 6 training examples for the form-app adapter.

Uses scaffolds/form-app/ (Vite + React + FileDropzone + DataTable + parseFile + exportCsv).
Pipeline: project_init(template="form-app") → file_write(src/App.tsx) → build → undertow → result.

FA01: CSV Explorer — upload CSV → DataTable with search/sort/export
FA02: Multi-step form wizard — 3 steps (info → details → review+submit)
FA03: XLSX Analyzer — upload Excel → parse sheets → tabbed DataTable views
FA04: Data entry tracker — form → add rows to table → exportCsv download
FA05: Error recovery — fetch() for CSV → build warning → file_edit to parseFile
FA06: Conversational routing — question → message_chat

Usage:
  /usr/bin/python3 training/build_formapp_v1.py
  Output: workspace/training_data/formapp_sft_v1.jsonl
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
    "- current: your sense of direction. If uncertain, search first.\n"
    "- circulation: routing. Low tension=deliver. High tension=search or refuse.\n"
    "- pressure: sustained uncertainty. 2 failures=search. 4 failures=ask the user.\n"
    "- eddies: parallel workers. 3+ components=dispatch swell.\n"
    "- undertow: QA. ALWAYS verify before delivering.\n"
    "- break: compile. shell_exec build after EVERY file_write.\n"
    "- reef: error. Fix directly. Type/syntax -> file_edit. Missing module -> shell_exec npm install. "
    "Missing file -> file_write. Wrong path (cd fails) -> shell_exec with corrected path (NEVER message_chat). "
    "CSS resolution errors -> file_edit to remove/replace the import.\n\n"
    "FORM-APP PIPELINE (file upload / data table apps follow this EXACTLY):\n"
    "1. project_init(name, template='form-app')\n"
    "2. file_write(src/App.tsx) -- import FileDropzone, DataTable, parseFile, exportCsv\n"
    "3. shell_exec -- npm run build\n"
    "4. IF ERROR: fix directly\n"
    "5. undertow -- QA before delivery\n"
    "6. message_result -- land the wave\n\n"
    "FORM-APP RULES:\n"
    "- ALWAYS template='form-app' in project_init\n"
    "- ALWAYS use parseFile(file) for CSV/Excel — NEVER fetch() a file\n"
    "- ALWAYS use <DataTable columns={...} rows={...} /> — never raw <table>\n"
    "- ALWAYS use exportCsv(columns, rows, 'name.csv') for downloads\n"
    "- NEVER overwrite main.tsx, vite.config.ts, or index.css\n"
    "- NEVER skip undertow before message_result\n\n"
    "NEVER skip the break. NEVER deliver without building. One tool call per response. Be brief."
)

TOOLS = [
    {"type": "function", "function": {"name": "project_init", "description": "Create a project.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "template": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Write a file with full content.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Make targeted modifications to an existing file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final outcome.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to the user.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "Search the web.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "plan_update", "description": "Create or revise the task plan.", "parameters": {"type": "object", "properties": {"goal": {"type": "string"}, "phases": {"type": "array"}}, "required": ["goal", "phases"]}}},
    {"type": "function", "function": {"name": "undertow", "description": "QA test an HTML file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "file_read", "description": "Read a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]

FA01_APP = '''import { useState } from 'react';
import FileDropzone from './components/FileDropzone';
import DataTable from './components/DataTable';
import { parseFile } from './components/parseFile';
import { exportCsv } from './components/exportCsv';

export default function App() {
  const [columns, setColumns] = useState<{ key: string; label: string }[]>([]);
  const [rows, setRows] = useState<Record<string, any>[]>([]);
  const [fileName, setFileName] = useState('');

  async function handleFile(file: File) {
    const sheets = await parseFile(file);
    if (sheets.length === 0) return;
    const { columns: cols, rows: data } = sheets[0];
    setColumns(cols);
    setRows(data);
    setFileName(file.name);
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>CSV Explorer</h1>
        {fileName && <span className="badge accent">{fileName}</span>}
      </header>
      <main className="app-main">
        {rows.length === 0 ? (
          <div className="card">
            <FileDropzone
              accept=".csv,.tsv"
              onFile={handleFile}
              label="Drop a CSV or TSV file to explore"
            />
          </div>
        ) : (
          <DataTable
            columns={columns}
            rows={rows}
            searchable
            onExport={() => exportCsv(columns, rows, 'export.csv')}
          />
        )}
      </main>
    </div>
  );
}'''

FA02_APP = '''import { useState } from 'react';

type Step = 'info' | 'details' | 'review';
const STEPS: Step[] = ['info', 'details', 'review'];

interface FormData {
  name: string; email: string; company: string;
  role: string; message: string;
}

export default function App() {
  const [step, setStep] = useState<Step>('info');
  const [form, setForm] = useState<FormData>({
    name: '', email: '', company: '', role: '', message: '',
  });
  const [submitted, setSubmitted] = useState(false);

  function update(k: keyof FormData, v: string) {
    setForm(f => ({ ...f, [k]: v }));
  }

  if (submitted) {
    return (
      <div className="app">
        <div className="card" style={{ maxWidth: 480, margin: '80px auto', textAlign: 'center' }}>
          <div style={{ fontSize: 48 }}>✓</div>
          <h2>Thank you, {form.name}!</h2>
          <p>We'll be in touch at {form.email}.</p>
        </div>
      </div>
    );
  }

  const stepIdx = STEPS.indexOf(step);

  return (
    <div className="app">
      <div className="card" style={{ maxWidth: 540, margin: '40px auto' }}>
        <div className="steps">
          {STEPS.map((s, i) => (
            <div key={s} className={`step ${i < stepIdx ? 'done' : i === stepIdx ? 'active' : ''}`}>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </div>
          ))}
        </div>

        {step === 'info' && (
          <div className="form-grid">
            <div className="form-group">
              <label>Full Name</label>
              <input value={form.name} onChange={e => update('name', e.target.value)} placeholder="Jane Smith" />
            </div>
            <div className="form-group">
              <label>Email</label>
              <input type="email" value={form.email} onChange={e => update('email', e.target.value)} placeholder="jane@example.com" />
            </div>
            <div className="form-actions">
              <button className="primary" onClick={() => setStep('details')} disabled={!form.name || !form.email}>
                Next →
              </button>
            </div>
          </div>
        )}

        {step === 'details' && (
          <div className="form-grid">
            <div className="form-group">
              <label>Company</label>
              <input value={form.company} onChange={e => update('company', e.target.value)} placeholder="Acme Corp" />
            </div>
            <div className="form-group">
              <label>Role</label>
              <input value={form.role} onChange={e => update('role', e.target.value)} placeholder="Engineer" />
            </div>
            <div className="form-group" style={{ gridColumn: '1/-1' }}>
              <label>Message</label>
              <textarea value={form.message} onChange={e => update('message', e.target.value)} rows={4} placeholder="Tell us about your project..." />
            </div>
            <div className="form-actions">
              <button className="ghost" onClick={() => setStep('info')}>← Back</button>
              <button className="primary" onClick={() => setStep('review')}>Review →</button>
            </div>
          </div>
        )}

        {step === 'review' && (
          <div>
            <h3>Review your submission</h3>
            <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 24 }}>
              <tbody>
                {Object.entries(form).filter(([, v]) => v).map(([k, v]) => (
                  <tr key={k}>
                    <td style={{ padding: '6px 12px', fontWeight: 600, textTransform: 'capitalize', opacity: 0.7 }}>{k}</td>
                    <td style={{ padding: '6px 12px' }}>{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="form-actions">
              <button className="ghost" onClick={() => setStep('details')}>← Back</button>
              <button className="primary" onClick={() => setSubmitted(true)}>Submit</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}'''

FA03_APP = '''import { useState } from 'react';
import FileDropzone from './components/FileDropzone';
import DataTable from './components/DataTable';
import { parseFile, ParsedSheet } from './components/parseFile';
import { exportCsv } from './components/exportCsv';

export default function App() {
  const [sheets, setSheets] = useState<ParsedSheet[]>([]);
  const [activeTab, setActiveTab] = useState(0);
  const [fileName, setFileName] = useState('');

  async function handleFile(file: File) {
    const parsed = await parseFile(file);
    setSheets(parsed);
    setActiveTab(0);
    setFileName(file.name);
  }

  const sheet = sheets[activeTab];

  return (
    <div className="app">
      <header className="app-header">
        <h1>XLSX Analyzer</h1>
        {fileName && <span className="badge accent">{fileName} — {sheets.length} sheet{sheets.length !== 1 ? 's' : ''}</span>}
      </header>
      <main className="app-main">
        {sheets.length === 0 ? (
          <div className="card">
            <FileDropzone
              accept=".xlsx,.xls,.csv"
              onFile={handleFile}
              label="Drop an Excel or CSV file to analyze"
            />
          </div>
        ) : (
          <>
            {sheets.length > 1 && (
              <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                {sheets.map((s, i) => (
                  <button
                    key={i}
                    className={i === activeTab ? 'primary' : 'ghost'}
                    onClick={() => setActiveTab(i)}
                  >
                    {s.sheetName}
                  </button>
                ))}
              </div>
            )}
            {sheet && (
              <DataTable
                columns={sheet.columns}
                rows={sheet.rows}
                searchable
                onExport={() => exportCsv(sheet.columns, sheet.rows, `${sheet.sheetName}.csv`)}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}'''

FA04_APP = '''import { useState } from 'react';
import DataTable from './components/DataTable';
import { exportCsv } from './components/exportCsv';

const COLS = [
  { key: 'item', label: 'Item' },
  { key: 'category', label: 'Category' },
  { key: 'amount', label: 'Amount ($)' },
  { key: 'date', label: 'Date' },
];

interface Entry { item: string; category: string; amount: string; date: string; }

export default function App() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [form, setForm] = useState<Entry>({ item: '', category: 'Food', amount: '', date: new Date().toISOString().slice(0, 10) });

  const CATEGORIES = ['Food', 'Transport', 'Utilities', 'Entertainment', 'Health', 'Other'];

  function add() {
    if (!form.item || !form.amount) return;
    setEntries(e => [...e, { ...form }]);
    setForm(f => ({ ...f, item: '', amount: '' }));
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Expense Tracker</h1>
      </header>
      <main className="app-main">
        <div className="card" style={{ marginBottom: 24 }}>
          <h3>Add Entry</h3>
          <div className="form-grid">
            <div className="form-group">
              <label>Item</label>
              <input value={form.item} onChange={e => setForm(f => ({ ...f, item: e.target.value }))} placeholder="Coffee" />
            </div>
            <div className="form-group">
              <label>Category</label>
              <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}>
                {CATEGORIES.map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Amount ($)</label>
              <input type="number" step="0.01" value={form.amount} onChange={e => setForm(f => ({ ...f, amount: e.target.value }))} placeholder="4.50" />
            </div>
            <div className="form-group">
              <label>Date</label>
              <input type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} />
            </div>
            <div className="form-actions">
              <button className="primary" onClick={add} disabled={!form.item || !form.amount}>Add Entry</button>
            </div>
          </div>
        </div>

        {entries.length > 0 && (
          <DataTable
            columns={COLS}
            rows={entries}
            searchable
            onExport={() => exportCsv(COLS, entries, 'expenses.csv')}
          />
        )}
      </main>
    </div>
  );
}'''

FA05_BROKEN_APP = '''import { useState } from 'react';

export default function App() {
  const [data, setData] = useState([]);

  async function load() {
    const res = await fetch('/data/employees.csv');
    const text = await res.text();
    const rows = text.split('\\n').map(line => {
      const [name, dept, salary] = line.split(',');
      return { name, dept, salary };
    });
    setData(rows);
  }

  return (
    <div className="app">
      <button onClick={load}>Load CSV</button>
      <table>
        <thead><tr><th>Name</th><th>Dept</th><th>Salary</th></tr></thead>
        <tbody>{data.map((r, i) => <tr key={i}><td>{r.name}</td><td>{r.dept}</td><td>{r.salary}</td></tr>)}</tbody>
      </table>
    </div>
  );
}'''

FA05_FIXED_APP = '''import { useState } from 'react';
import FileDropzone from './components/FileDropzone';
import DataTable from './components/DataTable';
import { parseFile } from './components/parseFile';
import { exportCsv } from './components/exportCsv';

export default function App() {
  const [columns, setColumns] = useState<{ key: string; label: string }[]>([]);
  const [rows, setRows] = useState<Record<string, any>[]>([]);

  async function handleFile(file: File) {
    const sheets = await parseFile(file);
    if (sheets.length === 0) return;
    setColumns(sheets[0].columns);
    setRows(sheets[0].rows);
  }

  return (
    <div className="app">
      <header className="app-header"><h1>Employee Viewer</h1></header>
      <main className="app-main">
        {rows.length === 0 ? (
          <div className="card">
            <FileDropzone accept=".csv,.xlsx" onFile={handleFile} label="Drop employee CSV here" />
          </div>
        ) : (
          <DataTable
            columns={columns}
            rows={rows}
            searchable
            onExport={() => exportCsv(columns, rows, 'employees.csv')}
          />
        )}
      </main>
    </div>
  );
}'''


def tool_call(call_id, name, args):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
    ]}

def tool_result(call_id, text):
    return {"role": "tool", "tool_call_id": call_id, "content": text}


EXAMPLES = []

# ──────────────────────────────────────────────────────────────────────────────
# FA01: CSV Explorer
# ──────────────────────────────────────────────────────────────────────────────
EXAMPLES.append([
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build a CSV explorer where I can upload a CSV file and see it in a searchable, sortable table with an export button"},
    tool_call("c1", "project_init", {"name": "csv-explorer", "template": "form-app"}),
    tool_result("c1", "[project_init] Created 'csv-explorer' with template='form-app'. Write src/App.tsx."),
    tool_call("c2", "file_write", {"path": "src/App.tsx", "content": FA01_APP}),
    tool_result("c2", "[file_write] src/App.tsx written."),
    tool_call("c3", "shell_exec", {"command": "npm run build"}),
    tool_result("c3", "[shell_exec] Build succeeded. dist/index.html ready."),
    tool_call("c4", "undertow", {"path": "dist/index.html"}),
    tool_result("c4", "[undertow] QA passed. FileDropzone renders. DataTable renders with search and export. No console errors."),
    tool_call("c5", "message_result", {"text": "CSV Explorer is ready. Drop any CSV or TSV file to explore it in a searchable, sortable table with export."}),
])

# ──────────────────────────────────────────────────────────────────────────────
# FA02: Multi-step form wizard
# ──────────────────────────────────────────────────────────────────────────────
EXAMPLES.append([
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build a contact form with 3 steps: personal info (name + email), details (company + role + message), then a review and submit step"},
    tool_call("c1", "project_init", {"name": "contact-wizard", "template": "form-app"}),
    tool_result("c1", "[project_init] Created 'contact-wizard' with template='form-app'. Write src/App.tsx."),
    tool_call("c2", "file_write", {"path": "src/App.tsx", "content": FA02_APP}),
    tool_result("c2", "[file_write] src/App.tsx written."),
    tool_call("c3", "shell_exec", {"command": "npm run build"}),
    tool_result("c3", "[shell_exec] Build succeeded."),
    tool_call("c4", "undertow", {"path": "dist/index.html"}),
    tool_result("c4", "[undertow] QA passed. Stepper shows 3 steps. Navigation between steps works. Review screen displays form data. Submit shows confirmation."),
    tool_call("c5", "message_result", {"text": "Contact wizard ready. 3-step form with personal info → details → review+submit. Progress stepper shows current step."}),
])

# ──────────────────────────────────────────────────────────────────────────────
# FA03: XLSX Analyzer
# ──────────────────────────────────────────────────────────────────────────────
EXAMPLES.append([
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build an Excel file analyzer — upload an XLSX and see each sheet as a tab with a searchable data table and export button"},
    tool_call("c1", "project_init", {"name": "xlsx-analyzer", "template": "form-app"}),
    tool_result("c1", "[project_init] Created 'xlsx-analyzer' with template='form-app'. Write src/App.tsx."),
    tool_call("c2", "file_write", {"path": "src/App.tsx", "content": FA03_APP}),
    tool_result("c2", "[file_write] src/App.tsx written."),
    tool_call("c3", "shell_exec", {"command": "npm run build"}),
    tool_result("c3", "[shell_exec] Build succeeded."),
    tool_call("c4", "undertow", {"path": "dist/index.html"}),
    tool_result("c4", "[undertow] QA passed. FileDropzone accepts XLSX. Multi-sheet tabs render. DataTable shows with search and per-sheet export."),
    tool_call("c5", "message_result", {"text": "XLSX Analyzer ready. Upload any Excel file to browse each sheet as a searchable table. Export individual sheets as CSV."}),
])

# ──────────────────────────────────────────────────────────────────────────────
# FA04: Data entry + editable table
# ──────────────────────────────────────────────────────────────────────────────
EXAMPLES.append([
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build an expense tracker where I fill in a form to add entries and see them in a table, with a CSV export button"},
    tool_call("c1", "project_init", {"name": "expense-tracker", "template": "form-app"}),
    tool_result("c1", "[project_init] Created 'expense-tracker' with template='form-app'. Write src/App.tsx."),
    tool_call("c2", "file_write", {"path": "src/App.tsx", "content": FA04_APP}),
    tool_result("c2", "[file_write] src/App.tsx written."),
    tool_call("c3", "shell_exec", {"command": "npm run build"}),
    tool_result("c3", "[shell_exec] Build succeeded."),
    tool_call("c4", "undertow", {"path": "dist/index.html"}),
    tool_result("c4", "[undertow] QA passed. Add form renders. DataTable appears after first entry. Export downloads CSV."),
    tool_call("c5", "message_result", {"text": "Expense tracker ready. Fill in the form to add entries — they appear in a searchable table below. Export to CSV anytime."}),
])

# ──────────────────────────────────────────────────────────────────────────────
# FA05: Error recovery — fetch() → file_edit to parseFile
# ──────────────────────────────────────────────────────────────────────────────
EXAMPLES.append([
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build an employee viewer that loads from a CSV file"},
    tool_call("c1", "project_init", {"name": "employee-viewer", "template": "form-app"}),
    tool_result("c1", "[project_init] Created 'employee-viewer' with template='form-app'. Write src/App.tsx."),
    tool_call("c2", "file_write", {"path": "src/App.tsx", "content": FA05_BROKEN_APP}),
    tool_result("c2", "[file_write] src/App.tsx written."),
    tool_call("c3", "shell_exec", {"command": "npm run build"}),
    tool_result("c3", "[shell_exec] Warning: fetch('/data/employees.csv') will fail in static build — no /data/ directory. Build succeeded but runtime will error."),
    tool_call("c4", "file_edit", {
        "path": "src/App.tsx",
        "old_text": FA05_BROKEN_APP,
        "new_text": FA05_FIXED_APP,
    }),
    tool_result("c4", "[file_edit] src/App.tsx updated to use FileDropzone + parseFile + DataTable."),
    tool_call("c5", "shell_exec", {"command": "npm run build"}),
    tool_result("c5", "[shell_exec] Build succeeded. No warnings."),
    tool_call("c6", "undertow", {"path": "dist/index.html"}),
    tool_result("c6", "[undertow] QA passed. FileDropzone visible. DataTable renders on file drop. No fetch calls."),
    tool_call("c7", "message_result", {"text": "Employee viewer ready. Uses file upload instead of fetch — works in any static deployment."}),
])

# ──────────────────────────────────────────────────────────────────────────────
# FA06: Conversational routing
# ──────────────────────────────────────────────────────────────────────────────
EXAMPLES.append([
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "What file types does the FileDropzone component support?"},
    {"role": "assistant", "content": "", "tool_calls": [
        {"id": "c1", "type": "function", "function": {
            "name": "message_chat",
            "arguments": json.dumps({
                "text": "FileDropzone supports any file type via the `accept` prop. Common values: `.csv,.tsv` for spreadsheet data, `.xlsx,.xls` for Excel, or `.csv,.xlsx,.json` for a mix. The component validates file type and size before calling `onFile`. If no `accept` prop is set it defaults to `.xlsx,.xls,.csv,.json,.tsv`.",
                "done": True,
            })
        }}
    ]},
])


OUT_PATH = Path("workspace/training_data/formapp_sft_v1.jsonl")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

records = []
for i, msgs in enumerate(EXAMPLES):
    prompt = tokenizer.apply_chat_template(
        msgs[:-1], tools=TOOLS, tokenize=False, add_generation_prompt=True
    )
    full = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    completion = full[len(prompt):]
    records.append({
        "prompt": prompt,
        "completion": completion,
        "source": f"FA{i+1:02d}",
        "date": TODAY,
    })

with open(OUT_PATH, "w") as f:
    for r in records:
        f.write(json.dumps(r) + "\n")

print(f"\n=== FORM-APP SFT v1 SUMMARY ===")
print(f"  Total examples: {len(records)}")
print(f"  File: {OUT_PATH}")
for r in records:
    print(f"  {r['source']}: {len(r['prompt'])+len(r['completion'])} chars")
print(f"\nTo train:")
print(f"  /usr/bin/python3 training/train_unsloth.py --model google/gemma-4-e4b-it \\")
print(f"    --data workspace/training_data/formapp_sft_v1.jsonl \\")
print(f"    --output models/gemma-4-e4b-tsunami-formapp-v1 --epochs 3 --lora-r 16 --lr 2e-4")
