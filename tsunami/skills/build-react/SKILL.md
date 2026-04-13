# Build a React app from a scaffold

The scaffold is a foundation, not a final product. Map the request, read what's there, then refine incrementally.

## When
- User says "build", "make", "create", or "I need a/an" + an app name
- The app does not already exist in `deliverables/`
- Default if the prompt doesn't match `iteration`, `in-place-cwd`, or `visual-clone`

## Pipeline (incremental, not one-shot)

### 1. Scaffold
`project_init(name)` — kebab-case from prompt. The scaffold output tells you what template was picked (react-app / dashboard / data-viz / landing / game / etc) and what's already in `src/`.

### 2. Map requirements against scaffold defaults
- Missing components? (e.g. user asked for a pricing table, scaffold only has a hero) → plan to add them
- Data needs? (list of items, form state) → plan the state shape
- Styling? (dark theme, specific brand colors) → plan CSS variable overrides

### 3. Read the scaffold entry point
`file_read(path="deliverables/<name>/src/App.tsx")` — see what placeholder/example code is there. The scaffold ships with stub content like `<div>Loading...</div>` or a sample hero. You need to know what's there before overwriting.

### 4. Replace, don't append
`file_write(path="deliverables/<name>/src/App.tsx", content=<COMPLETE TSX>)` — overwrite the placeholder with the real implementation. Full code, no `// TODO`, no `// Phase 1` comments. One file_write should produce a working app for most simple cases (counter, todo, calc, clock, dice, color picker).

### 5. Compile
`shell_exec("cd deliverables/<name> && npm run build")` — must compile clean. If it fails → switch to `build-recovery`.

### 6. QA
`undertow(path="deliverables/<name>/dist/index.html", expect="<plain-language description of what should render>")`. If FAIL → switch to `qa-loop`.

### 7. Deliver
`message_result(text="<one-line summary>", attachments=["deliverables/<name>/dist/index.html"])`

## Decomposition for larger apps (>200 LOC)
After reading the scaffold (step 3), if the app is genuinely modular:
1. `file_write` shared types → `src/types.ts`
2. `file_write` each component → `src/components/<Name>.tsx`
3. `file_write` App.tsx that imports them
4. Then build / undertow / deliver as above

Don't decompose for simple apps — one App.tsx is more reliable than 4 files for a counter.

## Gotchas
- **No narration.** Every assistant turn is exactly one tool call, no `content` text.
- **`import "./index.css"` at the top of App.tsx.** The scaffold provides base styles.
- **Use scaffold component classes** — `.container .card .button .button.primary .grid .grid-3 .flex .flex-col .flex-center .gap-4 .p-8 .text-bold .text-2xl .text-muted` — not inline styles for layout.
- **Never `dangerouslySetInnerHTML`** unless the user explicitly asked for HTML/markdown rendering.
- **Always provide `expect` to undertow** — describe what should render, not the implementation.
- **Cleanup before adding.** If the scaffold has a "Welcome to React" header, remove it first; don't paste your content underneath it.
