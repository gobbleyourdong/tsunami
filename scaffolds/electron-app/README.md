# Electron App Scaffold

Desktop application with Electron + React + TypeScript + Vite.

## Structure
```
main.ts           — Electron main process (BrowserWindow, IPC handlers)
preload.ts        — Context bridge (safe API exposure to renderer)
src/
  App.tsx         — React renderer with IPC hooks
  hooks/useIPC.ts — useIPC hook (type-safe IPC from React)
  index.css       — App styles
  main.tsx        — React entry point
```

## Development
```bash
npm install
npm run dev              # Vite dev server (browser preview)
npm run electron:dev     # Full Electron + Vite hot reload
```

## Packaging
```bash
npm run electron:build   # Build + package with electron-builder
```
Output goes to `release/`.

## IPC Pattern
```tsx
// In React (renderer):
const { invoke } = useIPC();
const content = await invoke('read-file', '/path/to/file');

// In main.ts (main process):
ipcMain.handle('read-file', async (_event, filePath) => {
  return fs.readFile(filePath, 'utf-8');
});
```

The `useIPC` hook falls back gracefully in browser mode (vite dev without Electron).
