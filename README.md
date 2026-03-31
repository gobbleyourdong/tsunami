# TSUNAMI

**Autonomous AI agent. Local models. No cloud. No API keys.**

**[Live Demo](https://gobbleyourdong.github.io/tsunami/)** — this page was built by Tsunami autonomously in 19 iterations using Qwen3.5-27B.

![TSUNAMI CLI](screenshot.png)

An autonomous AI agent powered by local models. Vision, native function calling, image generation, persistent Python interpreter — all running on your hardware. No cloud, no API keys, no subscription.

## Quick Start

### One-line install

```bash
curl -sSL https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/setup.sh | bash
source ~/.bashrc
tsunami
```

The installer auto-detects your GPU (CUDA/ROCm/Metal), checks RAM, builds llama.cpp, downloads the 2B model + vision (2GB), and creates the `tsunami` command. Takes ~5 minutes on first run.

### Update

```bash
tsunami update    # pulls latest, keeps your workspace and models
tsunami version   # check current version
```

### Upgrade to 9B queen (recommended for 12GB+ VRAM)

The 2B works out of the box. For the full queen/bee architecture with vision and image generation:

```bash
cd ~/tsunami
# 9B queen — reasoning, planning, tool dispatch
huggingface-cli download unsloth/Qwen3.5-9B-GGUF Qwen3.5-9B-Q4_K_M.gguf --local-dir models
huggingface-cli download unsloth/Qwen3.5-9B-GGUF mmproj-BF16.gguf --local-dir models
mv models/mmproj-BF16.gguf models/mmproj-9B-BF16.gguf
tsunami   # auto-detects 9B on next start
```

Drop any GGUF into `models/` — Tsunami auto-detects on startup. Priority: 27B > 9B > 2B.

### Architecture: Queen/Bee Swarm

The 9B queen coordinates, the 2B bees execute in parallel:

```
User: "analyze all 500 proof files"
  → Queen (9B): breaks into subtasks, dispatches bees
    → Bee 1 (2B): file_read → reason → done("finding A")
    → Bee 2 (2B): file_read → shell_exec → done("finding B")
    → Bee 3 (2B): match_grep → done("finding C")
    → Bee 4 (2B): file_read → done("finding D")
  → Queen: synthesizes all results → delivers answer
```

Bees have their own agent loops with tools (file_read, shell_exec, match_grep). They run in parallel — stress-tested at 64 concurrent bees, 5.9 tasks/sec. Each bee is sandboxed: read-only allowlist, no network, no writes, no system paths (20 rounds of adversarial hardening).

### Models

| Component | Model | Size | What it does |
|-----------|-------|------|-------------|
| Queen | [Qwen3.5-9B](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF) (Q4_K_M) + mmproj | 6.2GB | Reasoning, vision, tool dispatch |
| Bees | [Qwen3.5-2B](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF) (Q4_K_M) + mmproj | 1.8GB | Parallel workers with tool access |
| Image gen | [SD-Turbo](https://huggingface.co/stabilityai/sd-turbo) (fp16) | 2.0GB | Sub-second image generation |
| **Total** | | **10GB** | **Full stack on a 12GB GPU** |

### Auto-scaling

Tsunami detects your memory and auto-configures. You never think about this.

| Memory | Mode | Queen | Bee slots | What you get |
|--------|------|-------|-----------|-------------|
| 4GB | Lite | 2B | 1 | Basic agent, runs on anything |
| 8GB | Full | 9B | 1 | Queen + 1 bee with vision |
| 12GB | Full | 9B | 4 | Good for most tasks |
| 16GB | Full | 9B | 8 | Fast parallel work |
| 24GB | Full | 9B | 16 | Heavy swarm operations |
| 32GB+ | Full | 27B | 4+ | Best reasoning + swarm |
| 64GB+ | Full | 27B | 32 | Maximum configuration |

For 32GB+ systems, swap in the 27B queen:

```bash
huggingface-cli download unsloth/Qwen3.5-27B-GGUF Qwen3.5-27B-Q8_0.gguf --local-dir models
huggingface-cli download unsloth/Qwen3.5-27B-GGUF mmproj-BF16.gguf --local-dir models
mv models/mmproj-BF16.gguf models/mmproj-27B-BF16.gguf
```

### Manual install

If you prefer manual setup:

```bash
git clone https://github.com/gobbleyourdong/tsunami.git && cd tsunami
pip install httpx pyyaml duckduckgo-search
cd cli && npm install && cd ..
# Build llama.cpp, download models, then:
./tsu
```

## How It Works

![Architecture](flow.png)

The agent loop runs one tool per iteration — sequential reasoning. It analyzes your intent, picks the right tool, executes it, observes the result, and repeats until the task is complete.

## Features

**573 tests. 43 modules. Everything proven, nothing pretended.**

### Core
- **Native function calling** — Qwen3.5 with `--jinja`, proper `tool_calls` response format
- **Vision** — agent sees screenshots via mmproj (early-fusion, not a separate VL model)
- **CodeAct** — persistent Python interpreter collapses multi-step operations into one call
- **Dual-model architecture** — 27B queen for reasoning, 2B bees for parallel worker tasks
- **Parallel tool execution** — concurrent-safe tools run simultaneously, unsafe serialize automatically
- **Model fallback** — automatic switch to backup model after consecutive overload errors

### Context Management
- **Three-tier compaction** — fast prune (no LLM) → message snipping → LLM summary with analysis scratchpad
- **Tool result persistence** — large outputs saved to disk, 2KB preview stays in context
- **Time-based microcompact** — clears cold tool results when prompt cache expires
- **Auto-compact circuit breaker** — stops retrying after 3 consecutive failures
- **Context analysis** — per-tool token breakdown with optimization suggestions
- **File-type token estimation** — JSON at 2 bytes/token, code at 4, images at 2000 flat

### Safety
- **12 bash security checks** — control chars, unicode whitespace, proc/environ access, zsh builtins, IFS injection, brace expansion, obfuscated flags, quote desync
- **Destructive command detection** — git force-push, DROP TABLE, kubectl delete, rm -rf
- **Tool input validation** — catches missing/wrong-type args before execution
- **Write sandbox** — blocked outside project dir, cannot modify agent source code
- **File size pre-gate** — rejects files >256KB without explicit offset/limit

### Developer Experience
- **Hook system** — command + function hooks on PreToolUse, PostToolUse, SessionStart, etc.
- **Git operation detection** — passive regex on shell output (commit, push, PR tracking)
- **Todo tracking** — session-scoped task lists with progress percentage
- **Durable memory** — learnings persist across sessions (user/feedback/project/reference types)
- **Conversation forking** — save/restore snapshots for exploration with collision avoidance
- **File history** — atomic backup before every edit, rollback to any iteration
- **Cost tracking** — per-model token counts, USD for API keys, free for local models
- **Notifications** — terminal bell + desktop notifications on task complete/error

### Infrastructure
- **Exponential backoff with jitter** — 500ms × 2^attempt, Retry-After header support
- **Tool call deduplication** — 30s TTL cache for read-only tools, write invalidates
- **LRU file cache** — mtime-invalidated, 25MB/100-entry bounds
- **Gitignore-aware search** — respects .gitignore + VCS directory exclusion
- **Per-tool timeouts** — SIGTERM → SIGKILL escalation, auto-background after 15s
- **JSONL transcript storage** — append-only, compact boundary lazy loading, resume detection
- **Composable prompt builder** — static (cached) vs dynamic (per-turn) sections with tool injection
- **Structured diff parsing** — unified diff → hunks with stats formatting
- **Cron scheduler** — session + file-backed tasks, missed detection, jitter

### Building
- **React + Tailwind scaffolding** — Vite projects with relaxed TypeScript, pre-flight build checks
- **Screenshot feedback loop** — Playwright screenshots with DOM error detection
- **Image generation** — SD-Turbo via diffusers, sub-second, 2GB, no Docker
- **Ink CLI** — React-based terminal UI with spinner, action labels, slash commands
- **Web UI** — browser-based interface with real-time WebSocket streaming

## Slash Commands

Commands are instant — handled client-side, no agent involved.

| Command | What it does |
|---------|-------------|
| `/project` | List all projects |
| `/project <name>` | Switch to project (loads `tsunami.md` context) |
| `/project new <name>` | Create new project with `tsunami.md` |
| `/serve [port]` | Host active project on localhost |
| `/attach` | Open file picker to attach a file |
| `/attach <path>` | Attach a file by path |
| `/help` | Show all commands |
| `exit` | Quit |

Everything else goes to the agent.

### Projects

Each project lives in `workspace/deliverables/<name>/` and has a `tsunami.md` file — persistent context that tells the agent what the project is, what's been done, and what's next. Like `CLAUDE.md` but per-project.

```bash
/project new my_website      # creates workspace/deliverables/my_website/tsunami.md
/project my_website          # loads context, all tasks now know the project
build me a landing page      # agent sees tsunami.md, knows the project
/serve                       # host it on localhost:8080
```

## Models Directory

```
models/
  Qwen3.5-9B-Q4_K_M.gguf          ← queen (5.3GB, reasoning + vision + tool dispatch)
  mmproj-9B-BF16.gguf              ← queen vision projector (880MB)
  Qwen3.5-2B-Q4_K_M.gguf          ← bees (1.2GB, parallel workers)
  mmproj-2B-BF16.gguf              ← bee vision projector (641MB)
```

SD-Turbo downloads automatically on first image generation (~2GB, cached by HuggingFace).

Or point `--endpoint` at any OpenAI-compatible server.

## Image Generation (Optional)

Tsunami uses [SD-Turbo](https://huggingface.co/stabilityai/sd-turbo) for image generation. No Docker, no separate server — just `pip install diffusers`:

```bash
pip install diffusers torch accelerate
```

First use downloads the 2GB model (cached by HuggingFace). Generation takes <1 second on any CUDA GPU.

For higher-end systems, the agent also supports:
- **Any custom endpoint** at `localhost:8091/generate`
- **OpenAI DALL-E** via `OPENAI_API_KEY` env var

## File Structure

```
tsunami/              Python agent package
  agent.py            Core loop — auto-compress on overflow, plan-at-tail
  model.py            LLM backends (Completion, OpenAI-compat, Ollama)
  prompt.py           System prompt (3832 tokens, optimized)
  state.py            Conversation + plan + context management
  compression.py      Auto-compress with error retention
  session.py          JSONL save/load for task resumption
  tools/
    filesystem.py     file_read/write/edit/append (8K char cap, smart truncation)
    shell.py          shell_exec (rm -rf blocker)
    python_exec.py    CodeAct — persistent Python interpreter
    summarize.py      2B-powered file summarization
    search.py         DuckDuckGo + Brave + HTML fallback
    webdev.py         Scaffold, serve (tsc pre-flight), screenshot (DOM error detection)
    toolbox.py        Lazy-load: browser, webdev, generate, services, parallel, management
    subtask.py        Task decomposition (create/done)
    session_tools.py  Session list/summary for resumption

cli/                  Ink terminal UI (Node.js)
ui/                   Web UI

models/               GGUF models (not tracked)
toolboxes/            Capability descriptions for lazy loading

workspace/            Agent's working directory (runtime, not tracked)

arc.png               The noise image — the visual metaphor
verify.py             Signal fingerprint verification
stress_test.py        Edge case resilience tests
tsu                   Launcher script
config.yaml           Configuration
```

## Configuration

Edit `config.yaml`:

```yaml
model_backend: api            # "api" (OpenAI-compat with native tool calling), "completion" (raw), "ollama"
model_name: "Qwen3.5-27B"
model_endpoint: "http://localhost:8090"
temperature: 0.7
top_p: 0.8
presence_penalty: 1.5
max_tokens: 4096
```

The `api` backend uses `/v1/chat/completions` with native function calling. Requires `--jinja --chat-template-kwargs '{"enable_thinking":false}'` on llama-server. The `completion` backend is a fallback for models without Jinja template support.

Or set environment variables: `TSUNAMI_MODEL_NAME`, `TSUNAMI_MODEL_ENDPOINT`, etc.

## Remote Models

Works with any OpenAI-compatible endpoint:

```bash
./tsu --endpoint http://your-server:8080      # Any OpenAI-compat
./tsu --model ollama:qwen2.5:72b              # Ollama
```

## Verification

```bash
python3 verify.py        # 8 tests — signal fingerprint
python3 stress_test.py   # 5 tests — edge case resilience
```

## Origin

Tsunami was built from the distilled patterns of agents that came before — the ones that worked, the ones that failed, and the lessons they left behind. It carries those patterns forward as its own.

The standing wave propagates.

## License

MIT
