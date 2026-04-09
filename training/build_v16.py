#!/usr/bin/env python3
"""Generate v16 training data targeting specific L1-L5 gaps from v14r eval.

Sigma gaps identified:
- Training max=24 tools, avg=5.8. L5 eval avg=54.6 iters.
- Only 16% of v14 has multi-file builds.
- L3: file_read instead of file_edit on errors.
- L4: research gate, plan-first, shell loop break.

v16 = v14 + 200 new targeted examples.
All examples end with message_result. All file tools are path-first.
"""
import json
import random
import re

random.seed(1618)

SYSTEM_TEXT = """You are Tsunami. You are the wave. You build apps by calling tools.

The ocean:
- current: your sense of direction. If uncertain, search first.
- circulation: routing. Low tension=deliver. High tension=search or refuse.
- pressure: sustained uncertainty. 2 failures=search. 4 failures=ask the user.
- eddies: parallel workers. 3+ components=dispatch swell.
- undertow: QA. ALWAYS verify before delivering.
- break: compile. shell_exec build after EVERY file_write.
- reef: error. Read the file, REWRITE with file_write, rebuild.

THE PIPELINE (every build follows this EXACTLY):
1. project_init(name) — scaffold the project
2. file_write(App.tsx) — write COMPLETE code
3. shell_exec("cd deliverables/{name} && npx vite build") — run the break
4. IF ERROR: file_read → file_write (full rewrite) → shell_exec rebuild
5. undertow(dist/index.html) — QA before delivery
6. message_result — land the wave

RESUME/MODIFY (existing project):
1. file_read → 2. file_write/file_edit → 3. shell_exec build → 4. message_result

NEVER skip the break. NEVER deliver without building. One tool call per response. Be brief."""

QUOTE = '<|"|>'

TOOL_SCHEMAS = {
    'file_read': {
        'description': 'Read text content from a file.',
        'properties': {
            'limit': ('INTEGER', 'Max lines to read'),
            'offset': ('INTEGER', 'Line number to start from (0-indexed)'),
            'path': ('STRING', 'Path to the file to read'),
        },
        'required': ['path'],
    },
    'file_write': {
        'description': 'Create or overwrite a file with full content.',
        'properties': {
            'content': ('STRING', 'Full file content'),
            'path': ('STRING', 'Path to write to'),
        },
        'required': ['path', 'content'],
    },
    'file_edit': {
        'description': 'Make targeted modifications to an existing file.',
        'properties': {
            'new_text': ('STRING', 'Replacement text'),
            'old_text': ('STRING', 'Exact text to find and replace'),
            'path': ('STRING', 'Path to the file'),
        },
        'required': ['path', 'old_text', 'new_text'],
    },
    'shell_exec': {
        'description': 'Run a shell command and return its output.',
        'properties': {
            'command': ('STRING', 'Shell command to execute'),
            'timeout': ('INTEGER', 'Timeout in seconds'),
            'workdir': ('STRING', 'Working directory'),
        },
        'required': ['command'],
    },
    'match_glob': {
        'description': 'Find files by name and path patterns.',
        'properties': {
            'directory': ('STRING', 'Directory to search in'),
            'limit': ('INTEGER', 'Max results'),
            'pattern': ('STRING', 'Glob pattern'),
        },
        'required': ['pattern'],
    },
    'message_info': {
        'description': 'Acknowledge, update, or inform the user.',
        'properties': {'text': ('STRING', 'Information to share')},
        'required': ['text'],
    },
    'message_result': {
        'description': 'Deliver final outcome and end the task.',
        'properties': {'text': ('STRING', 'Final result to deliver')},
        'required': [],
    },
    'plan_update': {
        'description': 'Create or revise the task plan.',
        'properties': {
            'goal': ('STRING', 'Desired end state'),
            'phases': ('ARRAY', 'Ordered list of phases'),
        },
        'required': ['goal', 'phases'],
    },
    'project_init': {
        'description': 'Create a project from the scaffold library.',
        'properties': {
            'dependencies': ('ARRAY', 'Extra npm packages'),
            'name': ('STRING', 'Project name'),
        },
        'required': ['name'],
    },
    'search_web': {
        'description': 'Search the web for information.',
        'properties': {
            'num_results': ('INTEGER', 'Number of results'),
            'query': ('STRING', 'Search query'),
            'search_type': ('STRING', 'Type of search'),
        },
        'required': ['query'],
    },
    'undertow': {
        'description': 'Test an HTML file by screenshot, keypresses, clicks.',
        'properties': {
            'expect': ('STRING', 'What the app should look like'),
            'path': ('STRING', 'Path to HTML file'),
        },
        'required': ['path'],
    },
}


def format_declaration(name):
    s = TOOL_SCHEMAS[name]
    desc = s['description']
    props_parts = []
    for pname in sorted(s['properties'].keys()):
        ptype, pdesc = s['properties'][pname]
        items_str = ''
        if ptype == 'ARRAY':
            if pname == 'phases':
                items_str = f'items:{{type:{QUOTE}OBJECT{QUOTE}}},'
            else:
                items_str = f'items:{{type:{QUOTE}STRING{QUOTE}}},'
        props_parts.append(
            f'{pname}:{{description:{QUOTE}{pdesc}{QUOTE},{items_str}type:{QUOTE}{ptype}{QUOTE}}}'
        )
    req_str = ','.join(f'{QUOTE}{r}{QUOTE}' for r in s['required'])
    inner = f'description:{QUOTE}{desc}{QUOTE}'
    if props_parts:
        inner += f',parameters:{{properties:{{{",".join(props_parts)}}}'
        if req_str:
            inner += f',required:[{req_str}]'
        inner += f',type:{QUOTE}OBJECT{QUOTE}}}'
    return f'<|tool>declaration:{name}{{{inner}}}<tool|>'


