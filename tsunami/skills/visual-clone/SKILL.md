# Clone a visual reference

For "looks like X / clone Y / style of Z" prompts where the user wants to match a specific visual layout.

## When
- User says "looks like", "clone of", "style of", "matches", "mimic"
- User provides a screenshot path (e.g., `/tmp/ref.png`) OR mentions a well-known site
- User provides a generated reference path (after `generate_image` returned one)

## Pipeline
1. If no reference image yet:
   - `search_web(query="<site name> homepage layout reference")` — find layout descriptions
   - OR `generate_image(path="/tmp/ref.png", prompt=<concrete visual description>)` — synthesize a reference
2. `riptide(image_path=<path>, focus="<comma-separated UI elements to locate>")` — get bbox positions as percentages
3. `project_init(name=<kebab-case-clone-name>)` — usually `<base>-clone` or `<base>-style`
4. `file_write(path="workspace/deliverables/<name>/src/layout.css", content=<CSS using the bbox %s as position:absolute left/top/width/height>)`
5. `file_write(path="workspace/deliverables/<name>/src/App.tsx", content=<JSX that uses the layout classes>)`
6. `shell_exec("cd workspace/deliverables/<name> && npm run build")`
7. `undertow(path=..., expect="layout matches reference: <key elements + positions>")`
8. If undertow says positions are off → `file_edit` the layout.css percentages, rebuild
9. `message_result(text="<name> verified: layout matches reference percentages.", attachments=[dist/index.html])`

## Gotchas
- **`riptide` BEFORE `project_init`.** You need the bbox numbers before scaffolding — they shape the layout.css.
- **`focus` is a comma-separated list of UI elements.** Be specific: "screen, A button, B button, D-pad, speaker grille" not "everything".
- **Position values are percentages.** Use them in CSS as `left: 18%; top: 12%; width: 64%; height: 40%` with `position: absolute`.
- If the reference image path doesn't exist → `shell_exec("ls /tmp/*.png")` to find it. Don't ask the user.
