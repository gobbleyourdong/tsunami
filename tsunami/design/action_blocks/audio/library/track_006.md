# Track 006 — "Fall" (game-over sting)

**Shape:** canonical `ChipMusicTrack` per synthesis attempt_001 §2.
**Mood tags:** defeat, finality, minor-descending, short
**BPM:** 80    **Bars:** 3    **Key:** A minor → unresolved
**Channel layout:** pulse1 = descending lament melody, triangle =
held low pedal, noise = single cymbal fade
**Serves archetype:** player-death, run-failed, game-over-screen
transition. Duration ~2.25s.

## Motif

Descending minor-scale melody (A5–G5–F5–E5–D5–C5–B4–A4 over 3 bars).
Triangle holds a low A2 throughout. Noise plays a cymbal crash that
slowly fades to silence as the last note hits. No loop.

Think Zelda-heart-container-empty / Mega-Man-death-tune — short
acceptance that the run is over, without being melodramatic.

## JSON

```json
{
  "bpm": 80,
  "loop": false,
  "channels": {
    "pulse1": [
      { "time": 0,   "note": "A5", "duration": 0.5, "velocity": 0.9,
        "envelope": { "attack": 0.01, "decay": 0.05, "sustain": 0.7, "release": 0.1 } },
      { "time": 0.5, "note": "G5", "duration": 0.5, "velocity": 0.85 },
      { "time": 1,   "note": "F5", "duration": 0.5, "velocity": 0.8 },
      { "time": 1.5, "note": "E5", "duration": 0.5, "velocity": 0.75 },
      { "time": 2,   "note": "D5", "duration": 0.5, "velocity": 0.7 },
      { "time": 2.5, "note": "C5", "duration": 0.5, "velocity": 0.6 },
      { "time": 3,   "note": "B4", "duration": 1,   "velocity": 0.5 },
      { "time": 4,   "note": "A4", "duration": 2,   "velocity": 0.4,
        "envelope": { "attack": 0.02, "decay": 0.2, "sustain": 0.4, "release": 1.5 } }
    ],
    "triangle": [
      { "time": 0, "note": "A2", "duration": 6 }
    ],
    "noise": [
      { "time": 0, "note": "crash", "duration": 1.5, "velocity": 0.6,
        "envelope": { "attack": 0.0, "decay": 0.3, "sustain": 0.2, "release": 3.0 } }
    ]
  },
  "mixer": { "pulse1": 0.8, "triangle": 0.9, "noise": 0.5 }
}
```

**Content note:**
- `loop: false` — sting only, fires once.
- Per-note `envelope` overrides let the final A4 decay gently for a
  "fade" feel rather than abrupt cutoff.
- No pulse2 — the thinner texture signals "end of something," not
  arrangement-complete.
- Total duration ~4.5s at 80 BPM across 6 beats of music. Short enough
  to dismiss quickly and return to title or checkpoint.