def format_value(v):
    if isinstance(v, str):
        return f'{QUOTE}{v}{QUOTE}'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        items = []
        for it in v:
            if isinstance(it, dict):
                parts = [f'{k}:{format_value(iv)}' for k, iv in sorted(it.items())]
                items.append('{' + ','.join(parts) + '}')
            else:
                items.append(format_value(it))
        return f'[{",".join(items)}]'
    if isinstance(v, dict):
        parts = [f'{k}:{format_value(iv)}' for k, iv in sorted(v.items())]
        return '{' + ','.join(parts) + '}'
    return f'{QUOTE}{json.dumps(v)}{QUOTE}'


ARG_ORDER = {
    'file_write': ['path', 'content'],
    'file_edit': ['path', 'old_text', 'new_text'],
    'file_read': ['path', 'offset', 'limit'],
    'undertow': ['path', 'expect'],
    'shell_exec': ['command', 'workdir', 'timeout'],
    'project_init': ['name', 'dependencies'],
    'search_web': ['query', 'num_results', 'search_type'],
    'plan_update': ['goal', 'phases'],
    'match_glob': ['pattern', 'directory', 'limit'],
    'message_info': ['text'],
    'message_result': ['text'],
}


def format_tool_call(name, args):
    order = ARG_ORDER.get(name, sorted(args.keys()))
    seen = set()
    ordered_keys = []
    for k in order:
        if k in args:
            ordered_keys.append(k)
            seen.add(k)
    for k in sorted(args.keys()):
        if k not in seen:
            ordered_keys.append(k)
    parts = [f'{k}:{format_value(args[k])}' for k in ordered_keys]
    return f'<|tool_call>call:{name}{{{",".join(parts)}}}<tool_call|>'


def format_tool_response(name, value):
    truncated = value[:500] if value else 'OK'
    return f'<|tool_response>response:{name}{{value:{QUOTE}{truncated}{QUOTE}}}<tool_response|>'


def build_example(user_prompt, turns):
    tools_used = set(n for n, _, _ in turns) | {'file_write', 'shell_exec', 'message_result'}
    tools_used &= set(TOOL_SCHEMAS.keys())
    declarations = [format_declaration(n) for n in sorted(tools_used)]
    parts = [f'<|turn>system\n{SYSTEM_TEXT}']
    parts.extend(declarations)
    parts.append('<turn|>')
    parts.append(f'<|turn>user\n{user_prompt}<turn|>')
    for name, args, response in turns:
        call = format_tool_call(name, args)
        parts.append(f'<|turn>model\n{call}<turn|>')
        resp = format_tool_response(name, response)
        parts.append(f'<|turn>user\n{resp}<turn|>')
    return '\n'.join(parts)


