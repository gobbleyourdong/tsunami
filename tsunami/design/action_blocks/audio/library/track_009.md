# Track 009 — "The Shopkeep" (shop / town / safe-area loop)

**Shape:** canonical `ChipMusicTrack`.
**Mood:** warm, welcoming, major, moderate-energy
**BPM:** 96    **Bars:** 8    **Key:** F major
**Channel layout:** pulse1 = cheerful melodic lead, pulse2 = 3rd-
below harmony, triangle = I–IV–V bass walk, noise = brushed-snare
light percussion (low velocity)
**Serves archetype:** shop/vendor, town/village, rest-area, safe-
zone between dungeons, tutorial-mentor interaction

## Motif

Two 4-bar phrases. First phrase: F-major scale steps up (F–G–A–Bb–C).
Second phrase: arpeggiated resolution (F–A–C–F). Triangle walks
F–Bb–C–F (I–IV–V–I). Drums hit softly on 1 and 3. Harmony pulse 2
follows at 3rd below.

## JSON

```json
{
  "bpm": 96,
  "loop": true,
  "channels": {
    "pulse1": [
      { "time": 0,    "note": "F5", "duration": 0.5, "dutyCycle": 0.5 },
      { "time": 0.5,  "note": "G5", "duration": 0.5 },
      { "time": 1,    "note": "A5", "duration": 0.5 },
      { "time": 1.5,  "note": "A#5","duration": 0.5 },
      { "time": 2,    "note": "C6", "duration": 1 },
      { "time": 3,    "note": "A5", "duration": 1 },

      { "time": 4,    "note": "F5", "duration": 0.5 },
      { "time": 4.5,  "note": "A5", "duration": 0.5 },
      { "time": 5,    "note": "C6", "duration": 0.5 },
      { "time": 5.5,  "note": "F6", "duration": 0.5 },
      { "time": 6,    "note": "C6", "duration": 1 },
      { "time": 7,    "note": "F5", "duration": 1 }
    ],
    "pulse2": [
      { "time": 0,    "note": "A4", "duration": 0.5, "dutyCycle": 0.25 },
      { "time": 0.5,  "note": "A#4","duration": 0.5 },
      { "time": 1,    "note": "C5", "duration": 0.5 },
      { "time": 1.5,  "note": "D5", "duration": 0.5 },
      { "time": 2,    "note": "E5", "duration": 1 },
      { "time": 3,    "note": "C5", "duration": 1 },

      { "time": 4,    "note": "A4", "duration": 0.5 },
      { "time": 4.5,  "note": "C5", "duration": 0.5 },
      { "time": 5,    "note": "E5", "duration": 0.5 },
      { "time": 5.5,  "note": "A5", "duration": 0.5 },
      { "time": 6,    "note": "E5", "duration": 1 },
      { "time": 7,    "note": "A4", "duration": 1 }
    ],
    "triangle": [
      { "time": 0, "note": "F2", "duration": 2 },
      { "time": 2, "note": "F2", "duration": 2 },
      { "time": 4, "note": "A#2","duration": 2 },
      { "time": 6, "note": "C3", "duration": 2 }
    ],
    "noise": [
      { "time": 0, "note": "snare",      "duration": 0.1, "velocity": 0.25 },
      { "time": 1, "note": "hat_closed", "duration": 0.08, "velocity": 0.2 },
      { "time": 2, "note": "snare",      "duration": 0.1, "velocity": 0.25 },
      { "time": 3, "note": "hat_closed", "duration": 0.08, "velocity": 0.2 },
      { "time": 4, "note": "snare",      "duration": 0.1, "velocity": 0.25 },
      { "time": 5, "note": "hat_closed", "duration": 0.08, "velocity": 0.2 },
      { "time": 6, "note": "snare",      "duration": 0.1, "velocity": 0.25 },
      { "time": 7, "note": "hat_closed", "duration": 0.08, "velocity": 0.2 }
    ]
  },
  "mixer": { "pulse1": 0.9, "pulse2": 0.5, "triangle": 0.7, "noise": 0.4 }
}
```

**Content notes:**
- 96 BPM is deliberately moderate — neither tense nor slow. Walking
  pace.
- F major is a classically "warm" key for brass-ish / bright-lead
  timbres.
- Bars 1–4 shown; bars 5–8 repeat with slight counter-melody swap
  on pulse2.
- Low-velocity drums (0.2–0.25) provide pulse without dominating.
