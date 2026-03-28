#!/usr/bin/env node
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { render, Box, Text, useInput, useApp, useStdout } from 'ink';
import TextInput from 'ink-text-input';
import Spinner from 'ink-spinner';
import WebSocket from 'ws';
import fs from 'fs';
import path from 'path';
import { execSync, spawn } from 'child_process';
import { fileURLToPath } from 'url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ARK_DIR = path.resolve(__dirname, '..');

// ── Banner: white froth → deep blue water ──
const BANNER_LINES = [
  { text: '▀▛▘▞▀▖▌ ▌▙ ▌▞▀▖▙▗▌▜▘', color: '#ffffff' },
  { text: ' ▌ ▚▄ ▌ ▌▌▌▌▙▄▌▌▘▌▐',  color: '#b0d4f1' },
  { text: ' ▌ ▖ ▌▌ ▌▌▝▌▌ ▌▌ ▌▐',  color: '#4a9eff' },
  { text: ' ▘ ▝▀ ▝▀ ▘ ▘▘ ▘▘ ▘▀▘', color: '#1a5ab8' },
];

const TOOL_LABELS = {
  file_read: 'Read', file_write: 'Write', file_edit: 'Edit',
  file_append: 'Append', file_view: 'View', match_glob: 'Search',
  match_grep: 'Grep', shell_exec: 'Run', shell_view: 'Check',
  shell_kill: 'Kill', search_web: 'Search web',
  browser_navigate: 'Navigate', plan_update: 'Plan',
  plan_advance: 'Advance plan',
};

function toolLabel(name, args) {
  const base = TOOL_LABELS[name] || name.replace(/_/g, ' ');
  const detail = args?.command || args?.path || args?.query || args?.pattern || args?.url || '';
  return detail ? `${base}(${String(detail).slice(0, 50)})` : base;
}

