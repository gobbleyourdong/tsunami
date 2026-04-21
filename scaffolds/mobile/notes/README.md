# mobile/notes

**Pitch:** PWA notes scaffold — installable, works offline, localStorage
persistence. Sister scaffold to `mobile/chat` — same PWA infrastructure
(service worker, manifest, safe-area insets), different domain.

## Quick start

```bash
npm install
npm run dev        # localhost:5181
```

## Structure

| Path | What |
|------|------|
| `public/manifest.json`     | PWA manifest                                |
| `src/sw.ts`                | Cache-first static, network-first for rest  |
| `src/lib/notes-store.ts`   | External-store + localStorage persistence   |
| `src/components/`          | NoteList (newest-first) + NoteEditor (autosave 350ms debounce) |

## Add sync across devices

The scaffold is local-only — `notes-store.ts` writes to localStorage
and never hits a network. For cross-device sync, replace the internal
state mutations with an ops queue that streams to your backend:

```ts
// in notes-store.ts, wrap each mutation:
export function updateNote(id, patch) {
  // ... local update
  pushOp({ type: "update", id, patch })  // add this
}
```

A `remote-sync.ts` module can drain `pushOp()` to a backend, handle
conflict resolution (last-write-wins on updated_at is fine for notes),
and subscribe to server updates via WebSocket / SSE.

## Don't

- Don't serialize the whole state on every keystroke without a debounce
  — the autosave already waits 350ms. localStorage.setItem is
  synchronous, blocks paint.
- Don't store secrets (api keys, tokens) in localStorage — it's
  visible to every script on the origin. Use cookies with HttpOnly
  or the Credentials API.

## Anchors

`Apple Notes`, `Bear`, `Simplenote`, `Standard Notes`, `Obsidian sync`.
