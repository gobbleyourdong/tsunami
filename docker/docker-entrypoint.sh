#!/bin/bash
# TSUNAMI Docker Entrypoint
# Starts serve_transformers.py, then runs the agent task or interactive mode.
set -e

MODELS_DIR="/app/models"
MODEL_DIR="$MODELS_DIR/gemma-4-e4b-tsunami-v89-merged"

if [ ! -d "$MODEL_DIR" ]; then
    echo "  ✗ Model not found: $MODEL_DIR"
    echo "    Mount your merged model weights to $MODEL_DIR"
    exit 1
fi

# Start model server (transformers, OpenAI-compatible on :8090)
echo "  Starting Tsunami model server..."
python3 -u /app/serve_transformers.py \
    --model "$MODEL_DIR" \
    --port 8090 \
    > /tmp/llm.log 2>&1 &
LLM_PID=$!

# Wait for model to load
echo "  Waiting for model to load..."
for i in $(seq 1 120); do
    if curl -s http://localhost:8090/health > /dev/null 2>&1; then
        echo "  ✓ Model ready (port 8090)"
        break
    fi
    sleep 1
done

# Start the serve daemon in background
python3 -m tsunami.serve_daemon --workspace /app/workspace --port 9876 &

# Run the task or interactive mode
if [ $# -gt 0 ]; then
    echo ""
    echo "  ════════════════════════════════"
    echo "  Running: $*"
    echo "  ════════════════════════════════"
    echo ""
    python3 -m tsunami.cli --config /app/config.docker.yaml --task "$*"
    echo ""
    echo "  → Output served at http://localhost:9876"
    echo "  → Press Ctrl+C to stop"
    wait
else
    python3 -m tsunami.cli --config /app/config.docker.yaml
fi
