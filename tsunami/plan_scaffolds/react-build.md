# Plan: {goal}

## TOC
- [>] [Architecture](#architecture)
- [ ] [Components](#components)
- [ ] [Data](#data)
- [ ] [Tests](#tests)
- [ ] [Build](#build)
- [ ] [Deliver](#deliver)

## Architecture
One-line sketch: what the app does and what screens/sections it has.
Key hooks used (useInterval for timers, useLocalStorage for persistence).

## Components
List each component as:
- **Name** — file path — props — purpose
Compose in src/App.tsx. Use `./components/ui` primitives (Button, Card, Input, Badge, Dialog, Progress, etc.).

## Data
Types and state shape:
- Entity types (shape of each record)
- Where state lives (App.tsx useState / useLocalStorage key)

## Tests
Write src/App.test.tsx: **one behavioral test per interactive element**.
Each test follows a single shape: render → act → assert observable outcome.

For every button / input / keypress in your app, write:
```tsx
test('<action>: <input> → <expected observable state change>', () => {
  render(<App />)
  // act
  fireEvent.click(screen.getByRole('button', { name: /<label>/i }))
  // assert
  expect(<observable selector>).toHaveTextContent(/<expected/)
})
```

Example coverage for a pomodoro:
- `Start button → timer decrements from 25:00`
- `Pause button (while running) → timer stops changing`
- `Reset button → timer returns to 25:00`
- `Input + Enter → new task appears in list`
- `Task complete button → task pomodoro count increments`

Use vitest + @testing-library/react + @testing-library/user-event. Import
`fireEvent`, `screen`, `render`. Tests are the contract — they must pass
for delivery (build script runs `vitest run` after `vite build`).

## Build
shell_exec cd {project_path} && npm run build
(runs tsc + vite build + vitest — all three must pass)

## Deliver
message_result with one-line description.