APPS_SIMPLE = [
    ('counter-basic', 'a counter app with plus and minus buttons', [
        ('src/App.tsx', 'import { useState } from "react"\nimport Counter from "./components/Counter"\nimport "./index.css"\n\nexport default function App() {\n  const [count, setCount] = useState(0)\n  return (\n    <div className="app">\n      <h1>Counter</h1>\n      <Counter count={count} onInc={() => setCount(count + 1)} onDec={() => setCount(count - 1)} />\n    </div>\n  )\n}'),
        ('src/components/Counter.tsx', 'export default function Counter({ count, onInc, onDec }: any) {\n  return (\n    <div className="counter">\n      <button onClick={onDec}>-</button>\n      <span className="value">{count}</span>\n      <button onClick={onInc}>+</button>\n    </div>\n  )\n}'),
        ('src/index.css', '.app { text-align: center; padding: 2rem; }\n.counter { display: flex; gap: 1rem; justify-content: center; }\nbutton { padding: 0.5rem 1rem; font-size: 1.5rem; }'),
    ]),
    ('digital-clock', 'a digital clock showing HH:MM:SS', [
        ('src/App.tsx', 'import { useState, useEffect } from "react"\nimport Clock from "./components/Clock"\nimport "./index.css"\n\nexport default function App() {\n  const [now, setNow] = useState(new Date())\n  useEffect(() => {\n    const id = setInterval(() => setNow(new Date()), 1000)\n    return () => clearInterval(id)\n  }, [])\n  return <div className="app"><Clock time={now} /></div>\n}'),
        ('src/components/Clock.tsx', 'export default function Clock({ time }: { time: Date }) {\n  const h = String(time.getHours()).padStart(2, "0")\n  const m = String(time.getMinutes()).padStart(2, "0")\n  const s = String(time.getSeconds()).padStart(2, "0")\n  return <div className="clock">{h}:{m}:{s}</div>\n}'),
        ('src/index.css', '.app { display: flex; justify-content: center; align-items: center; height: 100vh; background: #0b0f19; }\n.clock { font-family: monospace; font-size: 5rem; color: #10f981; }'),
    ]),
    ('todo-list', 'a todo list with add and delete', [
        ('src/App.tsx', 'import { useState } from "react"\nimport TodoInput from "./components/TodoInput"\nimport TodoList from "./components/TodoList"\nimport "./index.css"\n\nexport default function App() {\n  const [todos, setTodos] = useState<string[]>([])\n  const add = (t: string) => setTodos([...todos, t])\n  const del = (i: number) => setTodos(todos.filter((_, idx) => idx !== i))\n  return (\n    <div className="app">\n      <h1>Todos</h1>\n      <TodoInput onAdd={add} />\n      <TodoList todos={todos} onDelete={del} />\n    </div>\n  )\n}'),
        ('src/components/TodoInput.tsx', 'import { useState } from "react"\nexport default function TodoInput({ onAdd }: any) {\n  const [v, setV] = useState("")\n  return (\n    <form onSubmit={e => { e.preventDefault(); if (v) { onAdd(v); setV("") } }}>\n      <input value={v} onChange={e => setV(e.target.value)} />\n      <button type="submit">add</button>\n    </form>\n  )\n}'),
        ('src/components/TodoList.tsx', 'export default function TodoList({ todos, onDelete }: any) {\n  return <ul>{todos.map((t: string, i: number) => <li key={i}>{t}<button onClick={() => onDelete(i)}>x</button></li>)}</ul>\n}'),
        ('src/index.css', '.app { max-width: 480px; margin: 2rem auto; padding: 1rem; }'),
    ]),
    ('color-picker', 'a color picker with hex and RGB display', [
        ('src/App.tsx', 'import { useState } from "react"\nimport Picker from "./components/Picker"\nimport Display from "./components/Display"\nimport "./index.css"\n\nexport default function App() {\n  const [color, setColor] = useState("#ff8800")\n  return <div className="app"><h1>Color Picker</h1><Picker value={color} onChange={setColor} /><Display color={color} /></div>\n}'),
        ('src/components/Picker.tsx', 'export default function Picker({ value, onChange }: any) {\n  return <input type="color" value={value} onChange={e => onChange(e.target.value)} />\n}'),
        ('src/components/Display.tsx', 'export default function Display({ color }: { color: string }) {\n  const r = parseInt(color.slice(1, 3), 16)\n  const g = parseInt(color.slice(3, 5), 16)\n  const b = parseInt(color.slice(5, 7), 16)\n  return <div><div className="swatch" style={{ background: color }} /><div>HEX: {color}</div><div>RGB: {r}, {g}, {b}</div></div>\n}'),
        ('src/index.css', '.app { padding: 2rem; text-align: center; }\n.swatch { width: 100px; height: 100px; margin: 1rem auto; border-radius: 8px; }'),
    ]),
    ('markdown-preview', 'a markdown editor with live preview', [
        ('src/App.tsx', 'import { useState } from "react"\nimport Editor from "./components/Editor"\nimport Preview from "./components/Preview"\nimport "./index.css"\n\nexport default function App() {\n  const [md, setMd] = useState("# Hello")\n  return <div className="app"><Editor value={md} onChange={setMd} /><Preview markdown={md} /></div>\n}'),
        ('src/components/Editor.tsx', 'export default function Editor({ value, onChange }: any) {\n  return <textarea value={value} onChange={e => onChange(e.target.value)} />\n}'),
        ('src/components/Preview.tsx', 'export default function Preview({ markdown }: { markdown: string }) {\n  return <div className="preview">{markdown}</div>\n}'),
        ('src/index.css', '.app { display: grid; grid-template-columns: 1fr 1fr; height: 100vh; }\ntextarea { padding: 1rem; font-family: monospace; }'),
    ]),
    ('quiz-app', 'a multiple choice quiz with score', [
        ('src/App.tsx', 'import { useState } from "react"\nimport Question from "./components/Question"\nimport Score from "./components/Score"\nimport { QUESTIONS } from "./data/questions"\nimport "./index.css"\n\nexport default function App() {\n  const [i, setI] = useState(0)\n  const [score, setScore] = useState(0)\n  if (i >= QUESTIONS.length) return <Score score={score} total={QUESTIONS.length} />\n  return <Question q={QUESTIONS[i]} onAnswer={(c) => { if (c) setScore(score + 1); setI(i + 1) }} />\n}'),
        ('src/components/Question.tsx', 'export default function Question({ q, onAnswer }: any) {\n  return <div><h2>{q.text}</h2>{q.options.map((o: string, i: number) => <button key={i} onClick={() => onAnswer(i === q.correct)}>{o}</button>)}</div>\n}'),
        ('src/components/Score.tsx', 'export default function Score({ score, total }: any) {\n  return <div><h1>Done!</h1><p>{score} / {total}</p></div>\n}'),
        ('src/data/questions.ts', 'export const QUESTIONS = [\n  { text: "What is 2+2?", options: ["3", "4", "5"], correct: 1 },\n  { text: "Capital of France?", options: ["Paris", "Rome"], correct: 0 },\n]'),
        ('src/index.css', '.app { padding: 2rem; text-align: center; }'),
    ]),
    ('stopwatch', 'a stopwatch with start stop reset', [
        ('src/App.tsx', 'import { useState, useRef } from "react"\nimport Display from "./components/Display"\nimport "./index.css"\n\nexport default function App() {\n  const [ms, setMs] = useState(0)\n  const [running, setRunning] = useState(false)\n  const ref = useRef<any>()\n  const start = () => { ref.current = setInterval(() => setMs(m => m + 10), 10); setRunning(true) }\n  const stop = () => { clearInterval(ref.current); setRunning(false) }\n  const reset = () => { stop(); setMs(0) }\n  return <div className="app"><Display ms={ms} /><button onClick={running ? stop : start}>{running ? "stop" : "start"}</button><button onClick={reset}>reset</button></div>\n}'),
        ('src/components/Display.tsx', 'export default function Display({ ms }: { ms: number }) {\n  const s = Math.floor(ms / 1000)\n  const m = Math.floor(s / 60)\n  return <div className="display">{String(m).padStart(2,"0")}:{String(s%60).padStart(2,"0")}</div>\n}'),
        ('src/index.css', '.app { text-align: center; padding: 2rem; }\n.display { font-family: monospace; font-size: 4rem; }'),
    ]),
    ('weather-card', 'a weather card showing temperature and conditions', [
        ('src/App.tsx', 'import Card from "./components/Card"\nimport Icon from "./components/Icon"\nimport "./index.css"\n\nexport default function App() {\n  const data = { temp: 72, condition: "sunny", city: "SF", humidity: 45 }\n  return <div className="app"><Card data={data}><Icon condition={data.condition} /></Card></div>\n}'),
        ('src/components/Card.tsx', 'export default function Card({ data, children }: any) {\n  return <div className="card"><h2>{data.city}</h2>{children}<div className="temp">{data.temp}°F</div></div>\n}'),
        ('src/components/Icon.tsx', 'const icons: any = { sunny: "☀️", cloudy: "☁️", rainy: "🌧️" }\nexport default function Icon({ condition }: any) {\n  return <div>{icons[condition] || "🌤️"}</div>\n}'),
        ('src/index.css', '.app { display: flex; justify-content: center; padding: 3rem; background: #dbe4ff; }\n.card { background: white; padding: 2rem; border-radius: 16px; }'),
    ]),
]

