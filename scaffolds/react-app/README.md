# React App Template

React 19 + TypeScript + Vite. Dark theme pre-configured.

## Build Loop

1. Write types in `src/types.ts` — shared interfaces for your domain
2. Write components in `src/components/` — one per file, under 100 lines
3. Write `src/App.tsx` LAST — import and wire all components
4. Run `npx vite build` to compile-check. Fix any errors.
5. Dev server auto-starts on port 9876 with HMR.

## File Structure

```
src/
  App.tsx          ← Main app — import and wire your components here
  main.tsx         ← Entry point (don't edit)
  index.css        ← Base dark theme + CSS utilities (don't edit)
  types.ts         ← Your domain interfaces
  components/      ← Your components (one per file)
```

## Available CSS

The base theme in `index.css` styles everything automatically:
- Dark background (#0f0f1a), light text
- Buttons, inputs, tables, links all styled
- Scrollbars themed

CSS utility classes (use via `className`):
- `.container` — centered max-width container with padding
- `.card` — dark card with border and rounded corners
- `.grid` `.grid-2` `.grid-3` `.grid-4` — CSS grid layouts
- `.flex` — flexbox
- `.gap-2` `.gap-4` `.gap-6` — gap spacing
- `.text-center` `.text-muted` — text alignment and color
- `.mt-4` `.mb-4` `.p-4` — margin and padding

## Tips

- Every `<button>` looks good automatically — no need for custom styling
- Every `<input>` and `<table>` are themed
- Use `className="card"` for panels/cards
- Use `className="grid grid-4 gap-4"` for grid layouts
- Use `className="container"` to center content
