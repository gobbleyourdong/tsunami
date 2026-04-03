# Chrome Extension Scaffold

React + TypeScript Chrome Extension (Manifest V3) with Vite + CRXJS hot reload.

## Structure
```
src/
  popup/        — React popup UI (App.tsx + main.tsx)
  content/      — Content script (injected into pages)
  background/   — Service worker (persistent background)
  index.css     — Shared styles
public/
  manifest.json — Extension manifest (MV3)
```

## Development
```bash
npm install
npm run dev     # Vite dev server with CRXJS hot reload
```

## Load in Chrome
1. `npm run build`
2. Open `chrome://extensions`
3. Enable **Developer mode**
4. Click **Load unpacked** → select the `dist/` folder

## Key APIs
- `chrome.storage.local` — persist data across sessions
- `chrome.tabs` — query/modify browser tabs
- `chrome.runtime.onMessage` — messaging between popup/content/background
- `chrome.action` — control the extension icon and badge
