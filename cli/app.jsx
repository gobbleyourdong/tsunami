#!/usr/bin/env node
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { render, Box, Text, useInput, useApp, useStdout } from 'ink';
import TextInput from 'ink-text-input';
import Spinner from 'ink-spinner';
import WebSocket from 'ws';
import fs from 'fs';
import os from 'os';
import path from 'path';
import { execSync, spawn } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ARK_DIR = path.resolve(__dirname, '..');
const HOME_DIR = os.homedir();

// Banner: white froth -> deep blue water
const BANNER_LINES = [
  { text: '▀▛▘▞▀▖▌ ▌▙ ▌▞▀▖▙▗▌▜▘', color: '#ffffff' },
  { text: ' ▌ ▚▄ ▌ ▌▌▌▌▙▄▌▌▘▌▐', color: '#b0d4f1' },
  { text: ' ▌ ▖ ▌▌ ▌▌▝▌▌ ▌▌ ▌▐', color: '#4a9eff' },
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

const COMMANDS = [
  { cmd: '/project', desc: 'list / switch / create projects', takesArgs: true },
  { cmd: '/serve', desc: 'host active project on localhost', takesArgs: true },
  { cmd: '/attach', desc: 'attach a file or image', takesArgs: true },
  { cmd: '/unattach', desc: 'remove an attached file', takesArgs: true },
  { cmd: '/detach', desc: 'alias for /unattach', takesArgs: true },
  { cmd: '/help', desc: 'show all commands', takesArgs: false },
];

function toolLabel(name, args) {
  const base = TOOL_LABELS[name] || name.replace(/_/g, ' ');
  const detail = args?.command || args?.path || args?.query || args?.pattern || args?.url || '';
  return detail ? `${base}(${String(detail).slice(0, 50)})` : base;
}

function timeAgo(start) {
  const s = Math.floor((Date.now() - start) / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

function humanSize(bytes) {
  for (const unit of ['B', 'KB', 'MB', 'GB']) {
    if (bytes < 1024) return `${bytes.toFixed(0)}${unit}`;
    bytes /= 1024;
  }
  return `${bytes.toFixed(1)}TB`;
}

function expandHome(rawPath) {
  if (!rawPath) return process.cwd();
  if (rawPath === '~') return HOME_DIR;
  if (rawPath.startsWith('~/') || rawPath.startsWith('~\\')) {
    return path.join(HOME_DIR, rawPath.slice(2));
  }
  if (path.isAbsolute(rawPath)) return rawPath;
  return path.resolve(process.cwd(), rawPath);
}

function compactHome(rawPath) {
  if (!rawPath) return rawPath;
  if (rawPath === HOME_DIR) return '~';
  if (rawPath.startsWith(`${HOME_DIR}${path.sep}`)) {
    return `~${path.sep}${rawPath.slice(HOME_DIR.length + 1)}`;
  }
  return rawPath;
}

function parseCommand(text) {
  const trimmed = text.trim();
  const firstSpace = trimmed.indexOf(' ');
  if (firstSpace === -1) {
    return { cmd: trimmed.toLowerCase(), argText: '', argWords: [] };
  }

  const cmd = trimmed.slice(0, firstSpace).toLowerCase();
  const argText = trimmed.slice(firstSpace + 1).trim();
  return { cmd, argText, argWords: argText ? argText.split(/\s+/) : [] };
}

function sortEntries(entries) {
  return entries.sort((a, b) => {
    if (a.isDirectory() !== b.isDirectory()) {
      return a.isDirectory() ? -1 : 1;
    }
    return a.name.localeCompare(b.name);
  });
}

function makeCommandSuggestions(input) {
  const normalized = input.toLowerCase();
  return COMMANDS
    .filter(command => command.cmd.startsWith(normalized))
    .map(command => ({
      kind: 'command',
      value: command.takesArgs ? `${command.cmd} ` : command.cmd,
      label: command.cmd,
      desc: command.desc,
    }));
}

function makePathSuggestions(rawPath) {
  if (!rawPath) return [];

  const separator = rawPath.includes('\\') ? '\\' : path.sep;
  const trailingSeparator = /[\\/]+$/.test(rawPath);
  let baseInput = '';
  let resolvedDir = process.cwd();
  let prefix = '';

  if (rawPath === '~') {
    baseInput = `~${separator}`;
    resolvedDir = HOME_DIR;
  } else if (trailingSeparator) {
    baseInput = rawPath;
    resolvedDir = expandHome(rawPath);
  } else {
    const lastSlash = Math.max(rawPath.lastIndexOf('/'), rawPath.lastIndexOf('\\'));
    if (lastSlash >= 0) {
      baseInput = rawPath.slice(0, lastSlash + 1);
      prefix = rawPath.slice(lastSlash + 1);
      resolvedDir = expandHome(baseInput);
    } else {
      prefix = rawPath;
    }
  }

  try {
    const entries = sortEntries(fs.readdirSync(resolvedDir, { withFileTypes: true }))
      .filter(entry => entry.name.toLowerCase().startsWith(prefix.toLowerCase()));

    return entries.map(entry => {
      const suffix = entry.isDirectory() ? separator : '';
      const completed = `${baseInput}${entry.name}${suffix}`;
      return {
        kind: 'path',
        value: completed,
        label: completed,
        desc: entry.isDirectory() ? 'directory' : 'file',
      };
    });
  } catch {
    return [];
  }
}

function makeDetachSuggestions(argText, attachedFiles) {
  const query = argText.trim().toLowerCase();
  const results = attachedFiles
    .map((filePath, index) => ({
      filePath,
      display: compactHome(filePath),
      basename: path.basename(filePath),
      index,
    }))
    .filter(file => {
      if (!query) return true;
      return (
        file.basename.toLowerCase().startsWith(query) ||
        file.display.toLowerCase().startsWith(query) ||
        file.display.toLowerCase().includes(query)
      );
    })
    .map(file => ({
      kind: 'detach',
      value: `/unattach ${file.display}`,
      label: file.display,
      desc: `attached #${file.index + 1}`,
    }));

  if ('all'.startsWith(query)) {
    results.unshift({
      kind: 'detach',
      value: '/unattach all',
      label: 'all',
      desc: 'remove every attached file',
    });
  }

  return results;
}

function makeSuggestions(input, attachedFiles) {
  if (!input.startsWith('/')) return [];

  const trimmed = input.trim();
  const hasArgs = /\s/.test(trimmed);
  if (!hasArgs && !input.endsWith(' ')) {
    return makeCommandSuggestions(trimmed);
  }

  const { cmd, argText } = parseCommand(input);
  if (cmd === '/attach') {
    return makePathSuggestions(argText).map(suggestion => ({
      ...suggestion,
      value: `/attach ${suggestion.value}`,
    }));
  }

  if (cmd === '/unattach' || cmd === '/detach') {
    return makeDetachSuggestions(argText, attachedFiles);
  }

  return [];
}

function previewText(text, maxLen = 120) {
  if (!text) return '';
  const compact = String(text).replace(/\s+/g, ' ').trim();
  if (compact.length <= maxLen) return compact;
  return `${compact.slice(0, maxLen - 3)}...`;
}

function traceLineForEvent(evt, iteration) {
  if (evt.tool && !evt.tool.startsWith('message_')) {
    const label = toolLabel(evt.tool, evt.args || {});
    return {
      kind: 'call',
      iteration,
      text: label,
    };
  }

  if (evt.role === 'tool_result') {
    return {
      kind: evt.content?.includes('ERROR:') ? 'error' : 'result',
      iteration,
      text: previewText(evt.content || ''),
    };
  }

  if (evt.tool === 'message_info') {
    return {
      kind: 'info',
      iteration,
      text: previewText(evt.args?.text || ''),
    };
  }

  return null;
}

function App({ serverUrl, singleTask }) {
  const { exit } = useApp();
  const { stdout } = useStdout();
  const cols = stdout?.columns || 80;
  const healthUrl = serverUrl.replace(/^ws/, 'http').replace(/\/ws$/, '/api/health');

  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);
  const [traceEntries, setTraceEntries] = useState([]);
  const [running, setRunning] = useState(false);
  const [connected, setConnected] = useState(false);
  const [health, setHealth] = useState(null);
  const [iteration, setIteration] = useState(0);
  const [startTime, setStartTime] = useState(null);
  const [currentAction, setCurrentAction] = useState(null);
  const [showTrace, setShowTrace] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [selectedSuggestion, setSelectedSuggestion] = useState(0);
  const [activeProject, setActiveProject] = useState(null);
  const [inputVersion, setInputVersion] = useState(0);
  const wsRef = useRef(null);
  const attachedFilesRef = useRef([]);

  const updateAttachedFiles = useCallback(updater => {
    setAttachedFiles(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      attachedFilesRef.current = next;
      return next;
    });
  }, []);

  useEffect(() => {
    const ws = new WebSocket(serverUrl);
    wsRef.current = ws;
    ws.on('open', () => setConnected(true));
    ws.on('close', () => setConnected(false));

    ws.on('message', data => {
      const msg = JSON.parse(data.toString());

      if (msg.type === 'start') {
        setRunning(true);
        setIteration(0);
        setStartTime(Date.now());
        setCurrentAction(null);
        setTraceEntries([{
          kind: 'status',
          iteration: 0,
          text: `run started: ${previewText(msg.task || '', 140)}`,
        }]);
      }

      if (msg.type === 'step') {
        setIteration(msg.iteration);
        const nextTraceEntries = [];
        for (const evt of msg.events || []) {
          const traceLine = traceLineForEvent(evt, msg.iteration);
          if (traceLine) {
            nextTraceEntries.push(traceLine);
          }

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
        if (nextTraceEntries.length > 0) {
          setTraceEntries(prev => [...prev, ...nextTraceEntries].slice(-200));
        }
      }

      if (msg.type === 'complete') {
        setRunning(false);
        setCurrentAction(null);
        setTraceEntries(prev => [...prev, {
          kind: 'status',
          iteration: msg.iterations,
          text: `run completed after ${msg.iterations} ${msg.iterations === 1 ? 'iteration' : 'iterations'}`,
        }].slice(-200));
        if (msg.result) {
          setMessages(prev => [...prev, { type: 'result', text: msg.result, iters: msg.iterations }]);
        }
        if (singleTask) setTimeout(() => exit(), 200);
      }

      if (msg.type === 'error') {
        setRunning(false);
        setCurrentAction(null);
        setTraceEntries(prev => [...prev, {
          kind: 'error',
          iteration: msg.iteration ?? msg.iterations ?? iteration,
          text: previewText(msg.message || 'agent error', 160),
        }].slice(-200));
        setMessages(prev => [...prev, {
          type: 'error',
          text: msg.message,
          iters: msg.iteration ?? msg.iterations,
        }]);
      }
    });

    return () => {
      try {
        ws.close();
      } catch {}
    };
  }, [exit, serverUrl, singleTask]);

  useEffect(() => {
    let cancelled = false;

    async function pollHealth() {
      try {
        const resp = await fetch(healthUrl);
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`);
        }
        const data = await resp.json();
        if (!cancelled) {
          setHealth(data);
        }
      } catch (error) {
        if (!cancelled) {
          setHealth({
            backend_ok: false,
            error: error?.message || 'backend unavailable',
          });
        }
      }
    }

    pollHealth();
    const timer = setInterval(pollHealth, 3000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [healthUrl]);

  useEffect(() => {
    if (singleTask && connected) {
      setMessages([{ type: 'user', text: singleTask }]);
      wsRef.current?.send(JSON.stringify({ type: 'run', task: singleTask }));
    }
  }, [singleTask, connected]);

  useEffect(() => {
    const nextSuggestions = makeSuggestions(input, attachedFiles);
    setSuggestions(nextSuggestions);
    setSelectedSuggestion(0);
  }, [input, attachedFiles]);

  function addAttachedFile(rawPath) {
    const resolvedPath = path.resolve(expandHome(rawPath));
    const currentAttachedFiles = attachedFilesRef.current;
    if (!fs.existsSync(resolvedPath)) {
      return { ok: false, message: `File not found: ${rawPath}` };
    }
    if (currentAttachedFiles.includes(resolvedPath)) {
      return { ok: false, message: `Already attached: ${path.basename(resolvedPath)}` };
    }
    updateAttachedFiles(prev => [...prev, resolvedPath]);
    return { ok: true, message: `Attached: ${path.basename(resolvedPath)}` };
  }

  function removeAttachedFile(rawTarget) {
    const target = rawTarget.trim();
    const currentAttachedFiles = attachedFilesRef.current;
    if (!target) {
      return { ok: false, message: 'Usage: /unattach <index|path|basename|all>' };
    }

    if (target.toLowerCase() === 'all') {
      if (currentAttachedFiles.length === 0) {
        return { ok: false, message: 'No attached files.' };
      }
      const removedCount = currentAttachedFiles.length;
      updateAttachedFiles([]);
      return { ok: true, message: `Removed ${removedCount} attached ${removedCount === 1 ? 'file' : 'files'}.` };
    }

    const index = Number.parseInt(target, 10);
    if (Number.isInteger(index) && String(index) === target && index >= 1 && index <= currentAttachedFiles.length) {
      const removed = currentAttachedFiles[index - 1];
      updateAttachedFiles(prev => prev.filter((_, i) => i !== index - 1));
      return { ok: true, message: `Removed: ${path.basename(removed)}` };
    }

    const resolvedTarget = path.resolve(expandHome(target));
    const exactMatches = currentAttachedFiles.filter(filePath => (
      filePath === resolvedTarget ||
      compactHome(filePath) === target
    ));
    if (exactMatches.length === 1) {
      const match = exactMatches[0];
      updateAttachedFiles(prev => prev.filter(filePath => filePath !== match));
      return { ok: true, message: `Removed: ${path.basename(match)}` };
    }
    if (exactMatches.length > 1) {
      return { ok: false, message: `Multiple attached files match '${target}'. Use /unattach <index> instead.` };
    }

    const basenameMatches = currentAttachedFiles.filter(filePath => path.basename(filePath) === target);
    if (basenameMatches.length === 1) {
      const match = basenameMatches[0];
      updateAttachedFiles(prev => prev.filter(filePath => filePath !== match));
      return { ok: true, message: `Removed: ${path.basename(match)}` };
    }
    if (basenameMatches.length > 1) {
      return { ok: false, message: `Multiple attached files match '${target}'. Use /unattach <index> instead.` };
    }

    return { ok: false, message: `Attached file not found: ${target}` };
  }

  function acceptSuggestion() {
    if (suggestions.length === 0) return false;
    setInput(suggestions[selectedSuggestion]?.value ?? input);
    setInputVersion(prev => prev + 1);
    return true;
  }

  function handleSlashCommand(text) {
    const { cmd, argText, argWords } = parseCommand(text);

    if (cmd === '/help') {
      setMessages(prev => [...prev, { type: 'user', text }, { type: 'result', text:
        'Commands:\n  /project              list / switch / create projects\n  /project <name>       switch to project\n  /project new <name>   create new project\n  /serve [port]         serve active project\n  /attach <path>        attach a file or image\n  /unattach <target>    remove an attached file\n  /help                 this message\n  exit                  quit\n\nAnything else goes to the agent.'
      }]);
      return true;
    }

    if (cmd === '/project') {
      const deliverablesDir = path.resolve(ARK_DIR, 'workspace/deliverables');

      if (argWords.length === 0 || argWords[0] === 'list') {
        try {
          const entries = fs.readdirSync(deliverablesDir).filter(entry => {
            try {
              return fs.statSync(path.join(deliverablesDir, entry)).isDirectory() && !entry.startsWith('.');
            } catch {
              return false;
            }
          });
          const listing = entries.length
            ? entries.map(entry => {
                const hasTsunamiMd = fs.existsSync(path.join(deliverablesDir, entry, 'tsunami.md'));
                const active = entry === activeProject ? ' <- active' : '';
                return `  ${hasTsunamiMd ? '●' : '○'} ${entry}${active}`;
              }).join('\n')
            : '  No projects yet. Use /project new <name>';
          setMessages(prev => [...prev, { type: 'user', text }, { type: 'result', text: `Projects:\n${listing}` }]);
        } catch {
          setMessages(prev => [...prev, { type: 'user', text }, { type: 'result', text: 'No projects directory found.' }]);
        }
        return true;
      }

      if (argWords[0] === 'new' && argWords[1]) {
        const name = argWords.slice(1).join(' ');
        const projectDir = path.join(deliverablesDir, name);
        fs.mkdirSync(projectDir, { recursive: true });
        fs.writeFileSync(path.join(projectDir, 'tsunami.md'), `# ${name}\n\nNew project.\n`);
        setActiveProject(name);
        setMessages(prev => [...prev, { type: 'user', text }, { type: 'result', text: `Created project: ${name}` }]);
        return true;
      }

      const name = argText;
      const projectDir = path.join(deliverablesDir, name);
      if (!fs.existsSync(projectDir) || !fs.statSync(projectDir).isDirectory()) {
        setMessages(prev => [...prev, { type: 'user', text }, { type: 'error', text: `Project '${name}' not found` }]);
        return true;
      }

      setActiveProject(name);
      const contextPath = path.join(projectDir, 'tsunami.md');
      const context = fs.existsSync(contextPath) ? fs.readFileSync(contextPath, 'utf-8') : 'No tsunami.md';
      const files = fs.readdirSync(projectDir).filter(file => file !== 'tsunami.md');
      setMessages(prev => [...prev, {
        type: 'user',
        text,
      }, {
        type: 'result',
        text: `Active: ${name}\n\n${context}\n\nFiles: ${files.join(', ') || 'none'}`,
      }]);
      return true;
    }

    if (cmd === '/serve') {
      const port = argWords[0] || '8080';
      const serveDir = activeProject
        ? path.resolve(ARK_DIR, 'workspace/deliverables', activeProject)
        : path.resolve(ARK_DIR, 'workspace/deliverables');
      spawn('python3', ['-m', 'http.server', port, '--directory', serveDir], {
        detached: true,
        stdio: 'ignore',
      }).unref();
      setMessages(prev => [...prev, { type: 'user', text }, { type: 'result', text: `Serving on http://localhost:${port}` }]);
      return true;
    }

    if (cmd === '/attach') {
      if (argText) {
        const result = addAttachedFile(argText);
        setMessages(prev => [...prev, { type: 'user', text }, { type: result.ok ? 'result' : 'error', text: result.message }]);
        return true;
      }

      try {
        const selected = execSync(
          'zenity --file-selection --title="Attach file" 2>/dev/null || kdialog --getopenfilename ~ 2>/dev/null',
          { encoding: 'utf-8', timeout: 30000 }
        ).trim();
        if (selected && fs.existsSync(selected)) {
          const result = addAttachedFile(selected);
          setMessages(prev => [...prev, { type: 'result', text: result.message }]);
        }
      } catch {
        setMessages(prev => [...prev, { type: 'result', text: 'Cancelled (or use /attach <path>)' }]);
      }
      return true;
    }

    if (cmd === '/unattach' || cmd === '/detach') {
      if (!argText) {
        if (attachedFilesRef.current.length === 0) {
          setMessages(prev => [...prev, { type: 'user', text }, { type: 'result', text: 'No attached files.' }]);
          return true;
        }
        const listing = attachedFilesRef.current
          .map((filePath, index) => `  ${index + 1}. ${compactHome(filePath)}`)
          .join('\n');
        setMessages(prev => [...prev, {
          type: 'user',
          text,
        }, {
          type: 'result',
          text: `Attached files:\n${listing}\n\nUse /unattach <index|path|basename|all>.`,
        }]);
        return true;
      }

      const result = removeAttachedFile(argText);
      setMessages(prev => [...prev, { type: 'user', text }, { type: result.ok ? 'result' : 'error', text: result.message }]);
      return true;
    }

    setMessages(prev => [...prev, { type: 'user', text }, { type: 'error', text: `Unknown command: ${cmd}. Type /help` }]);
    return true;
  }

  const handleSubmit = useCallback(value => {
    const text = value.trim();
    const currentAttachedFiles = attachedFilesRef.current;
    if (!text && currentAttachedFiles.length === 0) return;

    if (['exit', 'quit'].includes(text.toLowerCase())) {
      exit();
      return;
    }

    if (text.startsWith('/')) {
      setInput('');
      handleSlashCommand(text);
      return;
    }

    setInput('');

    let task = text;
    for (const filePath of currentAttachedFiles) {
      const ext = path.extname(filePath).toLowerCase();
      const isImage = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'].includes(ext);
      task += `\n[Attached ${isImage ? 'image' : 'file'}: ${filePath}]`;
    }

    setMessages(prev => [...prev, {
      type: 'user',
      text,
      files: [...currentAttachedFiles],
    }]);
    updateAttachedFiles([]);
    wsRef.current?.send(JSON.stringify({ type: 'run', task }));
  }, [exit, updateAttachedFiles]);

  useInput((ch, key) => {
    if (key.ctrl && ch === 'c') {
      if (running) {
        setRunning(false);
        setCurrentAction(null);
        setMessages(prev => [...prev, { type: 'error', text: 'interrupted' }]);
      }
      return;
    }

    if (key.ctrl && ch === 'd') {
      exit();
      return;
    }

    if ((running || showTrace) && !key.ctrl && !key.meta && !key.shift && ch === 't') {
      setShowTrace(prev => !prev);
      return;
    }

    if (suggestions.length > 0 && key.upArrow) {
      setSelectedSuggestion(prev => (prev === 0 ? suggestions.length - 1 : prev - 1));
      return;
    }

    if (suggestions.length > 0 && key.downArrow) {
      setSelectedSuggestion(prev => (prev + 1) % suggestions.length);
      return;
    }

    if (suggestions.length > 0 && (key.tab || ch === '\t')) {
      acceptSuggestion();
      return;
    }
  }, { isActive: !singleTask });

  const handleChange = useCallback(value => {
    setInput(value);
  }, []);

  return (
    <Box flexDirection="column" width={cols}>
      <Box flexDirection="column">
        {BANNER_LINES.map((line, index) => (
          <Text key={index} bold color={line.color}>{line.text}</Text>
        ))}
      </Box>
      <Text color="#4a9eff" bold> Autonomous Execution Agent</Text>
      <Text> </Text>

      <StatusView connected={connected} health={health} />
      <Text> </Text>

      {showTrace ? (
        <TraceTailView entries={traceEntries} cols={cols} />
      ) : (
        messages.map((msg, index) => (
          <MessageView key={index} msg={msg} cols={cols} />
        ))
      )}

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

      {running && startTime && (
        <Box marginTop={0} marginLeft={2}>
          <Text dimColor>({timeAgo(startTime)} · iteration {iteration})</Text>
          <Text dimColor>  · press t for {showTrace ? 'normal view' : 'trace tail'}</Text>
        </Box>
      )}

      {attachedFiles.length > 0 && !running && (
        <Box flexDirection="column" marginLeft={2} marginTop={1}>
          <Text dimColor>Attached files:</Text>
          {attachedFiles.map((filePath, index) => {
            const ext = path.extname(filePath).toLowerCase();
            const isImage = ['.png', '.jpg', '.jpeg', '.gif', '.webp'].includes(ext);
            const size = fs.existsSync(filePath) ? humanSize(fs.statSync(filePath).size) : '?';
            return (
              <Box key={filePath} marginRight={2}>
                <Text color={isImage ? 'magenta' : 'yellow'}>
                  {index + 1}. {isImage ? 'image' : 'file'} {path.basename(filePath)} ({size})
                </Text>
                <Text dimColor>  {compactHome(filePath)}</Text>
              </Box>
            );
          })}
          <Box>
            <Text dimColor>Use /unattach &lt;index|path|basename|all&gt; to remove attachments.</Text>
          </Box>
        </Box>
      )}

      {!running && !singleTask && suggestions.length > 0 && (
        <Box flexDirection="column" marginLeft={2} marginBottom={0}>
          {suggestions.map((suggestion, index) => (
            <Box key={`${suggestion.kind}-${suggestion.label}-${index}`}>
              <Text color={index === selectedSuggestion ? '#ffffff' : '#4a9eff'}>
                {index === selectedSuggestion ? '› ' : '  '}
                {suggestion.label}
              </Text>
              <Text dimColor>  {suggestion.desc}</Text>
            </Box>
          ))}
        </Box>
      )}

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
              key={inputVersion}
              value={input}
              onChange={handleChange}
              onSubmit={handleSubmit}
              placeholder=""
            />
          </Box>
          {!input.startsWith('/') && (
            <Box marginLeft={2}>
              <Text dimColor>type / for commands · t toggles trace · exit to quit</Text>
            </Box>
          )}
          {input.startsWith('/') && suggestions.length > 0 && (
            <Box marginLeft={2}>
              <Text dimColor>tab to accept · ↑/↓ to navigate</Text>
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}

function MessageView({ msg, cols }) {
  if (msg.type === 'user') {
    const pad = Math.max(0, cols - msg.text.length - 3);
    return (
      <Box flexDirection="column" marginTop={1} marginBottom={1}>
        <Box>
          <Text backgroundColor="#2a2a3a" color="white"> {msg.text}{' '.repeat(pad)}</Text>
        </Box>
        {msg.files && msg.files.length > 0 && (
          <Box marginLeft={2}>
            {msg.files.map((filePath, index) => {
              const ext = path.extname(filePath).toLowerCase();
              const isImage = ['.png', '.jpg', '.jpeg', '.gif', '.webp'].includes(ext);
              return (
                <Text key={`${filePath}-${index}`} dimColor> {isImage ? 'IMG' : 'FILE'} {path.basename(filePath)}</Text>
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
            <Text color="#4a9eff">OK completed ({msg.iters} {msg.iters === 1 ? 'iteration' : 'iterations'})</Text>
          </Box>
        )}
      </Box>
    );
  }

  if (msg.type === 'error') {
    return (
      <Box flexDirection="column" marginLeft={2} marginTop={1}>
        <Text color="red" wrap="wrap">ERR {msg.text}</Text>
        {msg.iters && (
          <Box marginTop={0}>
            <Text color="redBright">Failed after {msg.iters} {msg.iters === 1 ? 'iteration' : 'iterations'}</Text>
          </Box>
        )}
      </Box>
    );
  }

  return null;
}

function TraceTailView({ entries, cols }) {
  const visible = entries.slice(-Math.max(10, Math.min(28, cols ? Math.floor(cols / 3) : 18)));

  return (
    <Box flexDirection="column" marginLeft={2}>
      <Text color="#4a9eff">Trace Tail</Text>
      {visible.length === 0 ? (
        <Text dimColor>waiting for agent activity...</Text>
      ) : (
        visible.map((entry, index) => (
          <Box key={`${entry.iteration}-${index}`}>
            <Text dimColor>[{String(entry.iteration).padStart(3, ' ')}]</Text>
            <Text> </Text>
            <Text color={
              entry.kind === 'call' ? '#4a9eff' :
              entry.kind === 'error' ? 'red' :
              entry.kind === 'status' ? 'green' :
              entry.kind === 'info' ? 'cyan' :
              'gray'
            }>
              {entry.text}
            </Text>
          </Box>
        ))
      )}
    </Box>
  );
}

function StatusView({ connected, health }) {
  const backendOk = connected && health?.backend_ok !== false;
  const modelOk = Boolean(health?.model_ok);
  const watcherEnabled = Boolean(health?.watcher_enabled);
  const watcherOk = health?.watcher_ok;

  return (
    <Box flexDirection="column" marginLeft={2}>
      <Box>
        <Text color={backendOk ? 'green' : 'red'}>backend {backendOk ? 'ready' : 'down'}</Text>
        <Text dimColor> · </Text>
        <Text color={modelOk ? 'green' : 'red'}>
          wave {modelOk ? 'ready' : 'down'}
        </Text>
        {health?.model_name && (
          <>
            <Text dimColor> · </Text>
            <Text dimColor>{health.model_name}</Text>
          </>
        )}
        {watcherEnabled && (
          <>
            <Text dimColor> · </Text>
            <Text color={watcherOk ? 'green' : 'yellow'}>
              bee {watcherOk ? 'ready' : 'fallback'}
            </Text>
          </>
        )}
      </Box>

      {health?.model_endpoint && (
        <Box>
          <Text dimColor>wave endpoint: {health.model_endpoint}</Text>
        </Box>
      )}

      {!modelOk && health?.model_error && (
        <Box>
          <Text color="red" wrap="wrap">wave error: {health.model_error}</Text>
        </Box>
      )}

      {watcherEnabled && health?.watcher_endpoint && !watcherOk && (
        <Box>
          <Text dimColor>bee endpoint: {health.watcher_endpoint}</Text>
          {health?.watcher_error ? (
            <>
              <Text dimColor> · </Text>
              <Text color="yellow" wrap="wrap">{health.watcher_error}</Text>
            </>
          ) : null}
        </Box>
      )}

      {!health && (
        <Box>
          <Text dimColor>checking local model status...</Text>
        </Box>
      )}
    </Box>
  );
}

const args = process.argv.slice(2);
let task = null;
let wsPort = 3000;
const attachFiles = [];

for (let i = 0; i < args.length; i++) {
  if (args[i] === '--task' && args[i + 1]) task = args[++i];
  if (args[i] === '--port' && args[i + 1]) wsPort = parseInt(args[++i], 10);
  if (args[i] === '--attach' && args[i + 1]) attachFiles.push(args[++i]);
}

if (task && attachFiles.length > 0) {
  for (const filePath of attachFiles) {
    task += `\n[Attached file: ${filePath}]`;
  }
}

const serverUrl = `ws://localhost:${wsPort}/ws`;
render(<App serverUrl={serverUrl} singleTask={task} />);