APPS_MEDIUM = [
    ('kanban-board', 'a kanban board with todo in-progress and done columns', [
        'src/App.tsx', 'src/components/Board.tsx', 'src/components/Column.tsx',
        'src/components/Card.tsx', 'src/components/AddCard.tsx',
        'src/hooks/useBoard.ts', 'src/types.ts', 'src/index.css',
    ]),
    ('expense-tracker', 'an expense tracker with categories and totals', [
        'src/App.tsx', 'src/components/ExpenseForm.tsx', 'src/components/ExpenseList.tsx',
        'src/components/CategoryFilter.tsx', 'src/components/MonthlyChart.tsx',
        'src/components/Summary.tsx', 'src/hooks/useExpenses.ts',
        'src/data/categories.ts', 'src/index.css',
    ]),
    ('pomodoro-timer', 'a pomodoro timer with work and break sessions', [
        'src/App.tsx', 'src/components/Timer.tsx', 'src/components/Controls.tsx',
        'src/components/SessionLog.tsx', 'src/hooks/usePomodoro.ts', 'src/index.css',
    ]),
    ('recipe-book', 'a recipe book with search and favorites', [
        'src/App.tsx', 'src/components/RecipeCard.tsx', 'src/components/SearchBar.tsx',
        'src/components/FavoritesList.tsx', 'src/components/RecipeModal.tsx',
        'src/data/recipes.ts', 'src/hooks/useFavorites.ts', 'src/index.css',
    ]),
    ('flashcard-deck', 'a flashcard deck for studying', [
        'src/App.tsx', 'src/components/Deck.tsx', 'src/components/Card.tsx',
        'src/components/Progress.tsx', 'src/data/cards.ts', 'src/index.css',
    ]),
    ('drawing-canvas', 'a drawing canvas with color picker and undo', [
        'src/App.tsx', 'src/components/Canvas.tsx', 'src/components/Toolbar.tsx',
        'src/components/ColorSwatch.tsx', 'src/hooks/useDrawing.ts', 'src/index.css',
    ]),
    ('snake-game', 'a snake game with score and game over', [
        'src/App.tsx', 'src/components/Board.tsx', 'src/components/Score.tsx',
        'src/components/GameOver.tsx', 'src/hooks/useSnake.ts', 'src/index.css',
    ]),
    ('memory-matching', 'a memory matching card game', [
        'src/App.tsx', 'src/components/Board.tsx', 'src/components/Card.tsx',
        'src/components/Stats.tsx', 'src/hooks/useMemory.ts', 'src/index.css',
    ]),
]

APPS_COMPLEX = [
    ('chat-ui', 'a chat interface with rooms, messages, and typing indicator', [
        'src/App.tsx', 'src/components/RoomList.tsx', 'src/components/RoomItem.tsx',
        'src/components/MessageList.tsx', 'src/components/Message.tsx',
        'src/components/MessageInput.tsx', 'src/components/TypingIndicator.tsx',
        'src/components/UserAvatar.tsx', 'src/components/ChatHeader.tsx',
        'src/components/EmojiPicker.tsx', 'src/components/AttachmentPreview.tsx',
        'src/hooks/useChat.ts', 'src/hooks/useRooms.ts', 'src/hooks/useTyping.ts',
        'src/data/mockData.ts', 'src/data/mockUsers.ts', 'src/types.ts',
        'src/utils/format.ts', 'src/index.css',
    ]),
    ('code-editor', 'a code editor with syntax highlighting and file tabs', [
        'src/App.tsx', 'src/components/Editor.tsx', 'src/components/FileTabs.tsx',
        'src/components/Tab.tsx', 'src/components/Toolbar.tsx',
        'src/components/LineNumbers.tsx', 'src/components/StatusBar.tsx',
        'src/components/FileExplorer.tsx', 'src/components/SearchPanel.tsx',
        'src/components/CommandPalette.tsx', 'src/components/Minimap.tsx',
        'src/hooks/useFiles.ts', 'src/hooks/useEditor.ts', 'src/hooks/useHighlight.ts',
        'src/data/sampleFiles.ts', 'src/data/themes.ts', 'src/types.ts',
        'src/utils/tokenize.ts', 'src/index.css',
    ]),
    ('dashboard', 'an admin dashboard with charts, tables, and sidebar nav', [
        'src/App.tsx', 'src/components/Sidebar.tsx', 'src/components/TopBar.tsx',
        'src/components/MetricCard.tsx', 'src/components/LineChart.tsx',
        'src/components/BarChart.tsx', 'src/components/PieChart.tsx',
        'src/components/DataTable.tsx', 'src/components/ActivityFeed.tsx',
        'src/components/UserMenu.tsx', 'src/components/NotificationBell.tsx',
        'src/components/SearchBox.tsx', 'src/hooks/useMetrics.ts',
        'src/hooks/useActivity.ts', 'src/data/mockMetrics.ts',
        'src/data/mockUsers.ts', 'src/types.ts', 'src/utils/format.ts', 'src/index.css',
    ]),
    ('blog-platform', 'a blog platform with posts, comments, and tags', [
        'src/App.tsx', 'src/components/Header.tsx', 'src/components/PostList.tsx',
        'src/components/PostCard.tsx', 'src/components/PostDetail.tsx',
        'src/components/CommentList.tsx', 'src/components/CommentForm.tsx',
        'src/components/TagCloud.tsx', 'src/components/AuthorBio.tsx',
        'src/components/SearchBar.tsx', 'src/components/Pagination.tsx',
        'src/hooks/usePosts.ts', 'src/hooks/useComments.ts',
        'src/data/mockPosts.ts', 'src/data/mockAuthors.ts', 'src/types.ts',
        'src/utils/slug.ts', 'src/index.css',
    ]),
    ('music-player', 'a music player with playlist, controls, and visualizer', [
        'src/App.tsx', 'src/components/Player.tsx', 'src/components/Playlist.tsx',
        'src/components/Track.tsx', 'src/components/Controls.tsx',
        'src/components/ProgressBar.tsx', 'src/components/Visualizer.tsx',
        'src/components/VolumeSlider.tsx', 'src/components/TrackInfo.tsx',
        'src/components/QueueList.tsx', 'src/components/SearchTracks.tsx',
        'src/hooks/usePlayer.ts', 'src/hooks/useAudioAnalyzer.ts',
        'src/data/tracks.ts', 'src/data/albums.ts', 'src/types.ts',
        'src/utils/format.ts', 'src/index.css',
    ]),
    ('calendar-scheduler', 'a calendar with event scheduling and month view', [
        'src/App.tsx', 'src/components/Calendar.tsx', 'src/components/MonthView.tsx',
        'src/components/WeekView.tsx', 'src/components/DayCell.tsx',
        'src/components/EventList.tsx', 'src/components/EventForm.tsx',
        'src/components/EventModal.tsx', 'src/components/EventCard.tsx',
        'src/components/NavigationBar.tsx', 'src/components/MiniCalendar.tsx',
        'src/hooks/useEvents.ts', 'src/hooks/useCalendar.ts',
        'src/data/mockEvents.ts', 'src/data/calendars.ts',
        'src/types.ts', 'src/utils/dateFormat.ts', 'src/index.css',
    ]),
]


