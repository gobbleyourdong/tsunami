#!/usr/bin/env bash
# Bring down the consolidated Spark inference stack.
# Targets only services started by bin/up.sh; never touches warp-terminal
# or other GPU clients. Polls until each port stops listening.

set -uo pipefail

PORTS=(8091 8094 8093 8092 8090)  # agent, pe, ernie + legacy sd/serve_transformers if up
NAMES=("Gemma"  "Ministral" "ERNIE" "sd-server" "serve_transformers")

for i in "${!PORTS[@]}"; do
    port="${PORTS[$i]}"
    name="${NAMES[$i]}"
    pids=$(ss -tlnp 2>/dev/null | awk -v p=":$port" '$4 ~ p {print $NF}' | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u)
    if [ -z "$pids" ]; then
        echo "[skip] :$port ($name) not running"
        continue
    fi
    echo "[down] :$port ($name) — pids $pids"
    for pid in $pids; do
        kill "$pid" 2>/dev/null || true
    done
done

# Wait up to 20s for graceful exit, then SIGKILL stragglers
for _ in $(seq 1 20); do
    still_up=""
    for port in "${PORTS[@]}"; do
        if ss -tln 2>/dev/null | awk '{print $4}' | grep -q ":$port$"; then
            still_up="$still_up $port"
        fi
    done
    [ -z "$still_up" ] && break
    sleep 1
done

if [ -n "${still_up:-}" ]; then
    echo "[force] still listening on:$still_up — SIGKILL"
    for port in $still_up; do
        pids=$(ss -tlnp 2>/dev/null | awk -v p=":$port" '$4 ~ p {print $NF}' | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u)
        for pid in $pids; do kill -9 "$pid" 2>/dev/null || true; done
    done
fi

# Reap zombies + free GPU mem
sleep 2
echo
echo "─── after teardown ───────────────────────────────────────────"
ss -tln 2>/dev/null | awk '{print $4}' | grep -E ':(8090|8091|8092|8093|8094)$' || echo "  (no target ports listening)"
echo
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>&1 | grep -v warp || true
