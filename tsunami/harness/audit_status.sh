#!/usr/bin/env bash
# Quick audit snapshot — what's the state of the integration audit?
# Reads all live-round telemetry + runs full test suite + reports.
# Intended: operator runs this before committing, before launching, etc.

set -e
cd "$(dirname "$0")/../.."

echo "═══════════════════════════════════════════════════════════════"
echo "  TSUNAMI INTEGRATION AUDIT — STATUS SNAPSHOT"
echo "  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "═══════════════════════════════════════════════════════════════"
echo ""

echo "▸ TEST SUITES"
total_pass=0; total=0; suites=0
for t in tsunami/tests/test_routing_telemetry.py \
         tsunami/tests/test_doctrine_history.py \
         tsunami/tests/test_game_content.py \
         tsunami/tests/test_quality_telemetry.py \
         tsunami/tests/test_genre_scaffolds.py \
         tsunami/tests/test_gamedev_probe.py \
         tsunami/tests/test_promote_to_catalog.py \
         tsunami/tests/test_morning_report.py \
         tsunami/tests/test_emit_design_normaliser.py \
         tsunami/tests/test_file_write_dict_coercion.py \
         tsunami/tests/test_safe_write_scaffold_aware.py \
         tsunami/tests/test_gamedev_file_read_open.py \
         tsunami/tests/test_gamedev_turn1_override.py \
         tsunami/tests/test_e2e_gamedev_wiring.py \
         tsunami/tests/test_cli_ts_stage_tracking.py \
         tsunami/tests/test_pick_star_telemetry_wires.py \
         tsunami/tests/test_gamedev_delivery_gate_opened.py \
         tsunami/tests/test_scaffold_aware_nudges.py \
         tsunami/tests/test_probe_scan_functions.py \
         tsunami/tests/test_plan_scaffold_schema_alignment.py \
         tsunami/tests/test_error_fixer_design.py \
         tsunami/tests/test_engine_catalog.py \
         tsunami/tests/test_emit_design_project_name_hoist.py \
         tsunami/tests/test_code_write_gate_routing.py \
         tsunami/tests/test_emit_design_shape_normalizer.py \
         tsunami/tests/test_auto_discover_routes.py \
         tsunami/tests/test_tool_registry_smoke.py \
         tsunami/tests/test_phase_machine_transitions.py \
         tsunami/tests/test_server_monitor_smoke.py \
         tsunami/tests/test_worker_exit_classifier.py \
         tsunami/tests/test_progress_scaffold_aware.py; do
    [ -f "$t" ] || continue
    result=$(python3 "$t" 2>&1 | tail -1)
    pass=$(echo "$result" | grep -oP '\d+(?=/)' | head -1)
    of=$(echo "$result" | grep -oP '\d+(?= passed)' | head -1)
    [ -n "$pass" ] && total_pass=$((total_pass + pass))
    [ -n "$of" ] && total=$((total + of))
    suites=$((suites + 1))
done
echo "  $suites suites · $total_pass/$total tests"
echo ""

echo "▸ CORPUS"
essences=$(grep -l "^## Content Catalog" scaffolds/.claude/game_essence/*.md 2>/dev/null | wc -l)
routes=$(python3 -c "import sys; sys.path.insert(0,'.'); from tsunami.game_content import _GAME_SIGNALS; print(len(_GAME_SIGNALS))")
genres=$(ls tsunami/genre_scaffolds/*.md 2>/dev/null | wc -l)
mechanics=$(python3 -c "import sys; sys.path.insert(0,'.'); from tsunami.engine_catalog import KNOWN_MECHANIC_TYPES; print(len(KNOWN_MECHANIC_TYPES))")
echo "  $essences essences with Content Catalog · $routes game-replica routes"
echo "  $genres genre doctrines · $mechanics MechanicType literals"
echo ""

echo "▸ LIVE ROUNDS"
rounds=0; delivered=0; timeout=0; server_down=0; other_err=0
best_adoption_pct="0.00"
best_adoption_run=""
for f in /tmp/live_zelda_round*/runs.jsonl; do
    [ -f "$f" ] || continue
    rounds=$((rounds + 1))
    ex=$(python3 -c "import json,sys; r=json.loads(open('$f').read()); print(r.get('exit_reason','?'))" 2>/dev/null)
    [ "$ex" = "message_result" ] && delivered=$((delivered + 1))
    [ "$ex" = "timeout" ] && timeout=$((timeout + 1))
    [ "$ex" = "error:server_unreachable" ] && server_down=$((server_down + 1))
    case "$ex" in
        message_result|timeout|error:server_unreachable) ;;
        exit_*|error:*) other_err=$((other_err + 1));;
    esac
    # Track best adoption rate across all rounds
    eval_output=$(python3 -c "
import json
r = json.loads(open('$f').read())
rate = r.get('probe',{}).get('content_adoption_rate', 0)
names = r.get('probe',{}).get('content_named_distinct', 0)
rid = r.get('run_id','?')
print(f'{rate:.4f}|{names}|{rid}')
" 2>/dev/null)
    this_rate=$(echo "$eval_output" | cut -d'|' -f1)
    this_rid=$(echo "$eval_output" | cut -d'|' -f3)
    # Compare as floats
    if python3 -c "exit(0 if float('$this_rate') > float('$best_adoption_pct')/100 else 1)" 2>/dev/null; then
        best_adoption_pct=$(python3 -c "print(f'{float(\"$this_rate\")*100:.2f}')")
        best_adoption_run="$this_rid"
    fi
done
summary="  $rounds rounds · $delivered delivered · $timeout timeout"
[ "$server_down" -gt 0 ] && summary="$summary · $server_down server-down"
[ "$other_err" -gt 0 ] && summary="$summary · $other_err other-err"
echo "$summary"
echo "  best adoption: ${best_adoption_pct}% ($best_adoption_run)"
echo ""

echo "▸ SERVER"
python3 -m tsunami.harness.server_monitor 2>&1 | head -1 | sed 's/^/  /'
ls ~/.tsunami/opportunistic_runs/*.pending 2>/dev/null | head -1 | sed 's/^/  pending: /'
echo ""