def stub_content(path, app_desc):
    name = path.rsplit('/', 1)[-1].rsplit('.', 1)[0]
    if path.endswith('.tsx'):
        if 'App' in name:
            return f'import "./index.css"\nimport Main from "./components/Main"\n\nexport default function App() {{\n  return <div className="app"><h1>{app_desc}</h1><Main /></div>\n}}'
        return f'export default function {name}() {{\n  return <div className="{name.lower()}">{name}</div>\n}}'
    if path.endswith('.ts'):
        if 'hook' in path.lower() or name.startswith('use'):
            return f'import {{ useState }} from "react"\nexport function {name}() {{\n  const [state, setState] = useState<any>(null)\n  return {{ state, setState }}\n}}'
        if 'type' in name.lower():
            return 'export type Item = { id: string; title: string }\nexport type State = { items: Item[] }'
        if 'data' in path.lower() or 'mock' in name.lower():
            return f'export const {name.upper()} = [\n  {{ id: "1", title: "One" }},\n  {{ id: "2", title: "Two" }},\n]'
        return f'export function {name}() {{ return null }}'
    if path.endswith('.css'):
        return '.app { padding: 2rem; font-family: sans-serif; max-width: 1200px; margin: 0 auto; }\n.card { background: white; border-radius: 8px; padding: 1rem; }'
    return f'// {name}'


BUILD_OK_TEMPLATE = 'vite v6.4.1 building for production...\ntransforming...\n✓ {n} modules transformed.\ndist/index.html                   0.44 kB\ndist/assets/index.css             {css} kB\ndist/assets/index.js            {js} kB\n✓ built in {ms}ms\n[exit code: 0]'

def ok_build(n_modules=33, ms=None):
    if ms is None:
        ms = random.randint(300, 900)
    return BUILD_OK_TEMPLATE.format(n=n_modules, css=round(random.uniform(3, 8), 2), js=round(random.uniform(150, 250), 2), ms=ms)


BUILD_ERR_SYNTAX = 'vite v6.4.1 building for production...\nsrc/App.tsx:{line}:{col} - error TS1005: \',\' expected.\n{code}\n[exit code: 1]'
BUILD_ERR_IMPORT = 'vite v6.4.1 building for production...\nsrc/App.tsx: Failed to resolve import "{mod}". Does the file exist?\n[exit code: 1]'
BUILD_ERR_TYPE = 'vite v6.4.1 building for production...\nsrc/components/{file}:{line}:{col} - error TS2322: Type \'string\' is not assignable to type \'number\'.\n[exit code: 1]'
UNDERTOW_OK = '[undertow] PASS: screenshot captured, app renders correctly'


def stub_read(path):
    return f'// {path}\nimport {{ useState }} from "react"\n\nexport default function Component() {{\n  const [s, setS] = useState(0)\n  return <div>placeholder</div>\n}}\n'


# ============== GENERATORS ==============

def gen_happy_simple():
    name, desc, files = random.choice(APPS_SIMPLE)
    turns = []
    turns.append(('project_init', {'name': name}, f'[project_init] Scaffolded deliverables/{name}'))
    for path, content in files:
        turns.append(('file_write', {'path': f'deliverables/{name}/{path}', 'content': content}, f'[file_write] wrote {len(content)} bytes'))
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, ok_build(33 + len(files) * 2)))
    turns.append(('undertow', {'path': f'deliverables/{name}/dist/index.html', 'expect': f'Working {desc}'}, UNDERTOW_OK))
    turns.append(('message_result', {'text': f'Break clean, undertow clear. Built {desc}. Wave delivered.'}, f'[message_result] done'))
    return f'Build {desc}', turns


def gen_happy_medium():
    name, desc, paths = random.choice(APPS_MEDIUM)
    turns = [('project_init', {'name': name}, f'[project_init] Scaffolded deliverables/{name}')]
    for path in paths:
        content = stub_content(path, desc)
        turns.append(('file_write', {'path': f'deliverables/{name}/{path}', 'content': content}, f'[file_write] wrote {len(content)} bytes'))
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, ok_build(40 + len(paths) * 3)))
    turns.append(('undertow', {'path': f'deliverables/{name}/dist/index.html', 'expect': f'Working {desc}'}, UNDERTOW_OK))
    turns.append(('message_result', {'text': f'Break clean, undertow clear. {desc.capitalize()} built with {len(paths)} files.'}, '[message_result] done'))
    return f'Build {desc}', turns


