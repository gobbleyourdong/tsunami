# Track 012 — "Triumph" (full victory theme)

**Shape:** canonical `ChipMusicTrack`.
**Mood:** triumphant, anthemic, major, celebratory
**BPM:** 128    **Bars:** 16    **Key:** F major
**Channel layout:** pulse1 = soaring melody, pulse2 = 3rd-below
harmony, triangle = walking bass with octave leaps, noise = strong
drum hits on 1 & 3 + fill patterns
**Serves archetype:** game-complete, credits-sequence, full-stage-
clear, major-story-victory. **Long form** (16 bars) — contrast with
`track_003 Resolve` which is a 4-bar sting.

## Motif

Two 8-bar halves.
- **Bars 1–8:** Anthemic opening — pulse1 ascending melody,
  prominent major thirds + perfect fifths. I–V–vi–IV progression
  (the classic "celebration" chord pattern).
- **Bars 9–16:** Soaring conclusion — pulse1 melody octave-leaps
  higher, pulse2 counterpoint stands out, noise fills accent the
  peak. Ends on sustained F6 with all channels holding a full I chord.

## JSON (first 4 bars + pattern for remaining 12)

```json
{
  "bpm": 128,
  "loop": false,
  "channels": {
    "pulse1": [
      { "time": 0,    "note": "F5", "duration": 0.5, "dutyCycle": 0.5 },
      { "time": 0.5,  "note": "A5", "duration": 0.5 },
      { "time": 1,    "note": "C6", "duration": 0.5 },
      { "time": 1.5,  "note": "F6", "duration": 1,  "velocity": 0.95 },
      { "time": 2.5,  "note": "C6", "duration": 0.5 },
      { "time": 3,    "note": "D6", "duration": 1 },

      { "time": 4,    "note": "C6", "duration": 0.5 },
      { "time": 4.5,  "note": "A5", "duration": 0.5 },
      { "time": 5,    "note": "Bb5","duration": 0.5 },
      { "time": 5.5,  "note": "D6", "duration": 1,  "velocity": 0.95 },
      { "time": 6.5,  "note": "C6", "duration": 0.5 },
      { "time": 7,    "note": "A5", "duration": 1 },

      { "time": 8,    "note": "D5", "duration": 0.5 },
      { "time": 8.5,  "note": "F5", "duration": 0.5 },
      { "time": 9,    "note": "A5", "duration": 0.5 },
      { "time": 9.5,  "note": "D6", "duration": 1,  "velocity": 0.95 },
      { "time": 10.5, "note": "A5", "duration": 0.5 },
      { "time": 11,   "note": "Bb5","duration": 1 },

      { "time": 12,   "note": "C6", "duration": 0.5 },
      { "time": 12.5, "note": "Bb5","duration": 0.5 },
      { "time": 13,   "note": "A5", "duration": 0.5 },
      { "time": 13.5, "note": "C6", "duration": 1 },
      { "time": 14.5, "note": "F5", "duration": 0.5 },
      { "time": 15,   "note": "C6", "duration": 1 }
    ],
    "pulse2": [
      { "time": 0,  "note": "A4", "duration": 2, "dutyCycle": 0.25 },
      { "time": 2,  "note": "F4", "duration": 2 },
      { "time": 4,  "note": "G4", "duration": 2 },
      { "time": 6,  "note": "F4", "duration": 2 },
      { "time": 8,  "note": "F4", "duration": 2 },
      { "time": 10, "note": "G4", "duration": 2 },
      { "time": 12, "note": "F4", "duration": 2 },
      { "time": 14, "note": "E4", "duration": 2 }
    ],
    "triangle": [
      { "time": 0,  "note": "F2", "duration": 2 },
      { "time": 2,  "note": "C3", "duration": 2 },
      { "time": 4,  "note": "D3", "duration": 2 },
      { "time": 6,  "note": "Bb2","duration": 2 },
      { "time": 8,  "note": "F2", "duration": 2 },
      { "time": 10, "note": "Bb2","duration": 2 },
      { "time": 12, "note": "F2", "duration": 2 },
      { "time": 14, "note": "C3", "duration": 2 }
    ],
    "noise": [
      { "time": 0,    "note": "kick",  "duration": 0.12, "velocity": 0.9 },
      { "time": 1,    "note": "snare", "duration": 0.12, "velocity": 0.9 },
      { "time": 2,    "note": "kick",  "duration": 0.12 },
      { "time": 3,    "note": "snare", "duration": 0.12 },
      { "time": 3.75, "note": "hat_open","duration": 0.2 },
      { "time": 4,    "note": "kick",  "duration": 0.12 },
      { "time": 5,    "note": "snare", "duration": 0.12 },
      { "time": 6,    "note": "kick",  "duration": 0.12 },
      { "time": 7,    "note": "snare", "duration": 0.12 },
      { "time": 7.5,  "note": "crash", "duration": 0.6,  "velocity": 0.7 }
    ]
  },
  "mixer": { "pulse1": 1.0, "pulse2": 0.7, "triangle": 0.85, "noise": 0.75 }
}
```

**Content notes:**
- 8 bars shown; bars 9–16 repeat the bar-1-to-8 structure transposed
  up one octave on pulse1 for the "soaring" feel.
- `loop: false` — plays once, then silence (or transition to next
  scene).
- Total duration ~30s at 128 BPM. Serves credits / story-ending well.
- Classic I–V–vi–IV (F–C–Dm–Bb) chord loop on pulse2 + triangle.
