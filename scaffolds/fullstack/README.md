# Fullstack Scaffold

Vite + React 19 + Express + SQLite. Local-first CRUD with zero config.

## Quick Start
- Frontend: `src/App.tsx` — write your UI here
- Backend: `server/index.js` — add tables and routes
- Run both: `npm run dev` (uses concurrently)

## API (Express on :3001, proxied through Vite)

### Built-in CRUD
The server has generic CRUD for any table. Default table: `items`.

```
GET    /api/items          — list all
GET    /api/items/:id      — get one
POST   /api/items          — create (body: {name, description, ...})
PUT    /api/items/:id      — update
DELETE /api/items/:id      — delete
GET    /api/health          — health check
```

### Adding tables
In `server/index.js`, add `db.exec(CREATE TABLE...)` then `crudRoutes("tablename")`.

### useApi Hook
```tsx
import { useApi } from './components/useApi'

const { data, loading, error, create, update, remove, refresh } = useApi<Item>("items")
```
Returns: data (T[]), loading (boolean), error (string|null), CRUD functions.

## Vite Proxy
`/api/*` proxied to localhost:3001. No CORS issues.

## Rules
- Don't overwrite `main.tsx`, `vite.config.ts`, or `index.css`
- Backend: `server/index.js`. Frontend: `src/`
- useApi handles loading/error — just use data, loading, error
