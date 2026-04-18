# Game 011 — Gradius (1985 arcade, 1986 NES)

**Arcade chip:** Konami custom + AY-3-8910 PSG.
**NES port chip:** 2A03 + **Konami VRC1** (extra channels on some).
**Channels (arcade):** 3 PSG square + noise. Dense arrangements by
modern arcade standards.

## Instrument archetypes

- **Square 1:** fast lead, scalar runs characteristic of Konami
- **Square 2:** harmony / counter-melody, often in 3rds
- **Square 3:** bass pedal or walking bass
- **Noise:** tight drum patterns, often 16ths

**ADSR:** punchy attack + short sustain + medium decay — arcade
audiences need immediate impact, not pads.

## SFX archetypes present

- Power-up select bar blip (menu tick for Speed / Missile / Double /
  Laser / Options / ?)
- Laser-shot: classic "pew" (archetype for our sfx_002)
- Missile: whoosh + low-end punch
- Option-gain (acquire "Option" drone): short ascending chord
- Ship-destroyed: downward sweep + noise burst
- Boss-warning: alarm klaxon loop (looping SFX!)
- Stage-clear: 4-note major fanfare
- Continue-screen: single descending note

## Music style tags

`konami-era`, `fast-BPM`, `action-focused`, `memorable-per-stage-
theme`, `arcade-attention-grabbing`, `chromatic-thrills`.

## Signature

**Power-up bar as audio feedback layer.** Pressing the power-up
button during play moves a cursor through 6 slots; each move emits a
short blip, and hitting "activate" plays a different confirm sting
per power-up type. **Audio is a gameplay display** — the sound tells
you what you selected even if you're looking at enemies.

Also: **the boss-warning klaxon** is a looping SFX that plays until
the boss appears. Classic state-sonification (cf. Pac-Man hurry-up).

**Composer:** Miki Higashino.

## Lessons for action-blocks audio

- Power-up-select pattern: menu_blip sfx + per-selection confirm sting.
  Library-driven (one sfx per slot type) — straightforward with
  `SfxLibrary` + `play_sfx_ref`.
- Boss-warning loop is another **play_sfx_loop** use case.
  Synthesis's attempt_002 queue addresses this.
- Shmup-genre audio is SFX-dense (sfx:music ratio ~3:1). The palette
  map for "shmup" should weight SFX heavily in recommendations.
- Arcade BGM at fast BPM (140-180) keeps tempo pressure on the player.
  Track_002 "Pressure" at 140 is in this range.
