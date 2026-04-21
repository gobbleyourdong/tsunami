# mobile/chat

**Pitch:** PWA chat scaffold — installable web app, works offline, ships
from any static host. Not Expo / React Native; no native toolchain
needed. Opens at iOS/Android home-screen size, `env(safe-area-inset-*)`
respected, hooks up to a service worker for cache-first static assets.

## Quick start

```bash
npm install
npm run dev                    # localhost:5180
# On an iPhone / Android device:
npm run build && npx serve dist
# then open the served URL on your phone → Add to Home Screen
```

## Structure

| Path | What |
|------|------|
| `public/manifest.json`     | PWA manifest (name, icons, theme color) |
| `src/sw.ts`                | Service worker — cache-first for /, /assets, manifest; network-first for everything else |
| `src/lib/sw-register.ts`   | Registers the SW after page load                         |
| `src/lib/chat-store.ts`    | External-store message log with localStorage persistence  |
| `src/components/`          | MessageList, Composer, OfflineBanner                      |

## Swap the transport

`chat-store.ts::sendMessage` currently echoes replies locally. For a
real backend, replace that `setTimeout` call with your WebSocket /
fetch / SSE wiring. The store shape (array of `{id, body, sender, sent_at}`)
is stable — components don't care where messages come from.

For WebSocket:

```ts
// in chat-store.ts, replace the setTimeout echo with:
const ws = new WebSocket(import.meta.env.VITE_WS_URL)
ws.onmessage = (e) => receiveMessage(JSON.parse(e.data).body)
// and in sendMessage: ws.send(JSON.stringify(msg))
```

## Don't

- Don't cache API responses in the service worker's static list — mix
  up network-first on API paths (the SW already does this)
- Don't forget to bump `CACHE_VERSION` when changing the static list,
  otherwise stale cache pins users to the old shell
- Don't use `cache-only` for HTML — users will never see new deploys

## Anchors

`iMessage`, `Signal`, `Telegram Web`, `WhatsApp Web`, `Discord mobile`.
