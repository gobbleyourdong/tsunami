# Track 004 — "Over the Hill" (overworld exploration loop)

**Shape:** canonical `ChipMusicTrack` per synthesis attempt_001 §2.
**Mood tags:** wandering, pastoral, major, moderate-tempo
**BPM:** 100    **Bars:** 16    **Key:** G major
**Channel layout:** pulse1 = folky stepwise melody, pulse2 = open-5ths
harmony with 25% duty, triangle = simple I-V bass, noise = sparse
(hat on beat 1 only)
**Serves archetype:** overworld map, forest path, peaceful daytime
area — Zelda / RPG exploration feel

## Motif

Stepwise melody in 4-bar phrases, resolving back to G every 4 bars
(I–IV–V–I). Pulse 2 drones open fifths underneath (G+D, then C+G,
etc.) for "wide field" sound. Light percussion emphasizes walking pace.

## JSON (canonical shape)

Time and duration are in **beats** per attempt_001. Drum tokens from
synthesis drum-map.

```json
{
  "bpm": 100,
  "loop": true,
  "channels": {
    "pulse1": [
      { "time": 0,    "note": "G5", "duration": 1 },
      { "time": 1,    "note": "A5", "duration": 0.5 },
      { "time": 1.5,  "note": "B5", "duration": 0.5 },
      { "time": 2,    "note": "D6", "duration": 1 },
      { "time": 3,    "note": "B5", "duration": 1 },

      { "time": 4,    "note": "C6", "duration": 1 },
      { "time": 5,    "note": "D6", "duration": 0.5 },
      { "time": 5.5,  "note": "E6", "duration": 0.5 },
      { "time": 6,    "note": "D6", "duration": 1 },
      { "time": 7,    "note": "B5", "duration": 1 },

      { "time": 8,    "note": "A5", "duration": 0.5 },
      { "time": 8.5,  "note": "B5", "duration": 0.5 },
      { "time": 9,    "note": "C6", "duration": 1 },
      { "time": 10,   "note": "A5", "duration": 1 },
      { "time": 11,   "note": "D5", "duration": 1 },

      { "time": 12,   "note": "G5", "duration": 2 },
      { "time": 14,   "note": "D5", "duration": 1 },
      { "time": 15,   "note": "G5", "duration": 1 }
    ],
    "pulse2": [
      { "time": 0,  "note": "G4", "duration": 4, "dutyCycle": 0.25 },
      { "time": 4,  "note": "C5", "duration": 4, "dutyCycle": 0.25 },
      { "time": 8,  "note": "D5", "duration": 4, "dutyCycle": 0.25 },
      { "time": 12, "note": "G4", "duration": 4, "dutyCycle": 0.25 }
    ],
    "triangle": [
      { "time": 0,  "note": "G2", "duration": 2 },
      { "time": 2,  "note": "D2", "duration": 2 },
      { "time": 4,  "note": "C2", "duration": 2 },
      { "time": 6,  "note": "G2", "duration": 2 },
      { "time": 8,  "note": "D2", "duration": 2 },
      { "time": 10, "note": "A2", "duration": 2 },
      { "time": 12, "note": "G2", "duration": 2 },
      { "time": 14, "note": "D2", "duration": 2 }
    ],
    "noise": [
      { "time": 0,  "note": "hat_closed", "duration": 0.25, "velocity": 0.3 },
      { "time": 4,  "note": "hat_closed", "duration": 0.25, "velocity": 0.3 },
      { "time": 8,  "note": "hat_closed", "duration": 0.25, "velocity": 0.3 },
      { "time": 12, "note": "hat_closed", "duration": 0.25, "velocity": 0.3 }
    ]
  },
  "mixer": { "pulse1": 0.9, "pulse2": 0.5, "triangle": 0.7, "noise": 0.3 }
}
```

**Content note:** 16-bar overworld track — the longest so far.
Matches Zelda LTTP / Metroid overworld lengths. Loop seamlessly from
bar 16 → bar 0 (pulse2's 4-bar pad cycles naturally).
