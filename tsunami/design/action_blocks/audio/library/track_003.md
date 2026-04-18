# Track 003 — "Resolve" (victory fanfare)

**Mood tags:** triumphant, resolved, major, short-sting
**BPM:** 120    **Bars:** 4    **Key:** C major
**Channel layout:** pulse1 = bright fanfare lead, pulse2 = harmony
third below, triangle = punctuating bass hits, noise = single cymbal
crash at peak
**Serves archetype:** stage-clear, boss-kill, puzzle-solve, level-
complete — anywhere a short reward sting is needed. Duration ~4s.

## Motif

Classic I–IV–V–I cadence compressed into a 4-bar flourish. Pulse 1
does an ascending arpeggio (C–E–G–C–E–G–C) + sustained high C. Pulse
2 shadows at a third. Triangle hits root bass. Noise adds a cymbal
crash at the final high C.

## JSON

```json
{
  "bpm": 120,
  "channels": {
    "pulse1": [
      { "time": 0.00, "note": "C5", "duration": 0.25, "velocity": 0.9 },
      { "time": 0.25, "note": "E5", "duration": 0.25, "velocity": 0.9 },
      { "time": 0.50, "note": "G5", "duration": 0.25, "velocity": 0.9 },
      { "time": 0.75, "note": "C6", "duration": 0.25, "velocity": 0.9 },
      { "time": 1.00, "note": "E6", "duration": 0.25, "velocity": 1.0 },
      { "time": 1.25, "note": "G6", "duration": 0.25, "velocity": 1.0 },
      { "time": 1.50, "note": "C7", "duration": 1.00, "velocity": 1.0 }
    ],
    "pulse2": [
      { "time": 0.00, "note": "E4", "duration": 0.25 },
      { "time": 0.25, "note": "G4", "duration": 0.25 },
      { "time": 0.50, "note": "B4", "duration": 0.25 },
      { "time": 0.75, "note": "E5", "duration": 0.25 },
      { "time": 1.00, "note": "G5", "duration": 0.25 },
      { "time": 1.25, "note": "B5", "duration": 0.25 },
      { "time": 1.50, "note": "E6", "duration": 1.00 }
    ],
    "triangle": [
      { "time": 0.00, "note": "C3", "duration": 0.5 },
      { "time": 0.50, "note": "F3", "duration": 0.5 },
      { "time": 1.00, "note": "G3", "duration": 0.5 },
      { "time": 1.50, "note": "C4", "duration": 1.0 }
    ],
    "noise": [
      { "time": 1.50, "note": "crash", "duration": 0.8, "velocity": 1.0 }
    ]
  },
  "loop": false
}
```

**Implementation notes:**
- `loop: false` — one-shot sting, not a looping track.
- "crash" on noise channel is another named preset that needs mapping
  in the chipsynth drum-names table. If undefined, fall back to
  long-period noise with slow-decay envelope.
- Total duration is 2.5s at 120 BPM — this is a **short sting**, not
  a full track. Use for immediate-feedback moments (kill, pickup
  milestone). Most victory fanfares in shipped retro games are in
  this 2-4s range.
