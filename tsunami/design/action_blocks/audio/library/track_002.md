# Track 002 — "Pressure" (combat loop)

**Mood tags:** driving, tense, minor-key, arcade-shooter
**BPM:** 140    **Bars:** 8    **Key:** D minor
**Channel layout:** pulse1 = syncopated lead, pulse2 = detuned octave
doubling for "thicker" sound, triangle = walking bass (steady 8ths),
noise = tight drum loop (kick + hat + snare)
**Serves archetype:** combat loop for arena shooter, arcade vertical
shmup, boss-battle fallback

## Motif

D minor pedal with a 4-note chromatic descent motif (D–C#–C–B) that
resolves back to D each bar. Triangle walks 8th notes on roots;
noise plays a hi-hat 8ths pattern with snare hits on beats 2 and 4.
Pulse 2 doubles pulse 1 down an octave — only in choruses (bars 5-8)
to mark intensity rise.

## JSON (placeholder shape)

```json
{
  "bpm": 140,
  "channels": {
    "pulse1": [
      { "time": 0.00, "note": "D5",  "duration": 0.21 },
      { "time": 0.21, "note": "C#5", "duration": 0.21 },
      { "time": 0.43, "note": "C5",  "duration": 0.21 },
      { "time": 0.64, "note": "B4",  "duration": 0.21 },
      { "time": 0.86, "note": "D5",  "duration": 0.21 },
      { "time": 1.07, "note": "F5",  "duration": 0.21 },
      { "time": 1.29, "note": "D5",  "duration": 0.21 },
      { "time": 1.50, "note": "A4",  "duration": 0.21 }
    ],
    "triangle": [
      { "time": 0.00, "note": "D2", "duration": 0.21 },
      { "time": 0.21, "note": "D2", "duration": 0.21 },
      { "time": 0.43, "note": "D2", "duration": 0.21 },
      { "time": 0.64, "note": "D2", "duration": 0.21 },
      { "time": 0.86, "note": "F2", "duration": 0.21 },
      { "time": 1.07, "note": "F2", "duration": 0.21 },
      { "time": 1.29, "note": "A2", "duration": 0.21 },
      { "time": 1.50, "note": "A2", "duration": 0.21 }
    ],
    "noise": [
      { "time": 0.00, "note": "kick",  "duration": 0.10, "velocity": 0.9 },
      { "time": 0.21, "note": "hat",   "duration": 0.05, "velocity": 0.3 },
      { "time": 0.43, "note": "snare", "duration": 0.12, "velocity": 0.8 },
      { "time": 0.64, "note": "hat",   "duration": 0.05, "velocity": 0.3 },
      { "time": 0.86, "note": "kick",  "duration": 0.10, "velocity": 0.9 },
      { "time": 1.07, "note": "hat",   "duration": 0.05, "velocity": 0.3 },
      { "time": 1.29, "note": "snare", "duration": 0.12, "velocity": 0.8 },
      { "time": 1.50, "note": "hat",   "duration": 0.05, "velocity": 0.3 }
    ]
  },
  "loop": true
}
```

Bars 1-2 shown; bars 3-8 repeat the pattern with slight variations
(pulse1 phrase inverts in bar 4, pulse2 joins at bar 5).

**Implementation notes:**
- "kick" / "hat" / "snare" as note names on noise channel are a
  convention the synthesis thread's chipsynth should map to
  appropriate noise-generator configurations (period length, envelope).
  If that's not in their spec, fall back to pitch-based noise with
  three preset periods.
- Syncopation and swing feel rely on exact timing — if the chipsynth
  quantizes to a coarse grid, this track loses its groove.
