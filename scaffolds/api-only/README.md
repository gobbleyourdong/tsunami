# API-Only Scaffold

Express + SQLite. No frontend, just a REST API.

## Quick Start
`npm run dev` — starts server with auto-reload on :3001

## Endpoints (auto-generated CRUD)
```
GET    /items          — list all
GET    /items/:id      — get one
POST   /items          — create
PUT    /items/:id      — update
DELETE /items/:id      — delete
GET    /health         — health check
```

## Adding tables
In server/index.js: add `db.exec(CREATE TABLE...)` then `crud("tablename")`.

## Testing
```bash
curl http://localhost:3001/items
curl -X POST http://localhost:3001/items -H "Content-Type: application/json" -d '{"name":"test"}'
```
