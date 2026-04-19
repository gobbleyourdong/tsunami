# Plan: {goal}

Compositional replica plan — build an inner app inside a outer visual
shell. The outer shell constrains layout; the inner app is a sub-
application using standard scaffold primitives, scoped to a region
of the shell (e.g. pomodoro timer INSIDE an Apple Watch screen area).
Same structure as a mini-game inside a game.

## TOC
- [>] [OuterShell](#outershell)
- [ ] [InnerApp](#innerapp)
- [ ] [Grounding](#grounding)
- [ ] [Layout](#layout)
- [ ] [Content](#content)
- [ ] [Build](#build)
- [ ] [VisionCompare](#visioncompare)
- [ ] [Deliver](#deliver)

## OuterShell
The visual container the replica emulates.
- What product: Apple Watch, iPhone Calendar, Spotify, etc.
- Which element is the "screen" (the interactive region inside the
  shell — e.g. watch display, phone screen, car dashboard)
- Chrome elements (bezel, status bar, crown, home button)
- Container aspect ratio + approximate pixel dimensions

## InnerApp
The sub-application that lives INSIDE the outer shell's screen region.
- What it does (pomodoro timer, note-taker, mini-game)
- Features required (start/pause/reset, task list, etc.)
- Constraints imposed by the outer shell's screen size
  (e.g. watch = ~200x250px — no room for side-by-side buttons,
   everything must stack vertically and be ≥44px tappable)

## Reference
Acquire the reference image that defines the visual target.
- search_web type="image" with the style keywords from the task
  (e.g. "apple watch face", "iOS Calendar app", "Spotify now playing")
- OR generate_image with a detailed prompt describing the target
- Save as `src/reference.png` (so the drone can re-read it and riptide
  can see it)

## Grounding
Run riptide on the reference image. Returns bounding boxes as
percentages for each named UI element.
- Pass a list of elements the task needs, e.g.:
    ["bezel", "timer display", "Start button", "Pause button",
     "Reset button", "task list area"]
- Save output to `src/reference.md` as a grounded-position table

## Layout
Write `src/layout.css` from the riptide percentages:
- Container has `position: relative` + fixed aspect ratio matching the
  reference (Apple Watch ~= 1:1.25 portrait, 320x400)
- Each element class has `position: absolute` + top/left/width/height
  in percentages (directly from riptide)
- NO magic numbers from the task description — only from riptide output

## Content
Write `src/App.tsx`:
- Import `./layout.css` in addition to `./index.css`
- Compose elements inside `<div className="device-body">` wrapping
- Each interactive/display element gets the corresponding layout class
- Apply functional logic on top (onClick, useState, useInterval timer)
- Use scaffold UI primitives for interactive widgets (Button, Input)
  styled via layout.css positioning

## Build
shell_exec cd {project_path} && npm run build
(tsc + vite + vitest — all three must pass)

## VisionCompare
Delivery-time vision gate receives BOTH the built dist screenshot AND
the reference image. VLM judges whether they match on:
- Layout fidelity (elements in the right positions)
- Proportions (sizes match the reference)
- Visual style (colors, typography match the target product)
- Completeness (all task-required elements present)

Issues flagged here are replica-specific — the drone fixes via
layout.css tweaks, not a full rewrite.

## Deliver
message_result with a one-line description of the replicated UI.
