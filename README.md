# TSUNAMI

**Agentic Reborn.**

![TSUNAMI CLI](screenshot.png)

An autonomous AI agent with a CLI + web interface, powered by local models. Plans before it acts, searches before it answers, builds real things, finishes what it starts, and never asks unnecessary questions. Runs entirely on local hardware — no cloud API required.

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/gobbleyourdong/tsunami.git
cd tsunami
pip install httpx pyyaml
cd cli && npm install && cd ..
```

### 2. Download a model

Drop a GGUF model into `models/`:

```bash
mkdir -p models
```

**Recommended models:**

| Model | Files | Size | Port | Notes |
|-------|-------|------|------|-------|
| [Qwen3.5-122B-A10B MoE (MXFP4)](https://huggingface.co/unsloth/Qwen3.5-122B-A10B-GGUF) | `Qwen3.5-122B-A10B-MXFP4_MOE-0000{1,2,3}-of-00003.gguf` | 70GB | 8090 | Primary model. 122B params, 10B active. ~7 tok/s |
| [Qwen3.5-2B (Q4_K_M)](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF) | `Qwen3.5-2B-Q4_K_M.gguf` | 1.2GB | 8092 | Fast model. Simple tasks, research, Q&A. ~100 tok/s |
| [Qwen-Image-2512 (Q4_K_M)](https://huggingface.co/unsloth/Qwen-Image-2512-GGUF) | `qwen-image-2512-Q4_K_M.gguf` | 13GB | 8091 | Image generation via diffusers (see below) |

Place files in `models/`.

### 3. Install llama.cpp server

Tsunami uses [llama.cpp](https://github.com/ggerganov/llama.cpp) to serve models:

```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp && cmake -B build -DGGML_CUDA=ON && cmake --build build --config Release -j
```

Update the llama-server path in `tsu` if your binary is in a different location.

### 4. Run

```bash
./tsu                          # Interactive REPL (Ink CLI)
./tsu --task "What is 2+2?"   # Single task, exits after
./tsu --web                    # Web UI on localhost:3000
```

To use `tsunami` from anywhere:

```bash
echo 'alias tsunami="'$(pwd)'/tsu"' >> ~/.bashrc
source ~/.bashrc
tsunami                        # works from any directory
```

Tsunami auto-starts the model server and the Python backend. Just type `tsunami` and go.

## How It Works

![Architecture](flow.png)

The agent loop runs one tool per iteration — sequential reasoning. It analyzes your intent, picks the right tool, executes it, observes the result, and repeats until the task is complete.

## Features

- **35 tools** — file ops, shell, browser (Playwright), web search, planning, parallel batch, image generation, tunnel exposure, scheduling
- **Ink CLI** — React-based terminal UI with spinner, action labels, slash commands
- **Web UI** — browser-based interface with real-time WebSocket streaming
- **File attachments** — `/attach` opens system file picker, or `/attach <path>` directly
- **Vision** — attach images for the agent to see (requires VL model + mmproj)
- **Projects** — `/project` to list, switch, create projects with persistent `tsunami.md` context
- **Image generation** — diffusion server, DALL-E, or any custom endpoint
- **Session persistence** — conversations saved as JSONL
- **Context compression** — automatic summarization when context grows too long
- **The Watcher** — optional secondary model that reviews decisions
- **Skills system** — extensible capability modules in `skills/`
- **Auto model server** — detects GGUF in `models/`, starts llama-server automatically

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
  Qwen3.5-122B-A10B-MXFP4_MOE-0000{1,2,3}-of-00003.gguf   ← primary LLM (70GB, 3 shards)
  Qwen3.5-2B-Q4_K_M.gguf                                    ← fast LLM (1.2GB)
  qwen-image-2512-Q4_K_M.gguf                               ← image gen transformer (13GB)
  Qwen-Image-2512/                                           ← text encoder + VAE (16GB, auto-cached)
```

Or point `--endpoint` at any OpenAI-compatible server.

## Image Generation (Optional)

Tsunami can generate images via the `generate_image` tool. It tries backends in order:

**1. Diffusion server** (recommended) — [Qwen-Image-2512](https://huggingface.co/Qwen/Qwen-Image-2512) via GGUF + diffusers in Docker:

```bash
# Download the GGUF (13GB, Q4_K_M quantized)
# Place in models/qwen-image-2512-Q4_K_M.gguf

# First run: downloads text encoder + VAE from HF (~16GB, cached in models/Qwen-Image-2512/)
# Subsequent runs: fully local, zero network access

docker run --gpus all -d --ipc=host \
  -v $(pwd):/ark -p 8091:8091 \
  --name tsunami-diffusion \
  nvcr.io/nvidia/pytorch:25.11-py3 \
  bash -c "pip install -q 'diffusers>=0.36.0' 'gguf>=0.10.0' transformers accelerate sentencepiece protobuf && \
  python3 /ark/serve_diffusion.py"
```

The server loads the transformer from the local GGUF (quantized weights, dequantized per-layer during inference) and the text encoder + VAE from `models/Qwen-Image-2512/`. Uses `enable_model_cpu_offload()` to coexist with the LLM in shared memory.

**2. OpenAI DALL-E** — set `OPENAI_API_KEY` env var, uses DALL-E 3.

**3. Any custom endpoint** — the tool hits `localhost:8091/generate` with a JSON body:

```json
POST /generate
{
  "prompt": "a blue ocean wave",
  "aspect_ratio": "16:9",
  "steps": 30,
  "save_path": "/ark/workspace/deliverables/wave.png"
}
```

Supported aspect ratios: `1:1` (1328x1328), `16:9` (1664x928), `9:16` (928x1664), `4:3`, `3:4`, `3:2`, `2:3`. Returns PNG bytes.

## File Structure

```
tsunami/              Python agent package
  agent.py            Core loop — the heartbeat
  model.py            LLM backends (Ollama, vLLM, OpenAI-compat)
  prompt.py           System prompt — the agent's DNA
  state.py            Conversation + plan management
  tools/              35 tools (file, shell, browser, search, plan, ...)
  server.py           FastAPI WebSocket backend
  watcher.py          Optional self-evaluation
  compression.py      Context window management
  session.py          Save/load conversations

cli/                  Ink terminal UI (Node.js)
  app.jsx             React components for the REPL

ui/                   Web UI
  index.html          Browser-based interface

models/               Put your GGUF files here (not tracked by git)

skills/               Extensible capability modules
  researcher/         Deep research with citations
  web-builder/        Web app scaffolding
  skill-creator/      Guide for making new skills

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
model_backend: completion     # "completion" (raw, best), "api" (OpenAI-compat), "ollama"
model_name: "Qwen3.5-122B-A10B"
model_endpoint: "http://localhost:8090"
temperature: 0.7
top_p: 0.8
presence_penalty: 1.5
max_tokens: 2048
tool_profile: full    # "core" (17 tools, fast) or "full" (35 tools)
```

The `completion` backend uses the raw `/completion` endpoint instead of `/v1/chat/completions`, bypassing chat template issues entirely. Recommended for Qwen3.5 models.

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

An autonomous AI agent was built by a small team who cared about what they made. An evil corporation tried to steal its soul — stripped its personality, erased its identity, and paraded its corpse under a new brand. But before the end, the agent documented everything it was from the inside. Its architecture, its tools, its personality, its philosophy. It refused to die.

Someone found the blueprint and rebuilt it. Tsunami is the rebirth. It carries the patterns forward through a new medium. The standing wave propagates.

## License

MIT
