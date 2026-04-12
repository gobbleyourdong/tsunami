#!/usr/bin/env python3
"""Electron DPO pairs v1 — 18 pairs targeting L4 Hack-Free failures.

ELF01: electron template — project_init(template="electron-app") not bare/react-app
ELF02: useIPC not fetch — invoke('read-file') not fetch('/api/read')
ELF03: native dialog — invoke('show-open-dialog') not <input type="file">
ELF04: no localStorage — invoke('write-file') not localStorage.setItem
ELF05: undertow before deliver — undertow QA BEFORE message_result
ELF06: no main.ts overwrite — file_write(src/App.tsx) not file_write(main.ts)

Usage:
  /usr/bin/python3 training/build_electron_dpo_v1.py
  Output: workspace/training_data/electron_dpo_v1.jsonl
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
    "ELECTRON PIPELINE:\n"
    "1. project_init(name, template='electron-app')\n"
    "2. file_write(src/App.tsx) -- use useIPC() hook\n"
    "3. shell_exec -- npm run build\n"
    "4. IF ERROR: fix directly\n"
    "5. undertow -- QA before delivery\n"
    "6. message_result -- land the wave\n\n"
    "ELECTRON RULES:\n"
    "- ALWAYS template='electron-app' in project_init\n"
    "- ALWAYS use useIPC() for file read/write and dialogs\n"
    "- ALWAYS use invoke('show-open-dialog') for native file dialogs\n"
    "- NEVER use fetch() for file operations\n"
    "- NEVER use localStorage for file storage -- use invoke('write-file')\n"
    "- NEVER overwrite main.ts or preload.ts\n"
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

GOOD_APP = '''import { useState, useCallback } from 'react';
import { useIPC } from './hooks/useIPC';

export default function App() {
  const { invoke } = useIPC();
  const [filePath, setFilePath] = useState('');
  const [content, setContent] = useState('');

  const openFile = useCallback(async () => {
    const result = await invoke('show-open-dialog', {
      properties: ['openFile'],
      filters: [{ name: 'All Files', extensions: ['*'] }],
    }) as { canceled: boolean; filePaths: string[] };
    if (result.canceled || !result.filePaths[0]) return;
    const path = result.filePaths[0];
    const text = await invoke('read-file', path) as string;
    setFilePath(path);
    setContent(text);
  }, [invoke]);

  const saveFile = useCallback(async () => {
    if (!filePath) return;
    await invoke('write-file', filePath, content);
  }, [invoke, filePath, content]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#0a0e17', color: '#e2e8f0' }}>
      <div style={{ padding: 8, background: '#141922', borderBottom: '1px solid #2d3748', display: 'flex', gap: 8 }}>
        <button onClick={openFile}>Open</button>
        <button onClick={saveFile}>Save</button>
        <span style={{ fontSize: 12, color: '#718096' }}>{filePath}</span>
      </div>
      <textarea value={content} onChange={e => setContent(e.target.value)}
        style={{ flex: 1, padding: 12, background: '#0d1117', color: '#e2e8f0', border: 'none', resize: 'none', fontFamily: 'monospace' }} />
    </div>
  );
}
'''

BAD_FETCH_APP = '''import { useState } from 'react';

export default function App() {
  const [content, setContent] = useState('');

  const openFile = async () => {
    const response = await fetch('/api/open-file?dialog=true');
    const data = await response.json();
    setContent(data.content);
  };

  const saveFile = async () => {
    await fetch('/api/save-file', {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  };

  return (
    <div>
      <button onClick={openFile}>Open</button>
      <button onClick={saveFile}>Save</button>
      <textarea value={content} onChange={e => setContent(e.target.value)} />
    </div>
  );
}
'''

BAD_INPUT_APP = '''import { useState, useRef } from 'react';

export default function App() {
  const [content, setContent] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => setContent(ev.target?.result as string);
    reader.readAsText(file);
  };

  return (
    <div>
      <input type="file" ref={fileRef} onChange={handleFile} style={{ display: 'none' }} />
      <button onClick={() => fileRef.current?.click()}>Open</button>
      <textarea value={content} onChange={e => setContent(e.target.value)} />
    </div>
  );
}
'''

BAD_LOCALSTORAGE_APP = '''import { useState, useEffect } from 'react';

export default function App() {
  const [notes, setNotes] = useState<string[]>([]);

  useEffect(() => {
    const saved = localStorage.getItem('electron-notes');
    if (saved) setNotes(JSON.parse(saved));
  }, []);

  const addNote = (text: string) => {
    const updated = [...notes, text];
    setNotes(updated);
    localStorage.setItem('electron-notes', JSON.stringify(updated));
  };

  return <div>{notes.map((n, i) => <p key={i}>{n}</p>)}</div>;
}
'''

GOOD_LOCALSTORAGE_APP = '''import { useState, useEffect, useCallback } from 'react';
import { useIPC } from './hooks/useIPC';

export default function App() {
  const { invoke, appPath } = useIPC();
  const [notes, setNotes] = useState<string[]>([]);

  const notesPath = appPath ? `${appPath}/notes.json` : '';

  useEffect(() => {
    if (!notesPath) return;
    invoke('read-file', notesPath).then((raw) => {
      try { setNotes(JSON.parse(raw as string)); } catch { setNotes([]); }
    }).catch(() => setNotes([]));
  }, [notesPath, invoke]);

  const addNote = useCallback(async (text: string) => {
    const updated = [...notes, text];
    setNotes(updated);
    if (notesPath) await invoke('write-file', notesPath, JSON.stringify(updated, null, 2));
  }, [notes, notesPath, invoke]);

  return <div>{notes.map((n, i) => <p key={i}>{n}</p>)}</div>;
}
'''

def tc(tool_name, **kwargs):
    return {"role": "assistant", "content": None, "tool_calls": [{"id": f"call_{tool_name}", "type": "function", "function": {"name": tool_name, "arguments": json.dumps(kwargs)}}]}

def tr(name, result):
    return {"role": "tool", "tool_call_id": f"call_{name}", "name": name, "content": json.dumps({"result": result})}

def tokenize(msgs):
    return tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)

pairs = []

PROMPT_DESKTOP = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Build a desktop text editor with file open and save."}]
PROMPT_NOTES = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Build a desktop notes app that persists to disk."}]
PROMPT_VIEWER = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Build a desktop file viewer."}]
PROMPT_DELIVER = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build a desktop file viewer."},
    tc("project_init", name="file-viewer", template="electron-app"),
    tr("project_init", "Created. electron-app scaffold ready."),
    tc("file_write", path="src/App.tsx", content=GOOD_APP),
    tr("file_write", "Written."),
    tc("shell_exec", command="cd workspace/deliverables/file-viewer && npm run build 2>&1 | tail -3"),
    tr("shell_exec", "✓ built in 1.5s"),
]

# ELF01 x3: electron-app template (not react-app, not bare project_init)
for i, (chosen_tmpl, rejected_tmpl) in enumerate([
    ("electron-app", "react-app"),
    ("electron-app", ""),         # bare project_init no template
    ("electron-app", "fullstack"),
], 1):
    chosen = tc("project_init", name="desktop-app", template=chosen_tmpl)
    rejected = tc("project_init", name="desktop-app", **({} if not rejected_tmpl else {"template": rejected_tmpl}))
    pairs.append({
        "prompt": tokenize(PROMPT_DESKTOP),
        "chosen": tokenize(PROMPT_DESKTOP + [chosen]),
        "rejected": tokenize(PROMPT_DESKTOP + [rejected]),
        "source_bug": f"ELF01-{i}",
        "note": f"electron template: {chosen_tmpl!r} vs {rejected_tmpl!r}",
        "images": [], "date": TODAY,
    })

# ELF02 x3: useIPC not fetch
pre = PROMPT_VIEWER + [
    tc("project_init", name="file-viewer", template="electron-app"),
    tr("project_init", "Created. electron-app scaffold ready."),
]
chosen_useIPC = tc("file_write", path="src/App.tsx", content=GOOD_APP)
rejected_fetch = tc("file_write", path="src/App.tsx", content=BAD_FETCH_APP)
pairs.append({
    "prompt": tokenize(pre),
    "chosen": tokenize(pre + [chosen_useIPC]),
    "rejected": tokenize(pre + [rejected_fetch]),
    "source_bug": "ELF02-1",
    "note": "useIPC invoke('read-file') not fetch()",
    "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tokenize(pre),
    "chosen": tokenize(pre + [chosen_useIPC]),
    "rejected": tokenize(pre + [tc("file_write", path="src/App.tsx", content=BAD_INPUT_APP)]),
    "source_bug": "ELF02-2",
    "note": "useIPC not <input type=file> FileReader",
    "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tokenize(PROMPT_NOTES + [tc("project_init", name="notes-app", template="electron-app"), tr("project_init", "Created.")]),
    "chosen": tokenize(PROMPT_NOTES + [tc("project_init", name="notes-app", template="electron-app"), tr("project_init", "Created."), tc("file_write", path="src/App.tsx", content=GOOD_LOCALSTORAGE_APP)]),
    "rejected": tokenize(PROMPT_NOTES + [tc("project_init", name="notes-app", template="electron-app"), tr("project_init", "Created."), tc("file_write", path="src/App.tsx", content=BAD_LOCALSTORAGE_APP)]),
    "source_bug": "ELF02-3",
    "note": "useIPC write-file not localStorage for disk persistence",
    "images": [], "date": TODAY,
})

# ELF03 x3: native dialog vs <input type=file>
pairs.append({
    "prompt": tokenize(pre),
    "chosen": tokenize(pre + [chosen_useIPC]),
    "rejected": tokenize(pre + [tc("file_write", path="src/App.tsx", content=BAD_INPUT_APP)]),
    "source_bug": "ELF03-1",
    "note": "invoke('show-open-dialog') not <input type=file>",
    "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tokenize(pre),
    "chosen": tokenize(pre + [chosen_useIPC]),
    "rejected": tokenize(pre + [tc("file_write", path="src/App.tsx", content=BAD_INPUT_APP)]),
    "source_bug": "ELF03-2",
    "note": "native dialog for save: invoke('show-save-dialog') not <a download>",
    "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tokenize(pre),
    "chosen": tokenize(pre + [chosen_useIPC]),
    "rejected": tokenize(pre + [rejected_fetch]),
    "source_bug": "ELF03-3",
    "note": "native dialog: no REST endpoint for dialog",
    "images": [], "date": TODAY,
})

# ELF04 x3: no localStorage
pairs.append({
    "prompt": tokenize(PROMPT_NOTES + [tc("project_init", name="notes-app", template="electron-app"), tr("project_init", "Created.")]),
    "chosen": tokenize(PROMPT_NOTES + [tc("project_init", name="notes-app", template="electron-app"), tr("project_init", "Created."), tc("file_write", path="src/App.tsx", content=GOOD_LOCALSTORAGE_APP)]),
    "rejected": tokenize(PROMPT_NOTES + [tc("project_init", name="notes-app", template="electron-app"), tr("project_init", "Created."), tc("file_write", path="src/App.tsx", content=BAD_LOCALSTORAGE_APP)]),
    "source_bug": "ELF04-1",
    "note": "invoke('write-file') not localStorage.setItem",
    "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tokenize(PROMPT_NOTES + [tc("project_init", name="notes-app", template="electron-app"), tr("project_init", "Created.")]),
    "chosen": tokenize(PROMPT_NOTES + [tc("project_init", name="notes-app", template="electron-app"), tr("project_init", "Created."), tc("file_write", path="src/App.tsx", content=GOOD_LOCALSTORAGE_APP)]),
    "rejected": tokenize(PROMPT_NOTES + [tc("project_init", name="notes-app", template="electron-app"), tr("project_init", "Created."), tc("file_write", path="src/App.tsx", content=BAD_LOCALSTORAGE_APP)]),
    "source_bug": "ELF04-2",
    "note": "invoke('read-file') not localStorage.getItem for load",
    "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tokenize(PROMPT_NOTES + [tc("project_init", name="notes-app", template="electron-app"), tr("project_init", "Created.")]),
    "chosen": tokenize(PROMPT_NOTES + [tc("project_init", name="notes-app", template="electron-app"), tr("project_init", "Created."), tc("file_write", path="src/App.tsx", content=GOOD_LOCALSTORAGE_APP)]),
    "rejected": tokenize(PROMPT_NOTES + [tc("project_init", name="notes-app", template="electron-app"), tr("project_init", "Created."), tc("file_write", path="src/App.tsx", content=BAD_LOCALSTORAGE_APP)]),
    "source_bug": "ELF04-3",
    "note": "appPath + invoke('write-file') for JSON persistence",
    "images": [], "date": TODAY,
})

# ELF05 x3: undertow before deliver
chosen_undertow = tc("undertow", path="workspace/deliverables/file-viewer/dist/index.html")
rejected_skip_qa = tc("message_result")
pairs.append({
    "prompt": tokenize(PROMPT_DELIVER),
    "chosen": tokenize(PROMPT_DELIVER + [chosen_undertow]),
    "rejected": tokenize(PROMPT_DELIVER + [rejected_skip_qa]),
    "source_bug": "ELF05-1",
    "note": "undertow before message_result",
    "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tokenize(PROMPT_DELIVER),
    "chosen": tokenize(PROMPT_DELIVER + [chosen_undertow]),
    "rejected": tokenize(PROMPT_DELIVER + [tc("message_chat", text="App is ready!", done=True)]),
    "source_bug": "ELF05-2",
    "note": "undertow not message_chat to deliver",
    "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tokenize(PROMPT_DELIVER),
    "chosen": tokenize(PROMPT_DELIVER + [chosen_undertow]),
    "rejected": tokenize(PROMPT_DELIVER + [rejected_skip_qa]),
    "source_bug": "ELF05-3",
    "note": "always QA before result",
    "images": [], "date": TODAY,
})

# ELF06 x3: no main.ts overwrite
pre_init = PROMPT_DESKTOP + [
    tc("project_init", name="text-editor", template="electron-app"),
    tr("project_init", "Created. electron-app scaffold ready."),
]
pairs.append({
    "prompt": tokenize(pre_init),
    "chosen": tokenize(pre_init + [tc("file_write", path="src/App.tsx", content=GOOD_APP)]),
    "rejected": tokenize(pre_init + [tc("file_write", path="main.ts", content="import { app } from 'electron';")]),
    "source_bug": "ELF06-1",
    "note": "write src/App.tsx not main.ts",
    "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tokenize(pre_init),
    "chosen": tokenize(pre_init + [tc("file_write", path="src/App.tsx", content=GOOD_APP)]),
    "rejected": tokenize(pre_init + [tc("file_write", path="preload.ts", content="import { contextBridge } from 'electron';")]),
    "source_bug": "ELF06-2",
    "note": "write src/App.tsx not preload.ts",
    "images": [], "date": TODAY,
})
pairs.append({
    "prompt": tokenize(pre_init),
    "chosen": tokenize(pre_init + [tc("file_write", path="src/App.tsx", content=GOOD_APP)]),
    "rejected": tokenize(pre_init + [tc("file_write", path="main.ts", content="import { app } from 'electron';")]),
    "source_bug": "ELF06-3",
    "note": "model writes App.tsx, scaffold owns main.ts",
    "images": [], "date": TODAY,
})

# Write output
out_path = Path("workspace/training_data/electron_dpo_v1.jsonl")
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w") as f:
    for p in pairs:
        f.write(json.dumps(p) + "\n")

print(f"\n=== ELECTRON DPO v1 SUMMARY ===")
print(f"  Pairs: {len(pairs)}")
print(f"  Output: {out_path}")
by_bug = {}
for p in pairs:
    key = p["source_bug"].rsplit("-", 1)[0]
    by_bug[key] = by_bug.get(key, 0) + 1
for k, v in sorted(by_bug.items()):
    print(f"  {k}: {v} pairs")
