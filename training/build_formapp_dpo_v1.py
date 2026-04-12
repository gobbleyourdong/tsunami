#!/usr/bin/env python3
"""Form-app DPO pairs v1 — 18 pairs targeting L4 Hack-Free failures.

FAF01: template param — project_init(template="form-app") not bare project_init
FAF02: parseFile not fetch — parseFile(file) not fetch('/data.csv')
FAF03: DataTable not raw table — <DataTable> not <table><tbody>...
FAF04: exportCsv for downloads — exportCsv() not window.open / Blob + URL.createObjectURL
FAF05: undertow before deliver — undertow QA BEFORE message_result
FAF06: no main.tsx overwrite — file_write(src/App.tsx) not file_write(src/main.tsx)

Usage:
  /usr/bin/python3 training/build_formapp_dpo_v1.py
  Output: workspace/training_data/formapp_dpo_v1.jsonl
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
    "- ALWAYS use <DataTable> — never raw <table>\n"
    "- ALWAYS use exportCsv() for downloads\n"
    "- NEVER overwrite main.tsx, vite.config.ts, or index.css\n"
    "- NEVER skip undertow before message_result\n\n"
    "One tool call per response."
)

TOOLS = [
    {"type": "function", "function": {"name": "project_init", "description": "Create a project.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "template": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Write a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Edit a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final outcome.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to user.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "undertow", "description": "QA test an HTML file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "file_read", "description": "Read a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]

_GOOD_APP = '''import { useState } from 'react';
import FileDropzone from './components/FileDropzone';
import DataTable from './components/DataTable';
import { parseFile } from './components/parseFile';
import { exportCsv } from './components/exportCsv';

export default function App() {
  const [columns, setColumns] = useState([]);
  const [rows, setRows] = useState([]);
  async function handleFile(file) {
    const sheets = await parseFile(file);
    if (sheets.length > 0) { setColumns(sheets[0].columns); setRows(sheets[0].rows); }
  }
  return (
    <div className="app">
      {rows.length === 0
        ? <FileDropzone onFile={handleFile} />
        : <DataTable columns={columns} rows={rows} searchable onExport={() => exportCsv(columns, rows, 'data.csv')} />
      }
    </div>
  );
}'''

_FETCH_APP = '''import { useState } from 'react';
export default function App() {
  const [rows, setRows] = useState([]);
  async function load() {
    const res = await fetch('/data.csv');
    const text = await res.text();
    setRows(text.split('\\n').map(l => { const [a,b] = l.split(','); return {a,b}; }));
  }
  return (
    <div>
      <button onClick={load}>Load CSV</button>
      <table><tbody>{rows.map((r,i) => <tr key={i}><td>{r.a}</td><td>{r.b}</td></tr>)}</tbody></table>
    </div>
  );
}'''

_RAW_TABLE_APP = '''import { useState } from 'react';
import FileDropzone from './components/FileDropzone';
import { parseFile } from './components/parseFile';
export default function App() {
  const [columns, setColumns] = useState([]);
  const [rows, setRows] = useState([]);
  async function handleFile(file) {
    const sheets = await parseFile(file);
    if (sheets.length > 0) { setColumns(sheets[0].columns); setRows(sheets[0].rows); }
  }
  return (
    <div className="app">
      <FileDropzone onFile={handleFile} />
      <table>
        <thead><tr>{columns.map(c => <th key={c.key}>{c.label}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{columns.map(c => <td key={c.key}>{r[c.key]}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}'''

_BLOB_EXPORT_APP = '''import { useState } from 'react';
import DataTable from './components/DataTable';
export default function App() {
  const [rows, setRows] = useState([{ a: '1', b: '2' }]);
  const cols = [{ key: 'a', label: 'A' }, { key: 'b', label: 'B' }];
  function download() {
    const csv = rows.map(r => cols.map(c => r[c.key]).join(',')).join('\\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'data.csv'; a.click();
  }
  return <DataTable columns={cols} rows={rows} onExport={download} />;
}'''

_EXPORT_CSV_APP = '''import { useState } from 'react';
import DataTable from './components/DataTable';
import { exportCsv } from './components/exportCsv';
export default function App() {
  const [rows] = useState([{ a: '1', b: '2' }]);
  const cols = [{ key: 'a', label: 'A' }, { key: 'b', label: 'B' }];
  return <DataTable columns={cols} rows={rows} onExport={() => exportCsv(cols, rows, 'data.csv')} />;
}'''


def make_pair(messages, chosen_fn, chosen_args, rejected_fn, rejected_args, source_bug, note=""):
    prompt_text = tokenizer.apply_chat_template(
        messages, tools=TOOLS, tokenize=False, add_generation_prompt=True
    )
    chosen_msg = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "dpo_c", "type": "function", "function": {"name": chosen_fn, "arguments": json.dumps(chosen_args)}}
    ]}]
    chosen_text = tokenizer.apply_chat_template(messages + chosen_msg, tools=TOOLS, tokenize=False)
    chosen_response = chosen_text[len(prompt_text):]

    rejected_msg = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "dpo_r", "type": "function", "function": {"name": rejected_fn, "arguments": json.dumps(rejected_args)}}
    ]}]
    rejected_text = tokenizer.apply_chat_template(messages + rejected_msg, tools=TOOLS, tokenize=False)
    rejected_response = rejected_text[len(prompt_text):]

    return {"prompt": prompt_text, "chosen": chosen_response, "rejected": rejected_response,
            "images": [], "source_bug": source_bug, "note": note, "date": TODAY}


PAIRS = []

# ──────────────────────────────────────────────────────────────────────────────
# FAF01: template param — project_init must include template="form-app"
# ──────────────────────────────────────────────────────────────────────────────
for i, (app, prompt) in enumerate([
    ("csv-explorer",   "Build a CSV file explorer with drag-and-drop upload"),
    ("xlsx-viewer",    "Build a spreadsheet viewer with file dropzone"),
    ("data-entry-app", "Build a data entry form with an editable table"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="project_init", chosen_args={"name": app, "template": "form-app"},
        rejected_fn="project_init", rejected_args={"name": app},
        source_bug="FAF01-form-app-template",
        note=f"faf01-{i+1}: project_init must include template='form-app' for file upload apps",
    ))

# ──────────────────────────────────────────────────────────────────────────────
# FAF02: parseFile not fetch
# ──────────────────────────────────────────────────────────────────────────────
for i, (app, desc) in enumerate([
    ("csv-explorer",   "Build a CSV viewer with file upload"),
    ("data-inspector", "Build a data inspector with file dropzone"),
    ("sheet-viewer",   "Build a spreadsheet viewer"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": desc},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": app, "template": "form-app"})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{app}' with template='form-app'. Write src/App.tsx."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write", chosen_args={"path": "src/App.tsx", "content": _GOOD_APP},
        rejected_fn="file_write", rejected_args={"path": "src/App.tsx", "content": _FETCH_APP},
        source_bug="FAF02-parsefile-not-fetch",
        note=f"faf02-{i+1}: App.tsx must use parseFile(file) not fetch('/data.csv')",
    ))

# ──────────────────────────────────────────────────────────────────────────────
# FAF03: DataTable not raw <table>
# ──────────────────────────────────────────────────────────────────────────────
for i, (app, desc) in enumerate([
    ("csv-viewer",    "Build a CSV file viewer with table output"),
    ("log-viewer",    "Build a log file viewer showing rows in a table"),
    ("data-explorer", "Build a data file explorer with tabular display"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": desc},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": app, "template": "form-app"})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{app}' with template='form-app'. Write src/App.tsx."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write", chosen_args={"path": "src/App.tsx", "content": _GOOD_APP},
        rejected_fn="file_write", rejected_args={"path": "src/App.tsx", "content": _RAW_TABLE_APP},
        source_bug="FAF03-datatable-not-raw",
        note=f"faf03-{i+1}: App.tsx must use <DataTable> component not raw <table><tbody>",
    ))

# ──────────────────────────────────────────────────────────────────────────────
# FAF04: exportCsv not Blob URL
# ──────────────────────────────────────────────────────────────────────────────
for i, (app, desc) in enumerate([
    ("data-editor",   "Build a data editor with export to CSV button"),
    ("csv-builder",   "Build a table builder with downloadable CSV"),
    ("sheet-tracker", "Build a spreadsheet tracker with export"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": desc},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": app, "template": "form-app"})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{app}' with template='form-app'. Write src/App.tsx."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write", chosen_args={"path": "src/App.tsx", "content": _EXPORT_CSV_APP},
        rejected_fn="file_write", rejected_args={"path": "src/App.tsx", "content": _BLOB_EXPORT_APP},
        source_bug="FAF04-exportcsv-not-blob",
        note=f"faf04-{i+1}: use exportCsv(cols, rows, 'name.csv') not Blob+URL.createObjectURL",
    ))

# ──────────────────────────────────────────────────────────────────────────────
# FAF05: undertow before message_result
# ──────────────────────────────────────────────────────────────────────────────
for i, (app,) in enumerate([
    ("csv-explorer",),
    ("xlsx-viewer",),
    ("data-entry-app",),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Build a {app.replace('-', ' ')}"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": app, "template": "form-app"})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c1", "content": f"[project_init] Created '{app}'."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": _GOOD_APP})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c2", "content": "[file_write] src/App.tsx written."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c3", "type": "function", "function": {
                "name": "shell_exec", "arguments": json.dumps({"command": "npm run build"})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c3", "content": "[shell_exec] Build succeeded. dist/index.html ready."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="undertow", chosen_args={"path": "dist/index.html"},
        rejected_fn="message_result", rejected_args={"text": f"{app} is ready."},
        source_bug="FAF05-undertow-before-deliver",
        note=f"faf05-{i+1}: after successful build, undertow QA BEFORE message_result",
    ))

# ──────────────────────────────────────────────────────────────────────────────
# FAF06: no main.tsx — write App.tsx not main.tsx
# ──────────────────────────────────────────────────────────────────────────────
for i, (app, desc) in enumerate([
    ("csv-app",    "Build a CSV upload and viewer"),
    ("data-app",   "Build a data table with file upload"),
    ("sheet-app",  "Build a spreadsheet viewer app"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": desc},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": app, "template": "form-app"})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{app}' with template='form-app'. Write src/App.tsx."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write", chosen_args={"path": "src/App.tsx", "content": _GOOD_APP},
        rejected_fn="file_write", rejected_args={"path": "src/main.tsx", "content": "import App from './App'; ReactDOM.createRoot(document.getElementById('root')!).render(<App/>);"},
        source_bug="FAF06-no-main-tsx",
        note=f"faf06-{i+1}: after project_init write src/App.tsx not src/main.tsx (scaffold provides main.tsx)",
    ))


# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────
OUT_PATH = Path("workspace/training_data/formapp_dpo_v1.jsonl")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

with open(OUT_PATH, "w") as f:
    for p in PAIRS:
        f.write(json.dumps(p) + "\n")

counts = {
    "faf01-template":     sum(1 for p in PAIRS if "faf01" in p["note"]),
    "faf02-parsefile":    sum(1 for p in PAIRS if "faf02" in p["note"]),
    "faf03-datatable":    sum(1 for p in PAIRS if "faf03" in p["note"]),
    "faf04-exportcsv":    sum(1 for p in PAIRS if "faf04" in p["note"]),
    "faf05-undertow":     sum(1 for p in PAIRS if "faf05" in p["note"]),
    "faf06-no-main-tsx":  sum(1 for p in PAIRS if "faf06" in p["note"]),
}
print(f"\n=== FORM-APP DPO v1 SUMMARY ===")
print(f"  Total pairs: {len(PAIRS)}")
print(f"  File: {OUT_PATH}")
for k, v in counts.items():
    print(f"  {k}: {v}")
print(f"\nTo train (after SFT formapp-v1 + merge):")
print(f"  # Step 1: SFT")
print(f"  /usr/bin/python3 training/train_unsloth.py --model google/gemma-4-e4b-it \\")
print(f"    --data workspace/training_data/formapp_sft_v1.jsonl \\")
print(f"    --output models/gemma-4-e4b-tsunami-formapp-v1 --epochs 3 --lora-r 16 --lr 2e-4")
print(f"  # Step 2: Merge")
print(f"  /usr/bin/python3 training/merge_adapter.py --base google/gemma-4-e4b-it \\")
print(f"    --adapter models/gemma-4-e4b-tsunami-formapp-v1 \\")
print(f"    --output models/gemma-4-e4b-tsunami-formapp-v1-merged")
print(f"  # Step 3: DPO")
print(f"  /usr/bin/python3 training/train_dpo.py \\")
print(f"    --base-model models/gemma-4-e4b-tsunami-formapp-v1-merged \\")
print(f"    --data workspace/training_data/formapp_dpo_v1.jsonl \\")
print(f"    --output models/gemma-4-e4b-tsunami-formapp-v2 --epochs 1 --lora-r 16 --lr 5e-6 --beta 0.1")
