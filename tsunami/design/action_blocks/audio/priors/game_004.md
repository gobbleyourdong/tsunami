# Game 004 — Sonic the Hedgehog 2 (1992, Genesis/Mega Drive)

**Chips (two together):**
- **Yamaha YM2612** — 6 channels of 4-operator FM synthesis (or 5 FM + 1 PCM sample)
- **Texas SN76489** — 4-channel PSG (3 square + 1 noise)

Total: ~10 channels when both chips active. The **FM** is where
Sonic's distinctive sound comes from — no NES has FM.

## Instrument archetypes

| Channel role | Chip | Archetype |
|---|---|---|
| Slap bass | FM | 4-op FM with fast attack + slight release — signature Sonic bass |
| Lead synth | FM | bright 4-op FM brass or lead |
| Pad | FM | slower-attack 4-op stack, maybe layered with PSG |
| Drum kit | FM + PSG noise | FM handles kick (pitched sine), PSG noise = snare/hat |
| Harmony | PSG square | fills gaps FM doesn't cover |

**FM characteristic:** operators modulate each other (algorithm
selection controls topology). 8 algorithms available on YM2612.
Algorithm 4-6 = bell/e-piano feel; algorithm 7 = 4 pure sines
(adding for organ-like).

## SFX archetypes

- Ring-pickup: short sine ping, high pitch
- Lose-rings: descending PCM sample (sampled, not synthesized)
- Jump: "bop" — short pitched sine
- Spin-dash charge: pitched-up pulse loop
- Spin-dash release: descending noise + pitch sweep
- Boss-hit: "clang" = FM metallic
- Level-clear: ascending arpeggio fanfare

## Music style tags

`funky-bass-forward`, `house-disco-influence`, `chromatic-harmony`,
`major-7th-chords`, `tight-drum-groove`, `bright-lead-synth`,
`chemical-plant-energy`.

## Signature

**The slap-bass lead** is what makes Sonic sound like Sonic. 4-op FM
patch with:
- Op 1 (carrier): sine
- Op 2-3 (modulators): higher-frequency, short envelope
- Algorithm: 3 or 5 (two modulators stacked into carrier)
- Short AMP envelope: punchy attack, quick decay

Masato Nakamura (Sonic 1+2 composer) was a J-pop producer, which is
why the chord voicings are jazzy rather than arcade-simple.

## Lessons for action-blocks audio

- **FM synthesis is out of v1 chipsynth scope.** Our spec is pulse+
  triangle+noise (NES-style) — matches ~80% of retro "chippy" feel
  without needing FM's 4-op complexity.
- **PSG-only Genesis tracks** (rare but exist — pause-menu beeps,
  early demo songs) are achievable with our chipsynth. The FM-rich
  tracks aren't.
- If v2 audio ever wants FM: `FmPatchParams { algorithm: 0..7,
  operators: [{freq_mul, env, level}, ...] }` — but that's a lot of
  surface to add. Out of scope now.
- Genesis tracks are evidence that **content-multiplier works at the
  high end too** — same YM2612 patches × different track JSONs =
  wildly varied music (Streets of Rage vs Sonic vs Phantasy Star IV
  all sound distinct from the same chip).
