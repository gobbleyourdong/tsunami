# iso_cache_poc — render-time pixel cache demo

Self-contained HTML demo proving the prebaked-buffer rendering model.
No build step. Serve the directory and open in a browser:

```
python3 -m http.server 9123
```

Then visit `http://localhost:9123/object_buffer_cache.html`.

## What the demo proves

Each `GameObject` owns a triple buffer (color, depth, normal) baked
**once** by the SDF at init. Per-frame work is pure `drawImage`.
Transforms (translate, rotate, camera pan) never touch the buffer.
Only objects flagged `deform_full` or `deform_local` emit
cache-update events.

Watch the canvas HUD: **SDF evals this frame** stays at 0 in steady
state — no matter how fast the camera pans, how many objects are on
screen, or how the critter/fan animate. Toggle the heart pulse or
gear teeth to see the only re-bakes that actually fire.

See `../SDF_PIXEL_PRIMITIVES.md` § "Cache architecture" for the doc
backing this demo.

## Animation-flag taxonomy

| Flag | Per-frame work | Bake events |
|---|---|---|
| `static` | drawImage | once at init |
| `translate` | drawImage | once at init (motion is independent of flag) |
| `rotate` | drawImage with ctx.rotate | once at init |
| `loop` | drawImage(loopBuffers[loopTick % N]) | **N at init, then never.** Max 8 frames; all loops advance on one global tick. |
| `deform_full` | drawImage | per cache-update tick (whole buffer) |
| `deform_local` | drawImage | per cache-update tick (sub-rect(s) only) |

Cosmetic effects (palette cycling, sway, rim-light, damage-flash) run
at composite time over the prebaked buffers and are NOT bake events.