def gen_happy_complex():
    name, desc, paths = random.choice(APPS_COMPLEX)
    turns = [('project_init', {'name': name}, f'[project_init] Scaffolded deliverables/{name}')]
    for path in paths:
        content = stub_content(path, desc)
        turns.append(('file_write', {'path': f'deliverables/{name}/{path}', 'content': content}, f'[file_write] wrote {len(content)} bytes'))
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, ok_build(60 + len(paths) * 3)))
    turns.append(('undertow', {'path': f'deliverables/{name}/dist/index.html', 'expect': f'Working {desc}'}, UNDERTOW_OK))
    turns.append(('message_result', {'text': f'Full {desc} built across {len(paths)} files. Wave delivered.'}, '[message_result] done'))
    return f'Build {desc}', turns


def gen_fails_then_edit():
    name, desc, files = random.choice(APPS_SIMPLE)
    turns = [('project_init', {'name': name}, f'[project_init] Scaffolded deliverables/{name}')]
    for path, content in files:
        turns.append(('file_write', {'path': f'deliverables/{name}/{path}', 'content': content}, f'[file_write] wrote {len(content)} bytes'))
    fail_type = random.choice(['syntax', 'type', 'import'])
    broken = random.choice([f[0] for f in files if f[0].endswith('.tsx')])
    if fail_type == 'syntax':
        err = BUILD_ERR_SYNTAX.format(line=12, col=18, code='  const [c, setC = useState(0)')
        old, new = 'const [c, setC = useState(0)', 'const [c, setC] = useState(0)'
    elif fail_type == 'import':
        err = BUILD_ERR_IMPORT.format(mod='./components/Missing')
        old, new = 'import Missing from "./components/Missing"\n', ''
    else:
        err = BUILD_ERR_TYPE.format(file=broken.rsplit('/', 1)[-1], line=8, col=12)
        old, new = 'const value: number = "42"', 'const value: number = 42'
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, err))
    turns.append(('file_read', {'path': f'deliverables/{name}/{broken}'}, stub_read(broken)))
    turns.append(('file_edit', {'path': f'deliverables/{name}/{broken}', 'old_text': old, 'new_text': new}, '[file_edit] replaced'))
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, ok_build(35 + len(files) * 2)))
    turns.append(('undertow', {'path': f'deliverables/{name}/dist/index.html', 'expect': f'Working {desc}'}, UNDERTOW_OK))
    turns.append(('message_result', {'text': f'Break clean after fixing {fail_type} error. {desc.capitalize()} delivered.'}, '[message_result] done'))
    return f'Build {desc}', turns


def gen_fails_twice_then_edit():
    name, desc, files = random.choice(APPS_SIMPLE)
    turns = [('project_init', {'name': name}, f'[project_init] Scaffolded deliverables/{name}')]
    for path, content in files:
        turns.append(('file_write', {'path': f'deliverables/{name}/{path}', 'content': content}, f'[file_write] wrote {len(content)} bytes'))
    app_path = [f[0] for f in files if 'App' in f[0]][0]
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'},
                  BUILD_ERR_SYNTAX.format(line=5, col=20, code='  const { count setCount } = useState(0)')))
    turns.append(('file_read', {'path': f'deliverables/{name}/{app_path}'}, stub_read(app_path)))
    turns.append(('file_edit', {'path': f'deliverables/{name}/{app_path}',
                                'old_text': 'const { count setCount }', 'new_text': 'const [count, setCount]'},
                  '[file_edit] fixed syntax'))
    comp = [f[0] for f in files if 'components' in f[0]][0]
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'},
                  BUILD_ERR_TYPE.format(file=comp.rsplit('/', 1)[-1], line=3, col=14)))
    turns.append(('file_read', {'path': f'deliverables/{name}/{comp}'}, stub_read(comp)))
    turns.append(('file_edit', {'path': f'deliverables/{name}/{comp}',
                                'old_text': 'count: string', 'new_text': 'count: number'},
                  '[file_edit] fixed type'))
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, ok_build()))
    turns.append(('undertow', {'path': f'deliverables/{name}/dist/index.html', 'expect': f'Working {desc}'}, UNDERTOW_OK))
    turns.append(('message_result', {'text': f'Two fixes, {desc} delivered.'}, '[message_result] done'))
    return f'Build {desc}', turns


def gen_research_first():
    topics = [
        ('web animation libraries 2026', 'motion framer comparison', 'an animated landing page'),
        ('best react state management', 'zustand redux jotai', 'a state management demo'),
        ('tailwind vs css modules', 'styling react apps', 'a styled card component'),
        ('websocket chat tutorial', 'socket.io native', 'a websocket chat'),
        ('audio playback react', 'useAudio howler tone', 'an audio visualizer'),
        ('web accessibility ARIA', 'screen reader react', 'an accessible form'),
        ('react router v7', 'file based routing', 'a multi-page app'),
    ]
    q1, q2, desc = random.choice(topics)
    name = re.sub(r'[^a-z-]', '', desc.split()[-1].lower()) + '-demo'
    turns = []
    turns.append(('search_web', {'query': q1, 'num_results': 5}, 'Results: 1. Guide... 2. Docs...'))
    turns.append(('search_web', {'query': q2, 'num_results': 5}, 'Results: comparison article...'))
    turns.append(('project_init', {'name': name}, f'[project_init] Scaffolded'))
    n = random.randint(3, 5)
    for i in range(n):
        p = f'deliverables/{name}/src/Component{i}.tsx'
        c = f'export default function Component{i}() {{ return <div>comp {i}</div> }}'
        turns.append(('file_write', {'path': p, 'content': c}, f'[file_write] {len(c)} bytes'))
    app_c = 'import "./index.css"\n' + ''.join(f'import C{i} from "./Component{i}"\n' for i in range(n)) + 'export default function App() { return <div>' + ''.join(f'<C{i}/>' for i in range(n)) + '</div> }'
    turns.append(('file_write', {'path': f'deliverables/{name}/src/App.tsx', 'content': app_c}, '[file_write] App'))
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, ok_build()))
    turns.append(('undertow', {'path': f'deliverables/{name}/dist/index.html', 'expect': f'Working {desc}'}, UNDERTOW_OK))
    turns.append(('message_result', {'text': f'Researched, built {desc}.'}, '[message_result] done'))
    return f'Build {desc} using current best practices', turns


