# Plan: {goal}

Electron desktop app — main process + preload + renderer (React SPA).
Vision gate doesn't apply (gate fires against the renderer SPA's dist
via the standard vision flow IF the renderer ships to `dist/`).
Electron-specific delivery gate: `tsunami.core.electron_probe` —
checks build output, main-process entry, and flags `nodeIntegration:
true` / `contextIsolation: false` in the renderer config.

## TOC
- [>] [Main](#main)
- [ ] [Preload](#preload)
- [ ] [Renderer](#renderer)
- [ ] [IPC](#ipc)
- [ ] [Build](#build)
- [ ] [Deliver](#deliver)

## Main
`electron/main.ts` — creates the `BrowserWindow`. Non-negotiable
config (the gate rejects anything else):

```ts
new BrowserWindow({
  width: 1024, height: 768,
  webPreferences: {
    preload: path.join(__dirname, 'preload.js'),
    contextIsolation: true,     // REQUIRED
    nodeIntegration: false,     // REQUIRED
    sandbox: true,              // recommended
  },
})
```

Load `file://<dist>/index.html` in production, `http://localhost:5173`
in dev (read `app.isPackaged` to pick). Handle `before-quit`,
`second-instance`, and `activate` for macOS dock behaviour.

## Preload
`electron/preload.ts` — the ONLY bridge between Node and the renderer.
Expose a narrow surface via `contextBridge.exposeInMainWorld`:

```ts
contextBridge.exposeInMainWorld('api', {
  readFile: (path: string) => ipcRenderer.invoke('fs:read', path),
  saveSettings: (x) => ipcRenderer.invoke('settings:save', x),
})
```

No `ipcRenderer.send`-style fire-and-forget from the renderer — always
`invoke` with a typed return. TypeScript types for the exposed API
live in `src/types/electron.d.ts` and declare `window.api` globally.

## Renderer
`src/App.tsx` — normal React app. Reaches the main process only via
`window.api.*`. Never `require('fs')` or `process.*` — those won't
exist with contextIsolation:true (and the gate would flag relaxing
that).

## IPC
Every handler lives in `electron/main.ts` under a namespace:

```ts
ipcMain.handle('fs:read', async (_e, p) => fs.promises.readFile(p, 'utf-8'))
ipcMain.handle('settings:save', async (_e, obj) => store.set(obj))
```

Validate all inputs — treat the renderer as untrusted input (it can
load remote URLs or be compromised by a redirect). Never interpolate
renderer input into shell commands.

## Build
shell_exec cd {project_path} && npm run build

Must produce: `dist/main.js` (or whatever `package.json.main` points
at), `dist/preload.js`, and the renderer SPA bundle. The gate does
not run `electron-builder` (no GUI, no platform packaging) — it
verifies the artifacts and scans main/preload source for the two
security anti-patterns above.

## Deliver
`message_result` with a one-line description. A pass means build
succeeded + every declared entry exists + no v1-security smells.
Actual window-launch QA is deferred to a future playwright-electron
gate (see `electron_probe.py` docstring).
