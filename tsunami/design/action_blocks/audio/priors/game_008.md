# Game 008 — Street Fighter II: The World Warrior (1991, arcade / CPS-1)

**Chip:** Yamaha YM2151 (8-channel FM) + OKI MSM6295 (4-channel PCM).

Arcade hardware, not home console. Significantly richer than NES/GB:
- 8 channels of 4-op FM (same era as Genesis but more channels)
- 4 channels of sample playback (for voice clips + drum hits)

## Instrument archetypes

- **FM lead:** bright brass-or-saw synth, melodic character theme per
  fighter (Ryu, Ken, Blanka, Chun-Li each have signature motif)
- **FM bass:** punchy 4-op bass (like Sonic's slap but different
  algorithm)
- **FM drums:** FM-kick + FM-snare can sound tight but artificial
- **PCM drums:** sampled breaks layered OVER FM drums for fatter hits
- **PCM voice:** "HADOUKEN!", "SHORYUKEN!", "YOGA FIRE!" — per-move
  samples

## SFX archetypes

Arcade fighter SFX are **dense, high-information-rate:**
- Hit (light/medium/heavy): layered noise + FM + PCM punch sample
- Block: metallic clink (FM resonant)
- Throw: whoosh + thump
- Special-move input confirmation: "HADOUKEN" voice sample
- K.O.: elongated downward sweep + final sampled ring
- Round-start: "ROUND ONE — FIGHT!" PCM voice
- Time-up: klaxon alarm loop
- Coin-insert: ascending square fanfare

## Music style tags

`character-theme-per-fighter`, `culturally-coded-melodies` (Blanka =
samba-ish, Chun-Li = Chinese-pentatonic, Dhalsim = Indian-modal),
`regional-flavor`, `fast-BPM` (often 130-150), `looping-battle-layer`,
`tension-building-final-round`.

## Signature

**Leitmotif-per-character.** Like Chrono Trigger but applied to
fighters. Each stage has a theme tuned to the fighter's cultural
identity. Universally recognizable ("Ken's theme" = US-rock-motif
with fast lead + driving bass). Evidence of the emergence-via-
composition thesis (note_007): 12 themes × 12 fighters × hundreds of
matches = musical identity per match-up.

## Lessons for action-blocks audio

- **Character-theme pattern** — in an action-blocks game with multiple
  playable characters (party RPG, fighting, racing), author one
  ChipMusic per character. The flow selects the theme based on the
  current character archetype. Cheap per unit, high-signal per unit.

- **Arcade FM is out of v1 chipsynth scope.** Our 4-channel NES-style
  synth can't replicate SF2's FM depth or PCM-voice clips. The 
  *structure* transfers (character themes + stage loops + sting SFX);
  the *timbre* doesn't. Author SF2-shape games with compromised timbre,
  or wait for a later FM synth.

- **PCM-voice-as-SFX** is out of scope procedurally but fits cleanly
  into the existing pre-made-audio playback path. If an author wants
  "HADOUKEN" they record it and use `play_sound`, NOT `play_sfx`.
  The two systems coexist; sfxr covers chip-like SFX, samples cover
  recorded audio.