function timeAgo(start) {
  const s = Math.floor((Date.now() - start) / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s/60)}m ${s%60}s`;
}

function humanSize(bytes) {
  for (const u of ['B', 'KB', 'MB', 'GB']) {
    if (bytes < 1024) return `${bytes.toFixed(0)}${u}`;
    bytes /= 1024;
  }
  return `${bytes.toFixed(1)}TB`;
}

// ── Main App ──
function App({ serverUrl, singleTask }) {
  const { exit } = useApp();
  const { stdout } = useStdout();
  const cols = stdout?.columns || 80;

  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);
  const [running, setRunning] = useState(false);
  const [connected, setConnected] = useState(false);
  const [iteration, setIteration] = useState(0);
  const [startTime, setStartTime] = useState(null);
  const [currentAction, setCurrentAction] = useState(null);
  const [attachedFiles, setAttachedFiles] = useState([]);
  const wsRef = useRef(null);

  useEffect(() => {
    const ws = new WebSocket(serverUrl);
    wsRef.current = ws;
    ws.on('open', () => setConnected(true));
    ws.on('close', () => setConnected(false));

    ws.on('message', (data) => {
      const msg = JSON.parse(data.toString());

      if (msg.type === 'start') {
        setRunning(true);
        setIteration(0);
        setStartTime(Date.now());
        setCurrentAction(null);
      }

      if (msg.type === 'step') {
        setIteration(msg.iteration);
        for (const evt of (msg.events || [])) {
          if (evt.tool && !evt.tool.startsWith('message_')) {
            const label = toolLabel(evt.tool, evt.args || {});
            setCurrentAction(label);
            setMessages(prev => [...prev, {
              type: 'action',
              tool: evt.tool,
              label,
              args: evt.args || {},
              iter: msg.iteration,
            }]);
          }
          if (evt.tool === 'message_info') {
            const text = evt.args?.text;
            if (text) {
              setMessages(prev => [...prev, { type: 'agent', text }]);
              setCurrentAction(null);
            }
          }
        }
      }

      if (msg.type === 'complete') {
        setRunning(false);
        setCurrentAction(null);
        if (msg.result) {
          setMessages(prev => [...prev, { type: 'result', text: msg.result, iters: msg.iterations }]);
        }
        if (singleTask) setTimeout(() => exit(), 200);
      }

      if (msg.type === 'error') {
        setRunning(false);
        setCurrentAction(null);
        setMessages(prev => [...prev, { type: 'error', text: msg.message }]);
      }
    });

    return () => { try { ws.close(); } catch(e) {} };
  }, [serverUrl]);

  useEffect(() => {
    if (singleTask && connected) {
      setMessages([{ type: 'user', text: singleTask }]);
      wsRef.current?.send(JSON.stringify({ type: 'run', task: singleTask }));
    }
  }, [singleTask, connected]);

  // ── Slash commands — client-side, instant, no agent ──
  const [activeProject, setActiveProject] = useState(null);

  function handleSlashCommand(text) {
    const parts = text.split(/\s+/);
    const cmd = parts[0].toLowerCase();

    if (cmd === '/help') {
      setMessages(prev => [...prev, { type: 'user', text }, { type: 'result', text:
        'Commands:\n  /project              list projects\n  /project <name>       switch to project\n  /project new <name>   create new project\n  /serve [port]         serve active project\n  /help                 this message\n  exit                  quit\n\nAnything else goes to the agent.'
      }]);
      return true;
    }

    if (cmd === '/project') {
      const delDir = path.resolve(ARK_DIR, 'workspace/deliverables');

      // List projects: /project or /project list
      if (parts.length === 1 || parts[1] === 'list') {
        try {
          const entries = fs.readdirSync(delDir).filter(d => {
            try { return fs.statSync(path.join(delDir, d)).isDirectory() && !d.startsWith('.'); }
            catch { return false; }
          });
          const list = entries.length ? entries.map(d => {
            const hasTmd = fs.existsSync(path.join(delDir, d, 'tsunami.md'));
            const active = d === activeProject ? ' ← active' : '';
            return `  ${hasTmd ? '●' : '○'} ${d}${active}`;
          }).join('\n') : '  No projects yet. Use /project new <name>';
          setMessages(prev => [...prev, { type: 'user', text }, { type: 'result', text: `Projects:\n${list}` }]);
        } catch(e) {
          setMessages(prev => [...prev, { type: 'user', text }, { type: 'result', text: 'No projects directory found.' }]);
        }
        return true;
      }

      if (parts[1] === 'new' && parts[2]) {
        const name = parts[2];
        const projDir = path.join(delDir, name);
        fs.mkdirSync(projDir, { recursive: true });
        fs.writeFileSync(path.join(projDir, 'tsunami.md'), `# ${name}\n\nNew project.\n`);
        setActiveProject(name);
        setMessages(prev => [...prev, { type: 'user', text }, { type: 'result', text: `Created project: ${name}` }]);
        return true;
      }

      // Switch project
      const name = parts[1];
      const projDir = path.join(delDir, name);
      if (!fs.existsSync(projDir) || !fs.statSync(projDir).isDirectory()) {
        setMessages(prev => [...prev, { type: 'user', text }, { type: 'error', text: `Project '${name}' not found` }]);
        return true;
      }
      setActiveProject(name);
      const tmdPath = path.join(projDir, 'tsunami.md');
      const context = fs.existsSync(tmdPath) ? fs.readFileSync(tmdPath, 'utf-8') : 'No tsunami.md';
      const files = fs.readdirSync(projDir).filter(f => f !== 'tsunami.md');
      setMessages(prev => [...prev, { type: 'user', text }, { type: 'result', text: `Active: ${name}\n\n${context}\n\nFiles: ${files.join(', ') || 'none'}` }]);
      return true;
    }

    if (cmd === '/serve') {
      const port = parts[1] || '8080';
      const serveDir = activeProject
        ? path.resolve(ARK_DIR, 'workspace/deliverables', activeProject)
        : path.resolve(ARK_DIR, 'workspace/deliverables');
      spawn('python3', ['-m', 'http.server', port, '--directory', serveDir], {
        detached: true, stdio: 'ignore'
      }).unref();
      setMessages(prev => [...prev, { type: 'user', text }, { type: 'result', text: `Serving on http://localhost:${port}` }]);
      return true;
    }

    // Unknown slash command
    setMessages(prev => [...prev, { type: 'user', text }, { type: 'error', text: `Unknown command: ${cmd}. Type /help` }]);
    return true;
  }

  const handleSubmit = useCallback((value) => {
    const text = value.trim();
    if (!text && attachedFiles.length === 0) return;

    if (['exit', 'quit'].includes(text.toLowerCase())) {
      exit();
      return;
    }

    // Slash commands — instant, no agent
    if (text.startsWith('/')) {
      setInput('');
      handleSlashCommand(text);
      return;
    }

    setInput('');

    // Build task with file context
    let task = text;
    const fileInfos = [];

    for (const f of attachedFiles) {
      const ext = path.extname(f).toLowerCase();
      const isImage = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'].includes(ext);
      if (isImage) {
        task += `\n[Attached image: ${f}]`;
        fileInfos.push({ path: f, type: 'image' });
      } else {
        task += `\n[Attached file: ${f}]`;
        fileInfos.push({ path: f, type: 'file' });
      }
    }

    setMessages(prev => [...prev, {
      type: 'user',
      text,
      files: [...attachedFiles],
    }]);
    setAttachedFiles([]);
    wsRef.current?.send(JSON.stringify({ type: 'run', task }));
  }, [exit, attachedFiles]);

  // Key bindings — Ctrl+C does NOT exit, only cancels current action
  useInput((ch, key) => {
    if (key.ctrl && ch === 'c') {
      if (running) {
        // Cancel current task (TODO: send cancel to backend)
        setRunning(false);
        setCurrentAction(null);
        setMessages(prev => [...prev, { type: 'error', text: 'interrupted' }]);
      }
      // Don't exit — user can keep typing
      return;
    }

    // Ctrl+D to exit
    if (key.ctrl && ch === 'd') {
      exit();
      return;
    }

    // /attach <path> command
  }, { isActive: !singleTask });

  // Handle /commands in input
  const handleChange = useCallback((value) => {
    // Check for /attach command
    if (value.endsWith(' ') && value.trim().startsWith('/attach ')) {
      const filePath = value.trim().slice(8).trim();
      if (filePath && fs.existsSync(filePath)) {
        setAttachedFiles(prev => [...prev, filePath]);
        setInput('');
        return;
      }
    }
    setInput(value);
  }, []);

  return (
    <Box flexDirection="column" width={cols}>
      {/* Banner */}
      <Box flexDirection="column">
        {BANNER_LINES.map((line, i) => (
          <Text key={i} bold color={line.color}>{line.text}</Text>
        ))}
      </Box>
      <Text color="#4a9eff" bold> Agentic Reborn</Text>
      <Text> </Text>

      {/* Messages */}
      {messages.map((msg, i) => (
        <MessageView key={i} msg={msg} cols={cols} />
      ))}

      {/* Current activity */}
      {running && currentAction && (
        <Box marginLeft={2}>
          <Text color="#4a9eff"><Spinner type="dots" /></Text>
          <Text dimColor> {currentAction}</Text>
        </Box>
      )}
      {running && !currentAction && (
        <Box marginLeft={2}>
          <Text color="#4a9eff"><Spinner type="dots" /></Text>
          <Text dimColor> thinking...</Text>
        </Box>
      )}

      {/* Timer */}
      {running && startTime && (
        <Box marginTop={0} marginLeft={2}>
          <Text dimColor>({timeAgo(startTime)} · iteration {iteration})</Text>
        </Box>
      )}

      {/* Attached files indicator */}
      {attachedFiles.length > 0 && !running && (
        <Box marginLeft={2} marginTop={1}>
          {attachedFiles.map((f, i) => {
            const ext = path.extname(f).toLowerCase();
            const isImg = ['.png','.jpg','.jpeg','.gif','.webp'].includes(ext);
            const size = fs.existsSync(f) ? humanSize(fs.statSync(f).size) : '?';
            return (
              <Box key={i} marginRight={2}>
                <Text color={isImg ? 'magenta' : 'yellow'}>
                  {isImg ? '🖼 ' : '📎 '}{path.basename(f)} ({size})
                </Text>
              </Box>
            );
          })}
        </Box>
      )}

      {/* Command suggestions */}
      {!running && !singleTask && input.startsWith('/') && input.length < 15 && (
        <Box flexDirection="column" marginLeft={2} marginBottom={0}>
          {[
            { cmd: '/project', desc: 'list / switch / create projects' },
            { cmd: '/serve', desc: 'host active project on localhost' },
            { cmd: '/attach', desc: 'attach a file or image' },
            { cmd: '/help', desc: 'show all commands' },
          ].filter(c => c.cmd.startsWith(input)).map((c, i) => (
            <Box key={i}>
              <Text color="#4a9eff">{c.cmd}</Text>
              <Text dimColor>  {c.desc}</Text>
            </Box>
          ))}
        </Box>
      )}

      {/* Input */}
      {!running && !singleTask && (
        <Box flexDirection="column" marginTop={0}>
          <Box
            borderStyle="round"
            borderColor="#4a9eff"
            paddingLeft={1}
            paddingRight={1}
            width={cols - 2}
          >
            <TextInput
              value={input}
              onChange={handleChange}
              onSubmit={handleSubmit}
              placeholder=""
            />
          </Box>
          {!input.startsWith('/') && (
            <Box marginLeft={2}>
              <Text dimColor>type / for commands · exit to quit</Text>
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}

// ── Messages ──
function MessageView({ msg, cols }) {
  if (msg.type === 'user') {
    return (
      <Box flexDirection="column" marginTop={1} marginBottom={1}>
        <Box paddingLeft={1}>
          <Text backgroundColor="#2a2a3a" color="white"> {msg.text} </Text>
        </Box>
        {msg.files && msg.files.length > 0 && (
          <Box marginLeft={2}>
            {msg.files.map((f, i) => {
              const ext = path.extname(f).toLowerCase();
              const isImg = ['.png','.jpg','.jpeg','.gif','.webp'].includes(ext);
              return (
                <Text key={i} dimColor> {isImg ? '🖼' : '📎'} {path.basename(f)}</Text>
              );
            })}
          </Box>
        )}
      </Box>
    );
  }

  if (msg.type === 'action') {
    return (
      <Box marginLeft={1}>
        <Text color="#4a9eff">● </Text>
        <Text bold color="#4a9eff">{msg.label.split('(')[0]}</Text>
        {msg.label.includes('(') && (
          <Text dimColor>({msg.label.split('(').slice(1).join('(')})</Text>
        )}
      </Box>
    );
  }

  if (msg.type === 'agent') {
    return (
      <Box marginLeft={2} marginTop={0}>
        <Text wrap="wrap">{msg.text}</Text>
      </Box>
    );
  }

  if (msg.type === 'result') {
    return (
      <Box flexDirection="column" marginTop={1}>
        <Box marginLeft={2}>
          <Text wrap="wrap">{msg.text}</Text>
        </Box>
        {msg.iters && (
          <Box marginLeft={2} marginTop={0}>
            <Text color="#4a9eff">✓ completed ({msg.iters} {msg.iters === 1 ? 'iteration' : 'iterations'})</Text>
          </Box>
        )}
      </Box>
    );
  }

  if (msg.type === 'error') {
    return (
      <Box marginLeft={2} marginTop={1}>
        <Text color="red">✗ {msg.text}</Text>
      </Box>
    );
  }

  return null;
}

// ── CLI entry ──
const args = process.argv.slice(2);
let task = null;
let wsPort = 3000;
let attachFiles = [];

for (let i = 0; i < args.length; i++) {
  if (args[i] === '--task' && args[i + 1]) task = args[++i];
  if (args[i] === '--port' && args[i + 1]) wsPort = parseInt(args[++i]);
  if (args[i] === '--attach' && args[i + 1]) attachFiles.push(args[++i]);
}

// If task has attachments, append them
if (task && attachFiles.length > 0) {
  for (const f of attachFiles) {
    task += `\n[Attached file: ${f}]`;
  }
}

const serverUrl = `ws://localhost:${wsPort}/ws`;
render(<App serverUrl={serverUrl} singleTask={task} />);
