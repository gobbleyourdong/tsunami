# TSUNAMI — Containerized Autonomous Agent
# Works on Mac (Apple Silicon + Intel), Linux, Windows (WSL2)
#
# Build:  docker build -t tsunami .
# Run:    docker run -p 9876:9876 -p 8090:8090 tsunami "build me a calculator"
# UI:     open http://localhost:9876 after it builds something
#
# With GPU (NVIDIA):
#   docker run --gpus all -p 9876:9876 -p 8090:8090 tsunami "build me a game"
#
# Model: Gemma 4 E4B Q4_K_M (5GB) — single model for all roles
#
# Persist builds across runs:
#   docker run -v tsunami-workspace:/app/workspace -p 9876:9876 tsunami "build tetris"

FROM node:22-slim AS base

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    git curl cmake build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Build llama.cpp from source (CPU by default, CUDA if available) ---
RUN git clone --depth 1 https://github.com/ggerganov/llama.cpp /tmp/llama.cpp \
    && cd /tmp/llama.cpp \
    && cmake -B build -DGGML_NATIVE=OFF -DGGML_AVX2=OFF -DGGML_FMA=OFF \
    && cmake --build build --config Release -j$(nproc) --target llama-server \
    && cp build/bin/llama-server /usr/local/bin/llama-server \
    && rm -rf /tmp/llama.cpp

# --- Python deps ---
COPY requirements.txt* ./
RUN python3 -m pip install --break-system-packages --no-cache-dir \
    httpx pyyaml ddgs pillow primp websockets \
    && python3 -m pip install --break-system-packages --no-cache-dir playwright \
    && python3 -m playwright install --with-deps chromium 2>/dev/null || true

# --- Copy source ---
COPY . /app/

# --- Download model at build time (cached in image layer) ---
RUN mkdir -p /app/models \
    && echo "Downloading Gemma 4 E4B model (5GB)..." \
    && curl -fSL -o /app/models/gemma-4-E4B-it-Q4_K_M.gguf \
       "https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf"

# --- Workspace volume ---
RUN mkdir -p /app/workspace/deliverables

# Ports: llm(8090) serve(9876) ws-bridge(3002)
EXPOSE 8090 9876 3002

# --- Entrypoint: start everything and run the task ---
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
