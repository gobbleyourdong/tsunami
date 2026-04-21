#!/bin/bash
# crew — overnight 5-instance orchestration launcher
# Spawns Reef, Tide, Kelp, Coral, Current as parallel Claude Code instances
# each with their own plan.md and runtime state dir.

set -euo pipefail

DIR="$(cd "$(dirname "$(realpath "$0")")" && pwd)"
REPO="$(cd "$DIR/../.." && pwd)"
STATE="$HOME/.tsunami/crew"

NAMES=(reef tide kelp coral current shoal)

mkdir -p "$STATE"
for n in "${NAMES[@]}"; do
  mkdir -p "$STATE/$n"
done

cmd="${1:-help}"

spawn_one() {
  local name="$1"
  local plan_path="$DIR/$name/plan.md"
  local log="$STATE/$name/log.$(date +%Y%m%d_%H%M%S).txt"
  local pidfile="$STATE/$name/pid"

  # Guard: already running?
  if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "  $name: already running (pid $(cat "$pidfile")) — skipping"
    return
  fi

  local prompt="You are ${name^} — one of 6 crew instances working the tsunami overnight campaign. Read your plan carefully and execute it. Your plan file: ${plan_path}. Repo root: ${REPO}. Runtime state: ${STATE}/${name}/. Read the plans of the other 5 crew members under ${DIR}/{reef,tide,kelp,coral,current,shoal}/plan.md to understand the coordination. Start with your phase checklist, then enter the bonus long churn infinite loop. Commit and push artifacts as you produce them. Log one-liner per round to ${STATE}/${name}/log.jsonl."

  # Per-instance env: Shoal reads SHOAL_ERNIE_URL (falls back to localhost:8092
  # if unset or unreachable). Operator sets this to a dedicated RunPod GPU
  # endpoint so Shoal doesn't contend with local :8092 interactive flows.
  local env_overrides=""
  case "$name" in
    shoal)
      # Shoal's plan documents the fallback semantics — pass env through
      # and let the agent + generate_image tool handle retry/fallback.
      env_overrides="SHOAL_ERNIE_URL=${SHOAL_ERNIE_URL:-http://localhost:8092}"
      ;;
  esac

  echo "  $name: launching → $log"
  if [ -n "$env_overrides" ]; then
    echo "     env: $env_overrides"
  fi
  env $env_overrides nohup claude -p "$prompt" \
    --permission-mode bypassPermissions \
    --add-dir "$REPO" --add-dir "$STATE/$name" \
    > "$log" 2>&1 &
  echo $! > "$pidfile"
}

case "$cmd" in
  launch|start)
    echo "  Crew overnight launch"
    for n in "${NAMES[@]}"; do
      spawn_one "$n"
    done
    echo "  5 instances spawned. Check status with: $0 status"
    ;;

  status)
    for n in "${NAMES[@]}"; do
      pidfile="$STATE/$n/pid"
      if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        pid=$(cat "$pidfile")
        latest_log=$(ls -t "$STATE/$n"/log.*.txt 2>/dev/null | head -1)
        last_round=""
        if [ -f "$STATE/$n/log.jsonl" ]; then
          last_round=$(tail -1 "$STATE/$n/log.jsonl" 2>/dev/null | head -c 120)
        fi
        echo "  $n: RUNNING (pid $pid) log=$latest_log"
        [ -n "$last_round" ] && echo "     last: $last_round"
      else
        echo "  $n: stopped"
      fi
    done
    ;;

  tail)
    name="${2:-}"
    if [ -z "$name" ]; then
      echo "Usage: $0 tail <reef|tide|kelp|coral|current>"
      exit 1
    fi
    latest=$(ls -t "$STATE/$name"/log.*.txt 2>/dev/null | head -1)
    [ -z "$latest" ] && { echo "no log for $name"; exit 1; }
    tail -f "$latest"
    ;;

  stop|kill|down)
    echo "  Crew shutdown"
    for n in "${NAMES[@]}"; do
      pidfile="$STATE/$n/pid"
      if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        kill -TERM "$pid" 2>/dev/null || true
      fi
    done
    sleep 10
    for n in "${NAMES[@]}"; do
      pidfile="$STATE/$n/pid"
      if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        kill -KILL "$pid" 2>/dev/null || true
        rm -f "$pidfile"
      fi
    done
    echo "  All crew stopped"
    ;;

  restart)
    "$0" stop
    sleep 2
    "$0" launch
    ;;

  help|*)
    cat <<EOF
Usage: $0 <command>

Commands:
  launch      Spawn all 6 instances (Reef, Tide, Kelp, Coral, Current, Shoal)
  status      Show which instances are running + last log round
  tail <name> Tail the active log for one instance
  stop        SIGTERM all, grace, SIGKILL stragglers
  restart     Stop + relaunch

Plans: $DIR/{reef,tide,kelp,coral,current,shoal}/plan.md
State: $STATE/{reef,tide,kelp,coral,current,shoal}/
EOF
    ;;
esac
