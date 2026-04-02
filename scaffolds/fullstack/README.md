# Fullstack Template

React 19 + TypeScript + Vite + Express 5 + SQLite. Local-first, no cloud needed.

## Pre-built Components

Import from `./components`:
- `useApi(resource)` — CRUD helpers: `.list()`, `.get(id)`, `.create(data)`, `.update(id, data)`, `.remove(id)`

Backend (server/index.js):
- Express API on port 3001
- SQLite database (WAL mode, auto-created)
- CRUD endpoints for `items` table (GET/POST/PUT/DELETE)
- CORS enabled

## Build Loop

1. Edit `server/index.js` — add your database tables and API routes
2. Write types in `src/types.ts`
3. Use `useApi` hook in components to call the API
4. Wire in `src/App.tsx`
5. Start both: `npm run dev` (runs Vite + server concurrently)

## Usage Example

```tsx
import { useApi } from "./components"
import { useEffect, useState } from "react"

function TodoList() {
  const api = useApi("items")
  const [items, setItems] = useState([])

  useEffect(() => { api.list().then(setItems) }, [])

  const addItem = async (name) => {
    await api.create({ name })
    setItems(await api.list())
  }

  return items.map(item => <div key={item.id}>{item.name}</div>)
}
```

## File Structure

```
src/
  App.tsx              ← Wire your frontend here
  types.ts             ← Your domain interfaces
  components/
    useApi.ts           ← CRUD API hook (ready to use)
    index.ts            ← Barrel exports
server/
  index.js             ← Express API + SQLite (edit this)
```

## API Endpoints (default)

- `GET /api/items` — list all items
- `POST /api/items` — create item `{ name, data }`
- `PUT /api/items/:id` — update item
- `DELETE /api/items/:id` — delete item

Add your own routes by following the same pattern in `server/index.js`.
