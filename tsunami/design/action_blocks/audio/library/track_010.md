# Track 010 — "Pondering" (puzzle theme)

**Shape:** canonical `ChipMusicTrack`.
**Mood:** contemplative, curious, major-with-suspensions, unresolved
**BPM:** 88    **Bars:** 8    **Key:** D major (with pedal 4th)
**Channel layout:** pulse1 = melodic phrase with suspensions, pulse2
= sparse counter (holds 4th + 7th pedals), triangle = walking root,
noise = absent
**Serves archetype:** puzzle-solve, riddle-screen, logic-gate
challenge, Myst-ish mystery. Pairs with PuzzleObject mechanic.

## Motif

Unresolved-suspension pattern: pulse1 lands on 4ths and 7ths before
resolving to nearest scale tone. Creates intellectual "thinking"
tension. Pulse 2 holds pedal tones that color the harmony without
driving to resolution. No drums — thought is quiet.

## JSON

```json
{
  "bpm": 88,
  "loop": true,
  "channels": {
    "pulse1": [
      { "time": 0,    "note": "D5", "duration": 0.75, "dutyCycle": 0.5 },
      { "time": 0.75, "note": "G5", "duration": 0.5 },
      { "time": 1.25, "note": "F#5","duration": 0.75 },
      { "time": 2,    "note": "A5", "duration": 1 },
      { "time": 3,    "note": "D6", "duration": 1 },

      { "time": 4,    "note": "C#6","duration": 0.75 },
      { "time": 4.75, "note": "B5", "duration": 0.5 },
      { "time": 5.25, "note": "A5", "duration": 0.75 },
      { "time": 6,    "note": "G5", "duration": 1 },
      { "time": 7,    "note": "D5", "duration": 1 }
    ],
    "pulse2": [
      { "time": 0,  "note": "G4", "duration": 2, "velocity": 0.5, "dutyCycle": 0.25 },
      { "time": 2,  "note": "A4", "duration": 2, "velocity": 0.5, "dutyCycle": 0.25 },
      { "time": 4,  "note": "F#4","duration": 2, "velocity": 0.5, "dutyCycle": 0.25 },
      { "time": 6,  "note": "A4", "duration": 2, "velocity": 0.5, "dutyCycle": 0.25 }
    ],
    "triangle": [
      { "time": 0, "note": "D3", "duration": 4 },
      { "time": 4, "note": "D3", "duration": 4 }
    ]
  },
  "mixer": { "pulse1": 0.85, "pulse2": 0.5, "triangle": 0.7 }
}
```

**Content note:** 88 BPM is slow enough to think but not sluggish.
Held triangle root (D3 for 4 bars) anchors the listener while harmonic
ambiguity plays above. Pedal-4th pulse2 is the "puzzle chord" that
feels almost-resolved.
