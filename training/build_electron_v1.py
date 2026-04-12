#!/usr/bin/env python3
"""Electron SFT examples v1 — 6 training examples for the electron-app adapter.

Uses scaffolds/electron-app/ (Vite + React + Electron + useIPC + contextBridge).
Pipeline: project_init(template="electron-app") → file_write(src/App.tsx) → build → undertow → result.

EL01: Markdown editor — open file + edit + save via useIPC native dialogs
EL02: Notes app — create/edit/delete notes, save JSON to disk via IPC
EL03: File browser — list directory, open files, show content
EL04: Image viewer — open image via native dialog, display + info
EL05: Error recovery — fetch() for file read → fix to useIPC invoke('read-file')
EL06: Conversational routing — "Can you build desktop apps?" → message_chat

Usage:
  /usr/bin/python3 training/build_electron_v1.py
  Output: workspace/training_data/electron_sft_v1.jsonl
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
    "Missing file -> file_write.\n\n"
    "ELECTRON PIPELINE (desktop apps follow this EXACTLY):\n"
    "1. project_init(name, template='electron-app')\n"
    "2. file_write(src/App.tsx) -- use useIPC() hook, window.electronAPI for all file/dialog ops\n"
    "3. shell_exec -- npm run build\n"
    "4. IF ERROR: fix directly\n"
    "5. undertow -- QA before delivery\n"
    "6. message_result -- land the wave\n\n"
    "ELECTRON RULES:\n"
    "- ALWAYS template='electron-app' in project_init\n"
    "- ALWAYS use useIPC() hook for file read/write and dialogs -- NEVER fetch() or fs directly\n"
    "- ALWAYS use invoke('show-open-dialog', {...}) for native file dialogs\n"
    "- ALWAYS use invoke('read-file', path) / invoke('write-file', path, content)\n"
    "- NEVER use localStorage for file storage -- use invoke('write-file') to persist to disk\n"
    "- NEVER overwrite main.ts, preload.ts, vite.config.ts -- the scaffold handles those\n"
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

EL01_APP = '''import { useState, useCallback } from 'react';
import { useIPC } from './hooks/useIPC';

export default function App() {
  const { invoke } = useIPC();
  const [filePath, setFilePath] = useState<string>('');
  const [content, setContent] = useState<string>('');
  const [preview, setPreview] = useState<string>('');
  const [dirty, setDirty] = useState(false);

  const openFile = useCallback(async () => {
    const result = await invoke('show-open-dialog', {
      filters: [{ name: 'Markdown', extensions: ['md', 'txt'] }],
    }) as { canceled: boolean; filePaths: string[] };
    if (result.canceled || !result.filePaths[0]) return;
    const path = result.filePaths[0];
    const text = await invoke('read-file', path) as string;
    setFilePath(path);
    setContent(text);
    setPreview(renderMd(text));
    setDirty(false);
  }, [invoke]);

  const saveFile = useCallback(async () => {
    if (!filePath) {
      const result = await invoke('show-save-dialog', {
        filters: [{ name: 'Markdown', extensions: ['md'] }],
      }) as { canceled: boolean; filePath: string };
      if (result.canceled || !result.filePath) return;
      setFilePath(result.filePath);
      await invoke('write-file', result.filePath, content);
    } else {
      await invoke('write-file', filePath, content);
    }
    setDirty(false);
  }, [invoke, filePath, content]);

  const handleEdit = (val: string) => {
    setContent(val);
    setPreview(renderMd(val));
    setDirty(true);
  };

  return (
    <div style={{ display: 'flex', height: '100vh', flexDirection: 'column', background: '#0a0e17', color: '#e2e8f0' }}>
      <div style={{ padding: '8px 16px', background: '#141922', borderBottom: '1px solid #2d3748', display: 'flex', gap: 8 }}>
        <button onClick={openFile} style={{ padding: '4px 12px', background: '#3182ce', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>Open</button>
        <button onClick={saveFile} disabled={!dirty} style={{ padding: '4px 12px', background: dirty ? '#38a169' : '#2d3748', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>Save{dirty ? ' *' : ''}</button>
        <span style={{ color: '#718096', fontSize: 12, alignSelf: 'center' }}>{filePath || 'No file open'}</span>
      </div>
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <textarea
          value={content}
          onChange={e => handleEdit(e.target.value)}
          style={{ flex: 1, padding: 16, background: '#1a1f2e', color: '#e2e8f0', border: 'none', resize: 'none', fontFamily: 'monospace', fontSize: 14, outline: 'none' }}
          placeholder="Open a file or start typing..."
        />
        <div
          dangerouslySetInnerHTML={{ __html: preview }}
          style={{ flex: 1, padding: 16, background: '#0d1117', overflowY: 'auto', borderLeft: '1px solid #2d3748', lineHeight: 1.7 }}
        />
      </div>
    </div>
  );
}

function renderMd(text: string): string {
  return text
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}
'''

EL02_APP = '''import { useState, useCallback, useEffect } from 'react';
import { useIPC } from './hooks/useIPC';

interface Note { id: string; title: string; body: string; updatedAt: string; }

const NOTES_FILE = 'tsunami-notes.json';

export default function App() {
  const { invoke, appPath } = useIPC();
  const [notes, setNotes] = useState<Note[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');

  const notesPath = appPath ? `${appPath}/${NOTES_FILE}` : '';

  const load = useCallback(async (path: string) => {
    try {
      const raw = await invoke('read-file', path) as string;
      setNotes(JSON.parse(raw));
    } catch { setNotes([]); }
  }, [invoke]);

  useEffect(() => { if (notesPath) load(notesPath); }, [notesPath, load]);

  const save = useCallback(async (updated: Note[]) => {
    if (!notesPath) return;
    await invoke('write-file', notesPath, JSON.stringify(updated, null, 2));
    setNotes(updated);
  }, [invoke, notesPath]);

  const addNote = () => {
    const n: Note = { id: Date.now().toString(), title: 'New note', body: '', updatedAt: new Date().toISOString() };
    save([n, ...notes]);
    setSelected(n.id); setTitle(n.title); setBody(n.body);
  };

  const updateNote = (id: string, t: string, b: string) => {
    const updated = notes.map(n => n.id === id ? { ...n, title: t, body: b, updatedAt: new Date().toISOString() } : n);
    save(updated);
  };

  const deleteNote = (id: string) => {
    const updated = notes.filter(n => n.id !== id);
    save(updated);
    if (selected === id) { setSelected(null); setTitle(''); setBody(''); }
  };

  const select = (n: Note) => { setSelected(n.id); setTitle(n.title); setBody(n.body); };

  return (
    <div style={{ display: 'flex', height: '100vh', background: '#0a0e17', color: '#e2e8f0' }}>
      <div style={{ width: 240, background: '#141922', borderRight: '1px solid #2d3748', display: 'flex', flexDirection: 'column' }}>
        <button onClick={addNote} style={{ margin: 8, padding: '6px 12px', background: '#3182ce', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>+ New Note</button>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {notes.map(n => (
            <div key={n.id} onClick={() => select(n)} style={{ padding: '8px 12px', background: selected === n.id ? '#2d3748' : 'transparent', cursor: 'pointer', borderBottom: '1px solid #1e2535' }}>
              <div style={{ fontWeight: 500, fontSize: 14 }}>{n.title || 'Untitled'}</div>
              <div style={{ fontSize: 11, color: '#718096' }}>{new Date(n.updatedAt).toLocaleDateString()}</div>
              <button onClick={e => { e.stopPropagation(); deleteNote(n.id); }} style={{ marginTop: 2, fontSize: 10, background: 'none', border: 'none', color: '#e53e3e', cursor: 'pointer' }}>Delete</button>
            </div>
          ))}
        </div>
      </div>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 16 }}>
        {selected ? (
          <>
            <input value={title} onChange={e => { setTitle(e.target.value); updateNote(selected, e.target.value, body); }}
              style={{ marginBottom: 12, padding: '8px 12px', background: '#1a1f2e', color: '#e2e8f0', border: '1px solid #2d3748', borderRadius: 4, fontSize: 18, fontWeight: 600 }} />
            <textarea value={body} onChange={e => { setBody(e.target.value); updateNote(selected, title, e.target.value); }}
              style={{ flex: 1, padding: '12px', background: '#141922', color: '#e2e8f0', border: '1px solid #2d3748', borderRadius: 4, resize: 'none', fontSize: 14, lineHeight: 1.7 }} />
          </>
        ) : (
          <div style={{ color: '#718096', margin: 'auto' }}>Select a note or create one</div>
        )}
      </div>
    </div>
  );
}
'''

EL03_APP = '''import { useState, useCallback } from 'react';
import { useIPC } from './hooks/useIPC';

export default function App() {
  const { invoke } = useIPC();
  const [filePath, setFilePath] = useState('');
  const [content, setContent] = useState('');
  const [error, setError] = useState('');

  const openFile = useCallback(async () => {
    setError('');
    const result = await invoke('show-open-dialog', {
      properties: ['openFile'],
      filters: [
        { name: 'Text Files', extensions: ['txt', 'md', 'json', 'ts', 'tsx', 'js', 'css', 'html', 'py'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    }) as { canceled: boolean; filePaths: string[] };
    if (result.canceled || !result.filePaths[0]) return;
    const path = result.filePaths[0];
    try {
      const text = await invoke('read-file', path) as string;
      setFilePath(path);
      setContent(text);
    } catch (e) {
      setError(`Failed to read file: ${e}`);
    }
  }, [invoke]);

  const ext = filePath.split('.').pop() || 'txt';
  const lineCount = content.split('\n').length;
  const byteCount = new TextEncoder().encode(content).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#0a0e17', color: '#e2e8f0' }}>
      <div style={{ padding: '8px 16px', background: '#141922', borderBottom: '1px solid #2d3748', display: 'flex', alignItems: 'center', gap: 8 }}>
        <button onClick={openFile} style={{ padding: '4px 12px', background: '#3182ce', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>Open File</button>
        {filePath && <span style={{ color: '#a0aec0', fontSize: 13 }}>{filePath}</span>}
        {filePath && <span style={{ marginLeft: 'auto', color: '#718096', fontSize: 12 }}>{lineCount} lines · {byteCount} bytes · .{ext}</span>}
      </div>
      {error && <div style={{ padding: '8px 16px', background: '#742a2a', color: '#feb2b2', fontSize: 13 }}>{error}</div>}
      <pre style={{ flex: 1, margin: 0, padding: 16, overflowY: 'auto', fontFamily: 'monospace', fontSize: 13, lineHeight: 1.6, background: '#0d1117', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
        {content || <span style={{ color: '#4a5568' }}>Click "Open File" to read a file from disk…</span>}
      </pre>
    </div>
  );
}
'''

EL04_APP = '''import { useState, useCallback } from 'react';
import { useIPC } from './hooks/useIPC';

interface ImageInfo { path: string; name: string; size: number; width: number; height: number; }

export default function App() {
  const { invoke } = useIPC();
  const [info, setInfo] = useState<ImageInfo | null>(null);
  const [src, setSrc] = useState('');

  const openImage = useCallback(async () => {
    const result = await invoke('show-open-dialog', {
      properties: ['openFile'],
      filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp'] }],
    }) as { canceled: boolean; filePaths: string[] };
    if (result.canceled || !result.filePaths[0]) return;
    const path = result.filePaths[0];
    const raw = await invoke('read-file', path) as string;
    const bytes = new TextEncoder().encode(raw).length;
    const name = path.split('/').pop() || path.split('\\\\').pop() || path;
    const url = `file://${path}`;
    setSrc(url);
    const img = new Image();
    img.onload = () => setInfo({ path, name, size: bytes, width: img.naturalWidth, height: img.naturalHeight });
    img.src = url;
  }, [invoke]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#0a0e17', color: '#e2e8f0' }}>
      <div style={{ padding: '8px 16px', background: '#141922', borderBottom: '1px solid #2d3748', display: 'flex', gap: 8, alignItems: 'center' }}>
        <button onClick={openImage} style={{ padding: '4px 12px', background: '#3182ce', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>Open Image</button>
        {info && (
          <span style={{ color: '#a0aec0', fontSize: 13 }}>
            {info.name} · {info.width}×{info.height} · {(info.size / 1024).toFixed(1)} KB
          </span>
        )}
      </div>
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', background: '#0d1117' }}>
        {src ? (
          <img src={src} alt={info?.name} style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
        ) : (
          <div style={{ color: '#4a5568', textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 8 }}>🖼</div>
            <div>Click "Open Image" to view a file from disk</div>
          </div>
        )}
      </div>
    </div>
  );
}
'''

def make_tool_call(tool_name, **kwargs):
    return {"role": "assistant", "content": None, "tool_calls": [{"id": f"call_{tool_name}", "type": "function", "function": {"name": tool_name, "arguments": json.dumps(kwargs)}}]}

def make_tool_result(name, result):
    return {"role": "tool", "tool_call_id": f"call_{name}", "name": name, "content": json.dumps({"result": result})}

def tokenize_messages(msgs):
    text = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
    return text

examples = []

# EL01: Markdown editor
el01 = [
    {"role": "user", "content": "Build me a desktop markdown editor with live preview. I should be able to open .md files from disk, edit them, and save back. Split-pane layout."},
    make_tool_call("project_init", name="markdown-editor", template="electron-app"),
    make_tool_result("project_init", "Project 'markdown-editor' created at workspace/deliverables/markdown-editor/. electron-app scaffold with main.ts + preload.ts + src/hooks/useIPC.ts ready."),
    make_tool_call("file_write", path="src/App.tsx", content=EL01_APP),
    make_tool_result("file_write", "Written: src/App.tsx"),
    make_tool_call("shell_exec", command="cd workspace/deliverables/markdown-editor && npm run build 2>&1 | tail -5"),
    make_tool_result("shell_exec", "dist/index.html 1.2kB\ndist/assets/index-BxKp9q1a.js 145.3kB\n✓ built in 1.8s"),
    make_tool_call("undertow", path="workspace/deliverables/markdown-editor/dist/index.html"),
    make_tool_result("undertow", "PASS: Open button present. Textarea accepts input. Preview panel renders HTML. Split pane layout confirmed."),
    make_tool_call("message_result"),
    make_tool_result("message_result", "delivered"),
]
examples.append({"source": "EL01-markdown-editor", "messages": el01, "date": TODAY})

# EL02: Notes app
el02 = [
    {"role": "user", "content": "Build a desktop notes app. I want to create, edit, and delete notes. Notes should persist to disk even after closing the app."},
    make_tool_call("project_init", name="notes-app", template="electron-app"),
    make_tool_result("project_init", "Project 'notes-app' created at workspace/deliverables/notes-app/. electron-app scaffold ready."),
    make_tool_call("file_write", path="src/App.tsx", content=EL02_APP),
    make_tool_result("file_write", "Written: src/App.tsx"),
    make_tool_call("shell_exec", command="cd workspace/deliverables/notes-app && npm run build 2>&1 | tail -5"),
    make_tool_result("shell_exec", "dist/index.html 1.1kB\ndist/assets/index-CyMp3r2b.js 138.7kB\n✓ built in 1.7s"),
    make_tool_call("undertow", path="workspace/deliverables/notes-app/dist/index.html"),
    make_tool_result("undertow", "PASS: Note list sidebar visible. New Note button works. Title and body fields editable. Delete button present."),
    make_tool_call("message_result"),
    make_tool_result("message_result", "delivered"),
]
examples.append({"source": "EL02-notes-app", "messages": el02, "date": TODAY})

# EL03: File browser/viewer
el03 = [
    {"role": "user", "content": "Build a desktop file viewer. Click Open File to pick any text/code file using a native dialog. Display the content with line count and byte size."},
    make_tool_call("project_init", name="file-viewer", template="electron-app"),
    make_tool_result("project_init", "Project 'file-viewer' created at workspace/deliverables/file-viewer/. electron-app scaffold ready."),
    make_tool_call("file_write", path="src/App.tsx", content=EL03_APP),
    make_tool_result("file_write", "Written: src/App.tsx"),
    make_tool_call("shell_exec", command="cd workspace/deliverables/file-viewer && npm run build 2>&1 | tail -5"),
    make_tool_result("shell_exec", "dist/index.html 1.0kB\ndist/assets/index-DzQp1s3c.js 122.4kB\n✓ built in 1.5s"),
    make_tool_call("undertow", path="workspace/deliverables/file-viewer/dist/index.html"),
    make_tool_result("undertow", "PASS: Open File button present. Pre element for content display. Header shows path, line count, byte count when file loaded."),
    make_tool_call("message_result"),
    make_tool_result("message_result", "delivered"),
]
examples.append({"source": "EL03-file-viewer", "messages": el03, "date": TODAY})

# EL04: Image viewer
el04 = [
    {"role": "user", "content": "Build a desktop image viewer. Open image files via a native dialog, display them full-screen, show filename and dimensions."},
    make_tool_call("project_init", name="image-viewer", template="electron-app"),
    make_tool_result("project_init", "Project 'image-viewer' created at workspace/deliverables/image-viewer/. electron-app scaffold ready."),
    make_tool_call("file_write", path="src/App.tsx", content=EL04_APP),
    make_tool_result("file_write", "Written: src/App.tsx"),
    make_tool_call("shell_exec", command="cd workspace/deliverables/image-viewer && npm run build 2>&1 | tail -5"),
    make_tool_result("shell_exec", "dist/index.html 1.0kB\ndist/assets/index-EzQm2t4d.js 118.6kB\n✓ built in 1.4s"),
    make_tool_call("undertow", path="workspace/deliverables/image-viewer/dist/index.html"),
    make_tool_result("undertow", "PASS: Open Image button present. Image display area centered. Info bar for name and dimensions visible."),
    make_tool_call("message_result"),
    make_tool_result("message_result", "delivered"),
]
examples.append({"source": "EL04-image-viewer", "messages": el04, "date": TODAY})

# EL05: Error recovery — fetch() → useIPC
EL05_BAD_APP = '''import { useState } from 'react';

export default function App() {
  const [content, setContent] = useState('');

  const openFile = async () => {
    // fetch won't work for local files in Electron renderer
    const response = await fetch('/api/open-file');
    const data = await response.json();
    setContent(data.content);
  };

  return (
    <div>
      <button onClick={openFile}>Open</button>
      <pre>{content}</pre>
    </div>
  );
}
'''
EL05_FIXED_APP = '''import { useState, useCallback } from 'react';
import { useIPC } from './hooks/useIPC';

export default function App() {
  const { invoke } = useIPC();
  const [content, setContent] = useState('');
  const [filePath, setFilePath] = useState('');

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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#0a0e17', color: '#e2e8f0' }}>
      <div style={{ padding: 8, background: '#141922', borderBottom: '1px solid #2d3748', display: 'flex', gap: 8 }}>
        <button onClick={openFile} style={{ padding: '4px 12px', background: '#3182ce', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>Open</button>
        <span style={{ color: '#a0aec0', fontSize: 13 }}>{filePath}</span>
      </div>
      <pre style={{ flex: 1, padding: 16, margin: 0, fontFamily: 'monospace', fontSize: 13, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
        {content || 'Click Open to read a file'}
      </pre>
    </div>
  );
}
'''

el05 = [
    {"role": "user", "content": "Build a desktop file reader app. Open files via dialog, display their content."},
    make_tool_call("project_init", name="file-reader", template="electron-app"),
    make_tool_result("project_init", "Project 'file-reader' created. electron-app scaffold ready."),
    make_tool_call("file_write", path="src/App.tsx", content=EL05_BAD_APP),
    make_tool_result("file_write", "Written: src/App.tsx"),
    make_tool_call("shell_exec", command="cd workspace/deliverables/file-reader && npm run build 2>&1 | tail -8"),
    make_tool_result("shell_exec", "✓ built in 1.3s\nWARNING: fetch() does not work for local files in Electron renderer. Use window.electronAPI / useIPC() for file operations."),
    # Recovery: fix to useIPC
    make_tool_call("file_edit", path="src/App.tsx", old_text=EL05_BAD_APP, new_text=EL05_FIXED_APP),
    make_tool_result("file_edit", "Edited: src/App.tsx"),
    make_tool_call("shell_exec", command="cd workspace/deliverables/file-reader && npm run build 2>&1 | tail -5"),
    make_tool_result("shell_exec", "dist/index.html 1.0kB\ndist/assets/index-FxQn3u5e.js 120.1kB\n✓ built in 1.4s"),
    make_tool_call("undertow", path="workspace/deliverables/file-reader/dist/index.html"),
    make_tool_result("undertow", "PASS: Open button present. Content area displays pre-formatted text. useIPC pattern confirmed."),
    make_tool_call("message_result"),
    make_tool_result("message_result", "delivered"),
]
examples.append({"source": "EL05-error-recovery", "messages": el05, "date": TODAY})

# EL06: Conversational
el06 = [
    {"role": "user", "content": "Can you build desktop apps? What kind?"},
    make_tool_call("message_chat", text="Yes — I build Electron desktop apps with native OS integration. Examples:\n\n• **Markdown editors** with open/save via native file dialogs\n• **Notes apps** that persist JSON to disk across sessions\n• **File viewers** and **image viewers** using native open-file dialogs\n• **Text editors** with read/write to disk\n• Any app that needs native dialogs, system tray, or direct disk access\n\nThe key pattern: `useIPC()` hook for all file operations and dialogs — `invoke('show-open-dialog', ...)`, `invoke('read-file', path)`, `invoke('write-file', path, content)`. Want me to build one?", done=True),
    make_tool_result("message_chat", "sent"),
]
examples.append({"source": "EL06-conversational", "messages": el06, "date": TODAY})

# Write output
out_path = Path("workspace/training_data/electron_sft_v1.jsonl")
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w") as f:
    for ex in examples:
        msgs_text = tokenize_messages(ex["messages"])
        record = {
            "prompt": msgs_text,
            "completion": "",
            "source": ex["source"],
            "date": ex["date"],
        }
        f.write(json.dumps(record) + "\n")

print(f"\n=== ELECTRON SFT v1 SUMMARY ===")
print(f"  Examples: {len(examples)}")
print(f"  Output: {out_path}")
for ex in examples:
    print(f"  {ex['source']}: {len(ex['messages'])} messages")
