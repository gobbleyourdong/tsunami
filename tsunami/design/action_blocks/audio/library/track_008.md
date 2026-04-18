# Track 008 — "Deep Hollow" (ambient cave)

**Shape:** canonical `ChipMusicTrack`.
**Mood:** subterranean, ominous, minor-modal, non-rhythmic
**BPM:** 60 (slow — functions more as an ambient texture than
structured music)
**Bars:** 8
**Key:** D phrygian (dark modal color)
**Channel layout:** pulse1 = long melodic arc, pulse2 = drone fifth,
triangle = low pedal, noise = occasional water-drip (sparse,
arrhythmic)
**Serves archetype:** cave-dungeon, underwater-area, night-scene,
horror-exploration. Unsettling but not attacking.

## Motif

Slow descending phrygian scale (D–Eb–F–G–A–Bb–C–D) fragmented over
8 bars. Triangle holds low D2 drone. Pulse 2 holds a sustained 5th
(D4+A4) every 4 bars. Noise plays single "hat_open" drops at
irregular beats — sonifying condensation.

## JSON

```json
{
  "bpm": 60,
  "loop": true,
  "channels": {
    "pulse1": [
      { "time": 0,  "note": "D5",  "duration": 2, "velocity": 0.4,
        "envelope": { "attack": 0.15, "decay": 0.3, "sustain": 0.6, "release": 0.5 } },
      { "time": 2,  "note": "D#5", "duration": 2, "velocity": 0.35 },
      { "time": 5,  "note": "F5",  "duration": 1, "velocity": 0.3 },
      { "time": 8,  "note": "G5",  "duration": 2, "velocity": 0.35 },
      { "time": 12, "note": "A5",  "duration": 1, "velocity": 0.35 },
      { "time": 14, "note": "A#5", "duration": 1, "velocity": 0.3 },
      { "time": 18, "note": "C6",  "duration": 2, "velocity": 0.3 },
      { "time": 22, "note": "D6",  "duration": 3, "velocity": 0.4,
        "envelope": { "attack": 0.2, "decay": 0.4, "sustain": 0.5, "release": 1.2 } }
    ],
    "pulse2": [
      { "time": 0,  "note": "D4", "duration": 4, "velocity": 0.3, "dutyCycle": 0.125 },
      { "time": 8,  "note": "A4", "duration": 4, "velocity": 0.3, "dutyCycle": 0.125 },
      { "time": 16, "note": "D4", "duration": 4, "velocity": 0.3, "dutyCycle": 0.125 },
      { "time": 24, "note": "A4", "duration": 4, "velocity": 0.3, "dutyCycle": 0.125 }
    ],
    "triangle": [
      { "time": 0, "note": "D2", "duration": 32 }
    ],
    "noise": [
      { "time": 3.5, "note": "hat_open", "duration": 0.2, "velocity": 0.25 },
      { "time": 11.2, "note": "hat_open", "duration": 0.2, "velocity": 0.2 },
      { "time": 19.8, "note": "hat_open", "duration": 0.2, "velocity": 0.3 },
      { "time": 27.1, "note": "hat_open", "duration": 0.2, "velocity": 0.25 }
    ]
  },
  "mixer": { "pulse1": 0.5, "pulse2": 0.3, "triangle": 0.7, "noise": 0.2 }
}
```

**Content notes:**
- 60 BPM + long note durations (1-3 beats each) = slow, floating
  texture. Non-grooving.
- Phrygian mode (flat 2nd) gives the "Dorian-but-darker" feel.
- Per-note `envelope` overrides with long attacks (0.15-0.2s) let
  notes fade in rather than pluck — critical for atmospheric feel.
- Irregular noise timings (3.5 / 11.2 / 19.8 / 27.1) simulate
  unpredictable environmental drips. Arrhythmic on purpose.
- `hat_open` token chosen (rather than `hat_closed`) for the
  decay-tail quality matching a water drop's sustain.
