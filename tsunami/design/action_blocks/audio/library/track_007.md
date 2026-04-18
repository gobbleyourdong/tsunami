# Track 007 — "Idle Hum" (menu loop)

**Shape:** canonical `ChipMusicTrack`.
**Mood:** unobtrusive, minor-with-tension-unresolved, low-energy
**BPM:** 90    **Bars:** 8    **Key:** A minor
**Channel layout:** pulse1 = sparse high melodic fragments (every 4
beats), triangle = held root drone, noise = absent
**Serves archetype:** title-screen-idle, pause-menu, inventory,
settings, cutscene-subdued-backdrop. Designed to NOT interrupt
thought.

## Motif

Held A2 on triangle for 8 full bars. Pulse 1 plays an occasional
ornament — a 3-note figure every 4 beats (bar-line). Pulse 2 absent.
Noise absent. This is **negative-space audio** — what's NOT playing
creates the mood.

## JSON

```json
{
  "bpm": 90,
  "loop": true,
  "channels": {
    "pulse1": [
      { "time": 0,  "note": "E5", "duration": 0.25, "velocity": 0.4 },
      { "time": 0.5, "note": "A5", "duration": 0.5, "velocity": 0.35 },
      { "time": 4,  "note": "D5", "duration": 0.25, "velocity": 0.4 },
      { "time": 4.5, "note": "A5", "duration": 0.5, "velocity": 0.35 },
      { "time": 8,  "note": "E5", "duration": 0.25, "velocity": 0.4 },
      { "time": 8.5, "note": "G5", "duration": 0.5, "velocity": 0.35 },
      { "time": 12, "note": "D5", "duration": 0.25, "velocity": 0.4 },
      { "time": 12.5, "note": "A5", "duration": 1.5, "velocity": 0.3 },
      { "time": 16, "note": "E5", "duration": 0.25, "velocity": 0.4 },
      { "time": 16.5, "note": "A5", "duration": 0.5, "velocity": 0.35 },
      { "time": 20, "note": "D5", "duration": 0.25, "velocity": 0.4 },
      { "time": 20.5, "note": "A5", "duration": 0.5, "velocity": 0.35 },
      { "time": 24, "note": "E5", "duration": 0.25, "velocity": 0.4 },
      { "time": 24.5, "note": "G5", "duration": 0.5, "velocity": 0.35 },
      { "time": 28, "note": "D5", "duration": 0.25, "velocity": 0.4 },
      { "time": 28.5, "note": "A5", "duration": 1.5, "velocity": 0.3 }
    ],
    "triangle": [
      { "time": 0, "note": "A2", "duration": 32 }
    ]
  },
  "mixer": { "pulse1": 0.4, "triangle": 0.6 }
}
```

**Content note:** long-held triangle + sparse pulse fragments = Dark
Souls-bonfire-ish atmosphere. Can run indefinitely in menu without
fatigue. 8 bars × 4 beats = 32 beats. Loop seamlessly.

Low velocity (0.3-0.4) keeps everything in the background. This is
a **palette demonstrator** for "quiet / contemplative" mood —
achievable with minimal note events.
