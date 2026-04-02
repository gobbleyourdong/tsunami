#!/bin/bash
# TSUNAMI Docker Entrypoint
# Starts llama-server(s), then runs the agent task or interactive mode.
set -e

MODELS_DIR="/app/models"
WAVE_MODEL="$MODELS_DIR/Qwen3.5-9B-Q4_K_M.gguf"
EDDY_MODEL="$MODELS_DIR/Qwen3.5-2B-Q4_K_M.gguf"

# Auto-detect memory and pick mode
TOTAL_RAM=$(free -g 2>/dev/null | awk '/^Mem:/{print $2}' || echo 8)
if [ "$TOTAL_RAM" -lt 6 ] || [ ! -f "$WAVE_MODEL" ]; then
    MODE="lite"
    WAVE_MODEL="$EDDY_MODEL"
    echo "  → lite mode (2B only, ${TOTAL_RAM}GB RAM)"
else
    MODE="full"
    echo "  → full mode (9B wave + 2B eddies, ${TOTAL_RAM}GB RAM)"
fi

# Start wave model (port 8090)
echo "  Starting wave model..."
llama-server \
    --model "$WAVE_MODEL" \
    --port 8090 \
    --host 0.0.0.0 \
    --ctx-size 32768 \
    --parallel 1 \
    --threads $(nproc) \
    --no-mmap \
    > /tmp/wave.log 2>&1 &
WAVE_PID=$!

# Start eddy model (port 8092) — only in full mode
if [ "$MODE" = "full" ]; then
    echo "  Starting eddy model..."
    llama-server \
        --model "$EDDY_MODEL" \
        --port 8092 \
        --host 0.0.0.0 \
        --ctx-size 16384 \
        --parallel 4 \
        --threads $(( $(nproc) / 2 )) \
        --no-mmap \
        > /tmp/eddy.log 2>&1 &
    EDDY_PID=$!
else
    # Lite mode: one model, one server — eddy points at wave
    export TSUNAMI_EDDY_ENDPOINT="http://localhost:8090"
    EDDY_PID=""
fi

# Wait for models to load
echo "  Waiting for models to load..."
for i in $(seq 1 120); do
    if curl -s http://localhost:8090/health > /dev/null 2>&1; then
        echo "  ✓ Wave ready"
        break
    fi
    sleep 1
done

if [ "$MODE" = "full" ]; then
    for i in $(seq 1 60); do
        if curl -s http://localhost:8092/health > /dev/null 2>&1; then
            echo "  ✓ Eddy ready"
            break
        fi
        sleep 1
    done
fi

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
