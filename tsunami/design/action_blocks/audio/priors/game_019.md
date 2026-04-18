# Game 019 — Crypt of the NecroDancer (2015, Brace Yourself Games)

**Audio:** sampled + procedural. Runs on Unity. Sampled music + OGG
playback for main tracks; procedural timing analysis for beat-
detection.

**Genre:** roguelite-rhythm hybrid — every action must align with
the music's beat. Miss the beat = lose your combo multiplier.

## Why this matters

NecroDancer is the **prototype for the "grid-roguelite + rhythm"
genre.** Rhythm-gated movement means audio timing IS the core
mechanic. Player's success literally depends on hearing the music.

**Plus:** composer Danny Baranowsky's soundtrack allows **any music
to replace the defaults** via user-supplied MP3 imports — the rhythm
engine just beat-detects the track. Evidence that a well-built
rhythm mechanic is entirely **content-driven** (note_009 content-
multiplier thesis).

## Instrument archetypes

Original OST (Baranowsky + others):
- **Full-band electronic arrangements** per floor:
  Heart (spooky organ), Zone 1 (catacombs piano), Zone 2 (hot rock
  guitar), etc.
- **Beat prominence** emphasized in all tracks — 4/4 time, clear
  kick on downbeats, so the player can hear WHERE the beat is.
- **8–16 bar progressions** looping; track switches when player
  enters next level.

## SFX archetypes present

- Beat-tick (visible on UI): short pulse synced to beat
- Move-on-beat: satisfying "step" confirmation
- Move-off-beat: dulled "whiff" — player knows they broke combo
- Enemy-attack-telegraph: warning pulse 1 beat before hit
- Combo-break: descending error-buzz
- Coin-pickup: in-key chime quantized to next beat
- Boss-warning: short sting before boss-floor
- Die: descending loss theme

## Music style tags

`rhythm-gated-action`, `beat-analysis-required`, `player-music-
import-supported`, `combo-preservation`, `genre-hybrid`, `sampled-
BGM-with-procedural-timing`.

## Signature

**The mechanic IS the audio.** Without audible beat, the game doesn't
work. This is the strongest possible coupling of audio and gameplay
in the corpus. Every prior game uses audio as accompaniment or
feedback; NecroDancer uses audio as game state.

Proves **rhythm-gated action** is a genre that demands audio to be
load-bearing, not decorative.

**Composer:** Danny Baranowsky + Virt (Jake Kaufman, same as Shovel
Knight game_009) + others.

## Lessons for action-blocks audio

- **Rhythm-gated action** needs ChipMusic's `exposes.current_beat`
  to be reliable and expose as ConditionKey for flow + mechanics:
  ```ts
  // mechanic could gate on beat:
  trigger: { kind: 'damage', requires_beat?: 'on' | 'off' }
  ```
  This is a new schema thread — probably deserves its own v1.1.3
  proposal. Flag for synthesis next-fire considerations.

- **User-supplied music import** — out of chipsynth scope directly
  (our music is ChipMusic-authored JSON, not MP3 import). But the
  pattern is worth noting: for **procedural rhythm games**, the
  game could accept any audio file and extract beat-timing from it
  (FFT + onset detection). Deferrable to v2 rhythm scaffold.

- **Genre hybrid justifies a specific palette**:
  - Rhythm-roguelite: base track per floor + beat-ticks + move-on /
    move-off sfx + combo stingers. palette_MAP needs this row.

- **Baranowsky's influence** across multiple indie titles (Canabalt,
  Super Meat Boy, Binding of Isaac, NecroDancer) suggests an **author-
  level consistency** pattern. If Tsunami can identify a composer's
  signature, content-multiplier × author-signature = stylistically
  coherent output. Relevant for fine-tuning / QA fit metrics.
