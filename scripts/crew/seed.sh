#!/bin/bash
# crew/seed — bootstrap Coral's work queues from known gaps + pain points
# Idempotent: re-running appends only new entries (by id).
# Run once before first launch so the crew has immediate work.

set -euo pipefail

STATE="$HOME/.tsunami/crew/coral"
mkdir -p "$STATE"
cd "$STATE"

append_if_new() {
  local file="$1"; shift
  local id="$1"; shift
  local record="$1"
  touch "$file"
  if ! grep -q "\"id\": \"$id\"" "$file" 2>/dev/null; then
    echo "$record" >> "$file"
    echo "  seeded: $file :: $id"
  fi
}

TS="$(date -u +%Y-%m-%dT%H:%MZ)"

# --- gap_queue.jsonl (scaffolds to build) ---
append_if_new gap_queue.jsonl gap_cli_data_processor_001 \
  "{\"id\": \"gap_cli_data_processor_001\", \"type\": \"gap\", \"target\": \"cli/data-processor\", \"category\": \"scaffolds/cli\", \"priority\": 5, \"added\": \"$TS\", \"note\": \"CLI tool consumes stdin/file input, emits processed data. Python+Click or TS+yargs. Canary: pipe fixture → verify output shape.\"}"
append_if_new gap_queue.jsonl gap_cli_file_converter_001 \
  "{\"id\": \"gap_cli_file_converter_001\", \"type\": \"gap\", \"target\": \"cli/file-converter\", \"category\": \"scaffolds/cli\", \"priority\": 5, \"added\": \"$TS\"}"
append_if_new gap_queue.jsonl gap_cli_config_generator_001 \
  "{\"id\": \"gap_cli_config_generator_001\", \"type\": \"gap\", \"target\": \"cli/config-generator\", \"category\": \"scaffolds/cli\", \"priority\": 4, \"added\": \"$TS\"}"
append_if_new gap_queue.jsonl gap_web_landing_001 \
  "{\"id\": \"gap_web_landing_001\", \"type\": \"gap\", \"target\": \"web/landing\", \"category\": \"scaffolds/web\", \"priority\": 5, \"added\": \"$TS\", \"note\": \"Specialized react-app subtype — hero + features + CTA + footer.\"}"
append_if_new gap_queue.jsonl gap_web_dashboard_001 \
  "{\"id\": \"gap_web_dashboard_001\", \"type\": \"gap\", \"target\": \"web/dashboard\", \"category\": \"scaffolds/web\", \"priority\": 5, \"added\": \"$TS\"}"
append_if_new gap_queue.jsonl gap_web_docs_site_001 \
  "{\"id\": \"gap_web_docs_site_001\", \"type\": \"gap\", \"target\": \"web/docs-site\", \"category\": \"scaffolds/web\", \"priority\": 4, \"added\": \"$TS\"}"
append_if_new gap_queue.jsonl gap_web_ecommerce_001 \
  "{\"id\": \"gap_web_ecommerce_001\", \"type\": \"gap\", \"target\": \"web/ecommerce\", \"category\": \"scaffolds/web\", \"priority\": 4, \"added\": \"$TS\"}"
append_if_new gap_queue.jsonl gap_web_blog_001 \
  "{\"id\": \"gap_web_blog_001\", \"type\": \"gap\", \"target\": \"web/blog\", \"category\": \"scaffolds/web\", \"priority\": 3, \"added\": \"$TS\"}"
append_if_new gap_queue.jsonl gap_mobile_chat_001 \
  "{\"id\": \"gap_mobile_chat_001\", \"type\": \"gap\", \"target\": \"mobile/chat\", \"category\": \"scaffolds/mobile\", \"priority\": 3, \"added\": \"$TS\"}"
append_if_new gap_queue.jsonl gap_mobile_notes_001 \
  "{\"id\": \"gap_mobile_notes_001\", \"type\": \"gap\", \"target\": \"mobile/notes\", \"category\": \"scaffolds/mobile\", \"priority\": 3, \"added\": \"$TS\"}"
append_if_new gap_queue.jsonl gap_gamedev_bullet_hell_rpg_001 \
  "{\"id\": \"gap_gamedev_bullet_hell_rpg_001\", \"type\": \"gap\", \"target\": \"cross/bullet_hell_rpg\", \"category\": \"scaffolds/gamedev/cross\", \"priority\": 2, \"added\": \"$TS\"}"
