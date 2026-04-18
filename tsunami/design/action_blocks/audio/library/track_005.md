# Track 005 — "Approach" (boss theme)

**Shape:** canonical `ChipMusicTrack` per synthesis attempt_001 §2.
**Mood tags:** menacing, driving, minor, tension-without-resolution
**BPM:** 150    **Bars:** 8    **Key:** E minor
**Channel layout:** pulse1 = aggressive chromatic lead with 12.5% duty,
pulse2 = pulsing octave drone (tension), triangle = descending
bass walk, noise = tight kick-snare-hat drum line
**Serves archetype:** boss battle, Robot Master encounter, Castlevania
castle master, any "stop-and-fight-the-big-one" moment

## Motif

4-bar riff in E minor that resolves ambiguously (hangs on a 4th rather
than the tonic). Pulse 1 uses chromatic passing tones to feel unstable.
Triangle walks a 4-note chromatic descent (E–Eb–D–Db). Noise drums
hit on every beat + syncopated 16ths.

## JSON

```json
{
  "bpm": 150,
  "loop": true,
  "channels": {
    "pulse1": [
      { "time": 0,    "note": "E5",  "duration": 0.5, "dutyCycle": 0.125 },
      { "time": 0.5,  "note": "G5",  "duration": 0.5, "dutyCycle": 0.125 },
      { "time": 1,    "note": "B5",  "duration": 0.5, "dutyCycle": 0.125 },
      { "time": 1.5,  "note": "A#5", "duration": 0.5, "dutyCycle": 0.125 },
      { "time": 2,    "note": "A5",  "duration": 0.5, "dutyCycle": 0.125 },
      { "time": 2.5,  "note": "G5",  "duration": 0.5, "dutyCycle": 0.125 },
      { "time": 3,    "note": "E5",  "duration": 0.5, "dutyCycle": 0.125 },
      { "time": 3.5,  "note": "B4",  "duration": 0.5, "dutyCycle": 0.125 },

      { "time": 4,    "note": "E5",  "duration": 0.5, "dutyCycle": 0.125 },
      { "time": 4.5,  "note": "A5",  "duration": 0.5, "dutyCycle": 0.125 },
      { "time": 5,    "note": "G5",  "duration": 0.5, "dutyCycle": 0.125 },
      { "time": 5.5,  "note": "F#5", "duration": 0.5, "dutyCycle": 0.125 },
      { "time": 6,    "note": "E5",  "duration": 1,   "dutyCycle": 0.125 },
      { "time": 7,    "note": "A4",  "duration": 1,   "dutyCycle": 0.125 }
    ],
    "pulse2": [
      { "time": 0, "note": "E3", "duration": 0.5 },
      { "time": 1, "note": "E3", "duration": 0.5 },
      { "time": 2, "note": "E3", "duration": 0.5 },
      { "time": 3, "note": "E3", "duration": 0.5 },
      { "time": 4, "note": "E3", "duration": 0.5 },
      { "time": 5, "note": "E3", "duration": 0.5 },
      { "time": 6, "note": "E3", "duration": 0.5 },
      { "time": 7, "note": "E3", "duration": 0.5 }
    ],
    "triangle": [
      { "time": 0, "note": "E2",  "duration": 2 },
      { "time": 2, "note": "D#2", "duration": 2 },
      { "time": 4, "note": "D2",  "duration": 2 },
      { "time": 6, "note": "C#2", "duration": 2 }
    ],
    "noise": [
      { "time": 0,    "note": "kick",  "duration": 0.15, "velocity": 0.95 },
      { "time": 0.5,  "note": "hat_closed", "duration": 0.1 },
      { "time": 1,    "note": "snare", "duration": 0.15, "velocity": 0.85 },
      { "time": 1.5,  "note": "hat_closed", "duration": 0.1 },
      { "time": 2,    "note": "kick",  "duration": 0.15, "velocity": 0.95 },
      { "time": 2.25, "note": "kick",  "duration": 0.1,  "velocity": 0.7 },
      { "time": 2.5,  "note": "hat_closed", "duration": 0.1 },
      { "time": 3,    "note": "snare", "duration": 0.15, "velocity": 0.85 },
      { "time": 3.5,  "note": "hat_open",   "duration": 0.2 }
    ]
  },
  "mixer": { "pulse1": 1.0, "pulse2": 0.4, "triangle": 0.8, "noise": 0.7 }
}
```

Bars 1-4 shown (half of loop). Bars 5-8 repeat with triangle-bass
rising back to E (completing the E–Eb–D–Db–E loop signature).

**Content note:** 12.5% duty cycle on pulse1 gives the characteristic
"thin/piercing" boss-lead sound. Pulse 2 as E3 pedal pumping 8ths
creates tension. This is the "Pressure" archetype from track_002 but
tighter and more chromatic — boss-specific, not generic combat.
