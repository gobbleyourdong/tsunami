# React App Scaffold

Vite + React 19 + TypeScript. Dark theme pre-configured.

## Quick Start
Write your app in `src/App.tsx`. Import `./index.css` for the dark theme.
Build: `npx vite build`

## Available CSS
- Theme vars: `--bg`, `--bg-card`, `--accent`, `--text`, `--text-muted`, `--border`, `--radius`
- Buttons: styled by default, add `.primary` for accent color
- Inputs: styled by default with focus states
- Tables: styled with hover rows
- Layout: `.container`, `.flex`, `.flex-col`, `.grid`, `.grid-2/3/4`, `.gap-2/4/6`
- Spacing: `.mt-4`, `.mb-4`, `.p-4`
- Text: `.text-center`, `.text-muted`
- Cards: `.card` for bordered card containers

## Available UI Components (import from `./components/ui`)
Accordion, Alert, AnimatedCounter, AnnouncementBar, Avatar,
BeforeAfter, ColorPicker, Dialog, Dropdown, GlowCard, GradientText,
Kanban, Marquee, Parallax, Progress, ScrollReveal, Select, Skeleton,
Slideshow, StarRating, Switch, Timeline, Tooltip, TypeWriter

## Rules
- Don't overwrite `main.tsx`, `vite.config.ts`, or `index.css`
- Write your components in `src/components/`
- `App.tsx` is YOUR file — write the full app there
- React hooks (useState, useEffect, etc.) need explicit imports