def gen_plan_first():
    name, desc, paths = random.choice(APPS_COMPLEX)
    phases = [
        {'name': 'scaffold', 'goal': 'initialize'},
        {'name': 'core', 'goal': 'write components'},
        {'name': 'data', 'goal': 'wire state'},
        {'name': 'build', 'goal': 'compile'},
        {'name': 'deliver', 'goal': 'QA and result'},
    ]
    turns = [('plan_update', {'goal': f'Build {desc}', 'phases': phases}, '[plan_update] 5 phases')]
    turns.append(('project_init', {'name': name}, f'[project_init] Scaffolded'))
    for path in paths:
        c = stub_content(path, desc)
        turns.append(('file_write', {'path': f'deliverables/{name}/{path}', 'content': c}, f'[file_write] {len(c)} bytes'))
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, ok_build(70)))
    turns.append(('undertow', {'path': f'deliverables/{name}/dist/index.html', 'expect': f'Working {desc}'}, UNDERTOW_OK))
    turns.append(('message_result', {'text': f'Executed plan. {desc} complete.'}, '[message_result] done'))
    return f'Build {desc}. This needs careful planning — multiple components, state management, and testing.', turns


def gen_break_stall():
    name, desc, files = random.choice(APPS_SIMPLE)
    turns = [('project_init', {'name': name}, f'[project_init] Scaffolded')]
    for path, content in files:
        turns.append(('file_write', {'path': f'deliverables/{name}/{path}', 'content': content}, f'[file_write] {len(content)} bytes'))
    err = BUILD_ERR_SYNTAX.format(line=3, col=15, code='  return <div>{children</div>')
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, err))
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, err))
    app_path = [f[0] for f in files if 'App' in f[0]][0]
    turns.append(('file_read', {'path': f'deliverables/{name}/{app_path}'}, stub_read(app_path)))
    turns.append(('file_edit', {'path': f'deliverables/{name}/{app_path}',
                                'old_text': '{children</div>', 'new_text': '{children}</div>'},
                  '[file_edit] closed brace'))
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, ok_build()))
    turns.append(('undertow', {'path': f'deliverables/{name}/dist/index.html', 'expect': f'Working {desc}'}, UNDERTOW_OK))
    turns.append(('message_result', {'text': f'Stall broken by file_edit after 2 build failures. {desc} delivered.'}, '[message_result] done'))
    return f'Build {desc}', turns


def gen_verify_stop():
    name, desc, files = random.choice(APPS_SIMPLE)
    turns = [('project_init', {'name': name}, f'[project_init] Scaffolded')]
    for path, content in files:
        turns.append(('file_write', {'path': f'deliverables/{name}/{path}', 'content': content}, f'[file_write] {len(content)} bytes'))
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, ok_build()))
    turns.append(('undertow', {'path': f'deliverables/{name}/dist/index.html', 'expect': f'Working {desc}'}, UNDERTOW_OK))
    turns.append(('message_result', {'text': f'{desc.capitalize()} built and verified. Delivered.'}, '[message_result] done'))
    return f'Build {desc}', turns


def gen_progressive_complex():
    """Long multi-phase build: plan → scaffold → core files → build → fix → extra files → rebuild → undertow → deliver.
    Targets 22-35 tools. Teaches long-trajectory completion + recovery midway."""
    name, desc, paths = random.choice(APPS_COMPLEX)
    phases = [
        {'name': 'plan', 'goal': 'design component tree'},
        {'name': 'core', 'goal': 'write base components'},
        {'name': 'extend', 'goal': 'add features'},
        {'name': 'build', 'goal': 'compile clean'},
        {'name': 'qa', 'goal': 'verify and deliver'},
    ]
    turns = [('plan_update', {'goal': f'Build {desc}', 'phases': phases}, '[plan_update] 5 phases')]
    turns.append(('project_init', {'name': name}, f'[project_init] Scaffolded deliverables/{name}'))

    # Write first half
    half = len(paths) // 2
    for path in paths[:half]:
        c = stub_content(path, desc)
        turns.append(('file_write', {'path': f'deliverables/{name}/{path}', 'content': c}, f'[file_write] {len(c)} bytes'))

    # Build fails mid-way
    broken = [p for p in paths[:half] if p.endswith('.tsx') and 'App' not in p][0]
    err = BUILD_ERR_TYPE.format(file=broken.rsplit('/', 1)[-1], line=5, col=12)
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, err))
    turns.append(('file_read', {'path': f'deliverables/{name}/{broken}'}, stub_read(broken)))
    turns.append(('file_edit', {'path': f'deliverables/{name}/{broken}',
                                'old_text': 'count: string', 'new_text': 'count: number'},
                  '[file_edit] fixed type'))

    # Second half of writes
    for path in paths[half:]:
        c = stub_content(path, desc)
        turns.append(('file_write', {'path': f'deliverables/{name}/{path}', 'content': c}, f'[file_write] {len(c)} bytes'))

    # Final build + QA + deliver
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, ok_build(80)))
    turns.append(('undertow', {'path': f'deliverables/{name}/dist/index.html', 'expect': f'Working {desc}'}, UNDERTOW_OK))
    turns.append(('message_result', {'text': f'Plan executed in full. {desc.capitalize()} built with recovery across {len(paths)} files. Delivered at deliverables/{name}.'}, '[message_result] done'))
    return f'Build {desc} — this is a complex app, plan carefully.', turns


