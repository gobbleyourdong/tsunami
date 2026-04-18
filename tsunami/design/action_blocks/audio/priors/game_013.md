# Game 013 — The Legend of Zelda: A Link to the Past (1991, SNES)

**Chip:** Same as game_002 (Sony SPC700 + S-DSP). **Channels:** 8 ADPCM.

Same hardware as Chrono Trigger — different era (1991 vs 1995). Earlier
SPC700 software techniques; less dynamic range exploration, more
memorable-melody-forward.

## Instrument archetypes

- **Channel 1 (melody):** bright synth horn or harp sample — carries
  most of the memorable motifs
- **Channel 2 (harmony):** either 3rd-below doubling or pad pulse
- **Channel 3 (bass):** sampled bass or low synth
- **Channels 4-5 (percussion):** kick/snare/hat samples
- **Channels 6-8 (variable):** used for strings/choir pads or for
  counter-melodies

**Wide dynamic range:** calm overworld tracks use 3-4 active channels;
dungeon tracks use 6-7 with tension-heavy layering.

## SFX archetypes present

- Sword-slash: noise + descending pitch
- Sword-spin-charge: held rising tone (charge progress sonified)
- Bomb-explosion: low noise burst + pitch drop
- Chest-open: major arpeggio (heritage of game_003's jingle)
- Rupee-pickup: short pulse blip (heritage of sfx_001)
- Secret-found: 6-note major cadence (signature Zelda discovery chime)
- Hookshot: chain rattle (sampled — not procedural)
- Damage: descending "ow"
- Low-hearts: looping heartbeat alarm (state-sonification)
- Dungeon-complete: triumphant orchestral fanfare

## Music style tags

`hero-journey`, `memorable-melody-forward`, `major-key-overworld`,
`minor-key-dungeon`, `dynamic-active-channel-count`, `dark-world-
contrast`, `cultural-universal-melodies`.

## Signature

**Overworld vs dungeon vs town** — three clearly-distinguished music
registers. Overworld = confident + triumphant. Dungeon = tense +
minor + sparse. Town = peaceful + major + ambient. The player knows
the game state from the music alone.

Also: **the low-hearts heartbeat alarm.** A looping SFX that plays
when HP is below threshold. Doubles as state-sonification and player
warning without UI emphasis.

**Composer:** Koji Kondo (also game_001 / Mario).

## Lessons for action-blocks audio

- **Three-register music design** (overworld / dungeon / town) is a
  transferable pattern. Author 3 ChipMusic tracks per game with
  clear mood distinction; let the flow switch based on scene type.
  This is basically what `track_004 Over the Hill` + `track_005
  Approach` demonstrate at a 2-register cut.
- **HP-threshold alarm loop** is another play_sfx_loop use case. Ties
  to health system (already in engine, per `HealthSystem.onDamage`
  callback). When HP < N, start loop; when HP >= N, stop.
- **Dynamic channel count** as a feel mechanic — our chipsynth can
  mute/unmute channels per-track at runtime (via mixer map). Using
  `mixer` values of 0 for certain bars lets authors "pull channels
  out" for tension drops. Content-thread's track_005 could exploit
  this in bar 4 for a dynamic dip.
