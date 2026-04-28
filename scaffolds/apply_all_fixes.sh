#!/usr/bin/env bash
# apply_all_fixes.sh — applies all 6 verified fixes from the ASSET_PIPELINE
# verification campaign in one shot.
#
# Run from ark/ (the repo root). Idempotent: safe to re-run; each fix
# detects its own already-applied state and is no-op when so.
#
# Source of truth: ASSET_PIPELINE_SURVEY.md §"Verified-ready-to-apply
# fixes" (iter 64 bundle-verified). Operator can audit each artifact:
#   scaffolds/engine_readme_correction.diff       (engine README TL;DR)
#   scaffolds/config_generator_fix.diff           (parser + README)
#   scaffolds/gamedev_action_adventure_fix.diff   (schema sync, 4 files)
#   scaffolds/electron_app_fix.diff               (App.tsx type casts)
#   scaffolds/cli_readmes_test_section_fix.diff   (remove stale Test sections)
#   scaffolds/engine_v2_scope_fix.diff            (drop JRPG+Racing from out-of-scope)
#   scaffolds/engine_subsystem_table_fix.diff     (add 5 missing rows to subsystem table)
#   scaffolds/small_drift_fix.diff                (license ISC→Unlicense; Qwen→Llama example)
#   scaffolds/game_readme_create.diff             (creates scaffolds/game/README.md)
#   scaffolds/common_deferred_banner.diff         (DEFERRED banner on _common/README.md)
#   scaffolds/css_import_order_fix.diff           (silence @import-order warning in react-app CSS)
#   scaffolds/inheriting_scaffolds_fix.sh         (auth-app + ai-app)
#   scaffolds/chrome_extension_fix.sh             (3 PNG icons via PIL)
#
# Net impact: catalog moves from 34/42 (81%) PASS → 40/42 (~95%) PASS.
# Remaining 2 (gamedev/cross/platform_fighter, engine standalone tests)
# are out-of-scope for this bundle — they need creative work or
# documented as by-design.

set -euo pipefail

if [ ! -d "scaffolds/engine" ]; then
  echo "ERROR: scaffolds/engine not found — run from ark/ (repo root)" >&2
  exit 1
fi

echo "=== applying 11 unified-diff patches ==="
for diff in engine_readme_correction.diff config_generator_fix.diff \
            gamedev_action_adventure_fix.diff electron_app_fix.diff \
            cli_readmes_test_section_fix.diff engine_v2_scope_fix.diff \
            engine_subsystem_table_fix.diff small_drift_fix.diff \
            game_readme_create.diff common_deferred_banner.diff \
            css_import_order_fix.diff; do
  if patch --dry-run --silent -p1 < "scaffolds/$diff" 2>/dev/null; then
    echo "  → applying $diff"
    patch -p1 < "scaffolds/$diff" 2>&1 | grep -E '^(patching|Hunk)' || true
  elif patch -R --dry-run --silent -p1 < "scaffolds/$diff" 2>/dev/null; then
    echo "  ✓ $diff already applied (skip)"
  else
    echo "  ! $diff failed dry-run — context drift; needs manual review" >&2
  fi
done

echo
echo "=== running 2 shell-script fixes ==="
cd scaffolds
./inheriting_scaffolds_fix.sh
./chrome_extension_fix.sh

echo
echo "=== Done. Verify with cold-build of a previously-broken scaffold:"
echo "    cd scaffolds/auth-app && npm install && npm run build"
echo
echo "  Or run all 6 cold-tests from /tmp to confirm catalog impact."
