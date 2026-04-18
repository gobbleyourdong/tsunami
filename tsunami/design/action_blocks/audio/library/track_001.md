# Track 001 — "Overture" (title anthem)

**Mood tags:** anthemic, confident, major-key, NES-like
**BPM:** 110    **Bars:** 8    **Key:** C major
**Channel layout:** pulse1 = lead melody, pulse2 = harmony arpeggio,
triangle = bass, noise = light percussion (downbeats)
**Serves archetype:** title-screen for arcade-action, platformer,
classic-retro game-project

## Motif

Ascending I–V–IV–V progression. Pulse 1 plays a proud stepwise melody
over pulse 2's fast broken-chord arpeggios. Triangle marks the bass
(C–C–F–G pattern). Noise hits on 1 and 3 for a light march feel.

## JSON (placeholder shape per BRIEF_CONTENT.md)

```json
{
  "bpm": 110,
  "channels": {
    "pulse1": [
      { "time": 0.00, "note": "C5",  "duration": 0.54 },
      { "time": 0.54, "note": "E5",  "duration": 0.54 },
      { "time": 1.09, "note": "G5",  "duration": 0.54 },
      { "time": 1.63, "note": "C6",  "duration": 0.54 },
      { "time": 2.18, "note": "B5",  "duration": 0.54 },
      { "time": 2.72, "note": "G5",  "duration": 0.54 },
      { "time": 3.27, "note": "E5",  "duration": 0.54 },
      { "time": 3.81, "note": "G5",  "duration": 0.54 },
      { "time": 4.36, "note": "F5",  "duration": 0.54 },
      { "time": 4.90, "note": "A5",  "duration": 0.54 },
      { "time": 5.45, "note": "C6",  "duration": 0.54 },
      { "time": 6.00, "note": "F6",  "duration": 0.54 },
      { "time": 6.54, "note": "G5",  "duration": 0.54 },
      { "time": 7.09, "note": "B5",  "duration": 0.54 },
      { "time": 7.63, "note": "D6",  "duration": 0.54 },
      { "time": 8.18, "note": "G6",  "duration": 1.09 }
    ],
    "pulse2": [
      { "time": 0.00, "note": "C4", "duration": 0.18 },
      { "time": 0.18, "note": "E4", "duration": 0.18 },
      { "time": 0.36, "note": "G4", "duration": 0.18 }
    ],
    "triangle": [
      { "time": 0.00, "note": "C3", "duration": 2.18 },
      { "time": 2.18, "note": "C3", "duration": 2.18 },
      { "time": 4.36, "note": "F3", "duration": 2.18 },
      { "time": 6.54, "note": "G3", "duration": 2.18 }
    ],
    "noise": [
      { "time": 0.00, "note": "hi",  "duration": 0.08, "velocity": 0.4 },
      { "time": 1.09, "note": "hi",  "duration": 0.08, "velocity": 0.4 },
      { "time": 2.18, "note": "hi",  "duration": 0.08, "velocity": 0.4 },
      { "time": 3.27, "note": "hi",  "duration": 0.08, "velocity": 0.4 }
    ]
  },
  "loop": true
}
```

Pulse 2 abbreviated above — the full track repeats the C arpeggio
through the 8 bars with pitch matching the bass root. The shape is
what the synthesis thread needs to see; full expansion is parser
work.

**Implementation note:** duration values assume 110 BPM, so quarter =
60/110 = 0.545s. The synthesis thread may want to express time/duration
in *beats* rather than seconds so tempo changes don't require
re-authoring — flag for their next attempt.
