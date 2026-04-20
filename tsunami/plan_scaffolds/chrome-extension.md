# Plan: {goal}

Chrome MV3 extension. Popup + optional content script + optional
service-worker background. No React app shell — this is a browser
extension, not a webpage. Vision gate doesn't apply; delivery is
gated by `tsunami.core.extension_probe` (static manifest + bundle
check — no browser launch required for the core gate).

## TOC
- [>] [Manifest](#manifest)
- [ ] [Popup](#popup)
- [ ] [Content / Background](#content--background)
- [ ] [Permissions](#permissions)
- [ ] [Build](#build)
- [ ] [Deliver](#deliver)

## Manifest
Write `public/manifest.json` (vite copies it into `dist/`):

```json
{
  "manifest_version": 3,
  "name": "...", "version": "1.0.0", "description": "...",
  "action": { "default_popup": "popup.html", "default_icon": {...} },
  "background": { "service_worker": "background.js", "type": "module" },
  "content_scripts": [{
    "matches": ["<url-pattern>"],
    "js": ["content.js"]
  }],
  "permissions": [],
  "host_permissions": []
}
```

Forbidden v2 fields — the probe rejects any of these:
- `background.scripts` / `background.persistent` (v3 uses `service_worker`)
- `browser_action` / `page_action` (collapsed into `action`)
- bare-string `web_accessible_resources` (v3 wants `{resources, matches}` objects)

Every file the manifest names MUST exist in `dist/` post-build. That's
the #1 reason extensions silently fail to load.

## Popup
`src/popup.tsx` — small (≤400px wide) React root. Self-contained: no
router, no global state unless it's `chrome.storage`. Bundle via Vite
with `@crxjs/vite-plugin` or equivalent MV3 helper. The popup is just
an HTML page with a React entry — keep it single-file unless the task
genuinely needs a second view.

## Content / Background
- Content script: runs in the page. DOM-manipulation, scraping,
  `chrome.runtime.sendMessage` to the service worker. Keep pure DOM;
  no React (avoid 150 KB bundle per page).
- Service worker: the event hub. `chrome.runtime.onMessage`,
  `chrome.action.onClicked`, alarms. v3 workers are non-persistent —
  don't hold state in module globals, use `chrome.storage.session`.

## Permissions
Ask for the narrowest set. `tabs` / `activeTab` / `storage` cover
most drone tasks. `<all_urls>` requires justification — split
patterns into explicit `host_permissions`.

## Build
shell_exec cd {project_path} && npm run build

Must emit `dist/manifest.json` + every file it references. The gate
also flags bundles <32 bytes (empty esbuild emit, which silently
breaks extensions).

## Deliver
`message_result` with a one-line description. The gate reads the
built `dist/manifest.json`, validates v3 shape, confirms all
referenced files exist, flags v2-only fields. Passing this is
sufficient for delivery — playwright-load-unpacked is a future
extension (see `core.extension_probe` docstring).