append_if_new gap_queue.jsonl gap_gamedev_puzzle_platformer_001 \
  "{\"id\": \"gap_gamedev_puzzle_platformer_001\", \"type\": \"gap\", \"target\": \"cross/puzzle_platformer_roguelite\", \"category\": \"scaffolds/gamedev/cross\", \"priority\": 2, \"added\": \"$TS\"}"
append_if_new gap_queue.jsonl gap_gamedev_tactics_action_001 \
  "{\"id\": \"gap_gamedev_tactics_action_001\", \"type\": \"gap\", \"target\": \"cross/tactics_action_adventure\", \"category\": \"scaffolds/gamedev/cross\", \"priority\": 2, \"added\": \"$TS\"}"
append_if_new gap_queue.jsonl gap_training_finetune_001 \
  "{\"id\": \"gap_training_finetune_001\", \"type\": \"gap\", \"target\": \"training/finetune-recipe\", \"category\": \"scaffolds/ml\", \"priority\": 3, \"added\": \"$TS\"}"
append_if_new gap_queue.jsonl gap_infra_docker_compose_001 \
  "{\"id\": \"gap_infra_docker_compose_001\", \"type\": \"gap\", \"target\": \"infra/docker-compose\", \"category\": \"scaffolds/infra\", \"priority\": 3, \"added\": \"$TS\"}"

# --- vertical_gap.jsonl (probes to build) ---
append_if_new vertical_gap.jsonl vgap_cli_probe_001 \
  "{\"id\": \"vgap_cli_probe_001\", \"type\": \"vertical_gap\", \"target\": \"cli\", \"priority\": 5, \"added\": \"$TS\", \"note\": \"Probe for CLI: entry-point + --help returns 0 + fixture input → expected output.\"}"
append_if_new vertical_gap.jsonl vgap_mobile_probe_001 \
  "{\"id\": \"vgap_mobile_probe_001\", \"type\": \"vertical_gap\", \"target\": \"mobile\", \"priority\": 3, \"added\": \"$TS\"}"
append_if_new vertical_gap.jsonl vgap_training_probe_001 \
  "{\"id\": \"vgap_training_probe_001\", \"type\": \"vertical_gap\", \"target\": \"training\", \"priority\": 3, \"added\": \"$TS\"}"
append_if_new vertical_gap.jsonl vgap_infra_probe_001 \
  "{\"id\": \"vgap_infra_probe_001\", \"type\": \"vertical_gap\", \"target\": \"infra\", \"priority\": 3, \"added\": \"$TS\"}"
append_if_new vertical_gap.jsonl vgap_data_pipeline_probe_001 \
  "{\"id\": \"vgap_data_pipeline_probe_001\", \"type\": \"vertical_gap\", \"target\": \"data-pipeline\", \"priority\": 3, \"added\": \"$TS\"}"
append_if_new vertical_gap.jsonl vgap_docs_probe_001 \
  "{\"id\": \"vgap_docs_probe_001\", \"type\": \"vertical_gap\", \"target\": \"docs\", \"priority\": 2, \"added\": \"$TS\"}"

# --- pain_points.jsonl (orchestration fixes to land) ---
append_if_new pain_points.jsonl pain_scaffold_first_read_spiral \
  "{\"id\": \"pain_scaffold_first_read_spiral\", \"type\": \"pain\", \"slug\": \"scaffold_first_read_spiral\", \"severity\": 4, \"count\": 4, \"status\": \"hard_gated_in_9b7b085\", \"evidence\": [\"session_1776736395 ice-cavern Round J\"], \"added\": \"$TS\", \"note\": \"Hard gate landed. Needs replay regression test in tsunami/tests/replays/.\"}"
append_if_new pain_points.jsonl pain_drone_ignores_advisory_system_notes \
  "{\"id\": \"pain_drone_ignores_advisory_system_notes\", \"type\": \"pain\", \"slug\": \"advisory_vs_structural\", \"severity\": 3, \"count\": 3, \"status\": \"open\", \"added\": \"$TS\", \"note\": \"Broad class: drone ignores advisory system_notes. Approach: convert advisories to structural constraints (schema filter, tool hard-gate).\"}"
