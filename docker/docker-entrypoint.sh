#!/bin/bash
# TSUNAMI Docker Entrypoint
# Starts llama-server with Gemma 4 E4B, then runs the agent task or interactive mode.
set -e

MODELS_DIR="/app/models"
MODEL="$MODELS_DIR/gemma-4-E4B-it-Q4_K_M.gguf"

if [ ! -f "$MODEL" ]; then
    echo "  ✗ Model not found: $MODEL"
    echo "    Run: curl -fSL -o $MODEL https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf"
    exit 1
fi

# Start Gemma 4 E4B server (single model for all roles — port 8090)
echo "  Starting Gemma 4 E4B server..."
llama-server \
    --model "$MODEL" \
    --port 8090 \
    --host 0.0.0.0 \
    --ctx-size 16384 \
    --parallel 2 \
    --threads $(nproc) \
    --no-mmap \
    > /tmp/llm.log 2>&1 &
LLM_PID=$!

# Wait for model to load
echo "  Waiting for model to load..."
for i in $(seq 1 120); do
    if curl -s http://localhost:8090/health > /dev/null 2>&1; then
        echo "  ✓ Gemma 4 E4B ready (port 8090)"
        break
    fi
    sleep 1
done

# Start the serve daemon in background (persistent like ComfyUI)
python3 -m tsunami.serve_daemon --workspace /app/workspace --port 9876 &

# Run the task or interactive mode
if [ $# -gt 0 ]; then
    # Task mode: run the prompt
    echo ""
    echo "  ════════════════════════════════"
    echo "  Running: $*"
    echo "  ════════════════════════════════"
    echo ""
    python3 -m tsunami.cli --config /app/config.docker.yaml --task "$*"
    echo ""
    echo "  → Output served at http://localhost:9876"
    echo "  → Press Ctrl+C to stop"
    # Keep container alive so user can browse the output
    wait
else
    # Interactive mode
    python3 -m tsunami.cli --config /app/config.docker.yaml
fi