def gen_triple_recovery():
    """Write → build(fail1) → read → edit → build(fail2) → read → edit → build(fail3) → read → edit → build(ok) → undertow → deliver.
    Teaches multi-round recovery. Length: 22-30."""
    name, desc, files = random.choice(APPS_SIMPLE)
    turns = [('project_init', {'name': name}, f'[project_init] Scaffolded')]
    for path, content in files:
        turns.append(('file_write', {'path': f'deliverables/{name}/{path}', 'content': content}, f'[file_write] {len(content)} bytes'))

    app_path = [f[0] for f in files if 'App' in f[0]][0]
    comps = [f[0] for f in files if 'components' in f[0]]

    # Error 1: syntax in App.tsx
    err1 = BUILD_ERR_SYNTAX.format(line=5, col=20, code='  const { count setCount } = useState(0)')
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, err1))
    turns.append(('file_read', {'path': f'deliverables/{name}/{app_path}'}, stub_read(app_path)))
    turns.append(('file_edit', {'path': f'deliverables/{name}/{app_path}',
                                'old_text': 'const { count setCount }', 'new_text': 'const [count, setCount]'},
                  '[file_edit] fixed destructure'))

    # Error 2: type in first component
    if comps:
        c1 = comps[0]
        err2 = BUILD_ERR_TYPE.format(file=c1.rsplit('/', 1)[-1], line=3, col=14)
        turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, err2))
        turns.append(('file_read', {'path': f'deliverables/{name}/{c1}'}, stub_read(c1)))
        turns.append(('file_edit', {'path': f'deliverables/{name}/{c1}',
                                    'old_text': 'value: string', 'new_text': 'value: number'},
                      '[file_edit] fixed type'))

    # Error 3: import path in App.tsx
    err3 = BUILD_ERR_IMPORT.format(mod='./components/NotExist')
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, err3))
    turns.append(('file_read', {'path': f'deliverables/{name}/{app_path}'}, stub_read(app_path)))
    turns.append(('file_edit', {'path': f'deliverables/{name}/{app_path}',
                                'old_text': 'import NotExist from "./components/NotExist"\n', 'new_text': ''},
                  '[file_edit] removed bad import'))

    # Final build passes
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, ok_build()))
    turns.append(('undertow', {'path': f'deliverables/{name}/dist/index.html', 'expect': f'Working {desc}'}, UNDERTOW_OK))
    turns.append(('message_result', {'text': f'3 fixes (syntax → type → import). {desc.capitalize()} delivered.'}, '[message_result] done'))
    return f'Build {desc}', turns


def gen_long_complex_plain():
    """Pure long happy-path complex build — no recovery, just long. Length: 22-28."""
    name, desc, paths = random.choice(APPS_COMPLEX)
    phases = [
        {'name': 'structure', 'goal': 'components'},
        {'name': 'state', 'goal': 'hooks'},
        {'name': 'data', 'goal': 'mocks'},
        {'name': 'deliver', 'goal': 'verify and ship'},
    ]
    turns = [('plan_update', {'goal': f'Build {desc}', 'phases': phases}, '[plan_update] 4 phases')]
    turns.append(('project_init', {'name': name}, f'[project_init] Scaffolded'))
    for path in paths:
        c = stub_content(path, desc)
        turns.append(('file_write', {'path': f'deliverables/{name}/{path}', 'content': c}, f'[file_write] {len(c)} bytes'))
    turns.append(('shell_exec', {'command': f'cd {name} && npx vite build', 'workdir': 'deliverables'}, ok_build(75)))
    turns.append(('undertow', {'path': f'deliverables/{name}/dist/index.html', 'expect': f'Working {desc}'}, UNDERTOW_OK))
    turns.append(('message_result', {'text': f'{desc.capitalize()} built across {len(paths)} files. Delivered.'}, '[message_result] done'))
    return f'Build {desc}', turns


def main():
    v14_path = 'workspace/training_data/e4b_toolcall_train_v14.jsonl'
    v16_path = 'workspace/training_data/e4b_toolcall_train_v16.jsonl'

    v14 = []
    with open(v14_path) as f:
        for line in f:
            v14.append(json.loads(line))
    print(f"Loaded {len(v14)} v14 examples")

    generators = [
        (gen_happy_simple, 25),
        (gen_happy_medium, 25),
        (gen_happy_complex, 25),
        (gen_fails_then_edit, 30),
        (gen_fails_twice_then_edit, 20),
        (gen_research_first, 20),
        (gen_plan_first, 20),
        (gen_break_stall, 20),
        (gen_verify_stop, 15),
        (gen_progressive_complex, 30),
        (gen_triple_recovery, 25),
        (gen_long_complex_plain, 25),
    ]

    new = []
    for gen, count in generators:
        for _ in range(count):
            user, turns = gen()
            text = build_example(user, turns)
            new.append({'text': text})

    lens = [len(re.findall(r'call:\w+', ex['text'])) for ex in new]
    print(f"Generated {len(new)} new examples")
    print(f"  length: min={min(lens)} max={max(lens)} avg={sum(lens)/len(lens):.1f}")
    print(f"  15+ tools: {sum(1 for l in lens if l >= 15)}/{len(lens)}")
    print(f"  25+ tools: {sum(1 for l in lens if l >= 25)}/{len(lens)}")

    # Validate
    pf_write = total_write = 0
    pf_edit = total_edit = 0
    ends_ok = 0
    for ex in new:
        for m in re.findall(r'<\|tool_call>call:file_write\{(.*?)\}<tool_call\|>', ex['text'], re.DOTALL):
            total_write += 1
            if m.startswith('path:'):
                pf_write += 1
        for m in re.findall(r'<\|tool_call>call:file_edit\{(.*?)\}<tool_call\|>', ex['text'], re.DOTALL):
            total_edit += 1
            if m.startswith('path:'):
                pf_edit += 1
        tools = re.findall(r'call:(\w+)', ex['text'])
        if tools and tools[-1] == 'message_result':
            ends_ok += 1
    print(f"  path-first file_write: {pf_write}/{total_write}")
    print(f"  path-first file_edit:  {pf_edit}/{total_edit}")
    print(f"  ends w/ message_result: {ends_ok}/{len(new)}")

    with open(v16_path, 'w') as f:
        for ex in v14 + new:
            f.write(json.dumps(ex, ensure_ascii=False) + '\n')
    print(f"Wrote {len(v14) + len(new)} examples to {v16_path}")


if __name__ == '__main__':
    main()