append_if_new pain_points.jsonl pain_loop_guard_fires_late \
  "{\"id\": \"pain_loop_guard_fires_late\", \"type\": \"pain\", \"slug\": \"loop_guard_fires_late\", \"severity\": 2, \"count\": 2, \"status\": \"open\", \"added\": \"$TS\", \"note\": \"Read-spiral loop detection at iter 19 but spiral began at iter 6. Lower threshold for scaffold-first.\"}"
append_if_new pain_points.jsonl pain_non_scaffold_first_read_spiral \
  "{\"id\": \"pain_non_scaffold_first_read_spiral\", \"type\": \"pain\", \"slug\": \"non_scaffold_first_read_spiral\", \"severity\": 2, \"count\": 1, \"status\": \"hypothesis\", \"added\": \"$TS\", \"note\": \"Hard gate covers only gamedev-*-scaffold projects. Mine sessions for read-spirals elsewhere.\"}"

# --- asset_gap.jsonl (Shoal workflows to build) ---
append_if_new asset_gap.jsonl asset_top_down_character_001 \
  "{\"id\": \"asset_top_down_character_001\", \"type\": \"asset_gap\", \"target\": \"top_down_character\", \"category\": \"character\", \"anim_flag\": \"ANIM\", \"priority\": 5, \"added\": \"$TS\", \"note\": \"No canonical top-down workflow. Shoal plan category 1.\"}"
append_if_new asset_gap.jsonl asset_side_scroller_character_001 \
  "{\"id\": \"asset_side_scroller_character_001\", \"type\": \"asset_gap\", \"target\": \"side_scroller_character\", \"category\": \"character\", \"anim_flag\": \"ANIM\", \"priority\": 5, \"added\": \"$TS\"}"
append_if_new asset_gap.jsonl asset_vfx_library_001 \
  "{\"id\": \"asset_vfx_library_001\", \"type\": \"asset_gap\", \"target\": \"vfx_library\", \"category\": \"vfx\", \"anim_flag\": \"LOOP\", \"priority\": 4, \"added\": \"$TS\", \"note\": \"20+ pre-rendered VFX spritesheets. Cuts ERNIE load ~70%.\"}"
append_if_new asset_gap.jsonl asset_tree_static_001 \
  "{\"id\": \"asset_tree_static_001\", \"type\": \"asset_gap\", \"target\": \"tree_static\", \"category\": \"object\", \"anim_flag\": \"STATIC\", \"priority\": 3, \"added\": \"$TS\", \"note\": \"Base tree (no wind). 5 species.\"}"
append_if_new asset_gap.jsonl asset_tileable_terrain_001 \
  "{\"id\": \"asset_tileable_terrain_001\", \"type\": \"asset_gap\", \"target\": \"tileable_terrain\", \"category\": \"tileset\", \"anim_flag\": \"STATIC\", \"priority\": 4, \"added\": \"$TS\", \"note\": \"12 baseline terrains, 64x64 or 128x128 seamless.\"}"
append_if_new asset_gap.jsonl asset_47_tile_autotile_masks_001 \
  "{\"id\": \"asset_47_tile_autotile_masks_001\", \"type\": \"asset_gap\", \"target\": \"47_tile_autotile_masks\", \"category\": \"tileset\", \"anim_flag\": \"STATIC\", \"priority\": 3, \"added\": \"$TS\", \"note\": \"One-time mask template generation.\"}"
append_if_new asset_gap.jsonl asset_dialogue_portrait_001 \
  "{\"id\": \"asset_dialogue_portrait_001\", \"type\": \"asset_gap\", \"target\": \"dialogue_portrait\", \"category\": \"npc\", \"anim_flag\": \"STATIC_WITH_EMOTIONS\", \"priority\": 2, \"added\": \"$TS\"}"

echo ""
echo "  Coral queues seeded:"
for f in gap_queue.jsonl vertical_gap.jsonl pain_points.jsonl asset_gap.jsonl; do
  [ -f "$f" ] && echo "    $(wc -l < "$f") entries in $f"
done
echo ""
echo "  Launch the crew: $(cd "$(dirname "$0")" 2>/dev/null && pwd)/crew.sh launch"
