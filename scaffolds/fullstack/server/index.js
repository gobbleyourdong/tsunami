import express from "express"
import cors from "cors"
import Database from "better-sqlite3"
import { dirname, join } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const PORT = process.env.PORT || 3001

// SQLite — local-first, no cloud needed
const db = new Database(join(__dirname, "data.db"))
db.pragma("journal_mode = WAL")
db.pragma("foreign_keys = ON")

// Generic items table — replace with your schema
db.exec(`
  CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    data TEXT DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`)

const app = express()
app.use(cors())
app.use(express.json())

// Health check
app.get("/api/health", (req, res) => res.json({ ok: true }))

// Generic CRUD — works with any table via :resource param
// GET /api/items, POST /api/items, PUT /api/items/:id, DELETE /api/items/:id
function crudRoutes(table) {
  const safe = table.replace(/[^a-z_]/gi, "")

  app.get(`/api/${safe}`, (req, res) => {
    try {
      const rows = db.prepare(`SELECT * FROM ${safe} ORDER BY created_at DESC`).all()
      res.json(rows)
    } catch (e) { res.status(500).json({ error: e.message }) }
  })

  app.get(`/api/${safe}/:id`, (req, res) => {
    try {
      const row = db.prepare(`SELECT * FROM ${safe} WHERE id = ?`).get(req.params.id)
      row ? res.json(row) : res.status(404).json({ error: "not found" })
    } catch (e) { res.status(500).json({ error: e.message }) }
  })

  app.post(`/api/${safe}`, (req, res) => {
    try {
      const keys = Object.keys(req.body).filter(k => k !== "id")
      const vals = keys.map(k => typeof req.body[k] === "object" ? JSON.stringify(req.body[k]) : req.body[k])
      const result = db.prepare(
        `INSERT INTO ${safe} (${keys.join(",")}) VALUES (${keys.map(() => "?").join(",")})`
      ).run(...vals)
      res.json({ id: result.lastInsertRowid })
    } catch (e) { res.status(500).json({ error: e.message }) }
  })

  app.put(`/api/${safe}/:id`, (req, res) => {
    try {
      const keys = Object.keys(req.body).filter(k => k !== "id")
      const vals = keys.map(k => typeof req.body[k] === "object" ? JSON.stringify(req.body[k]) : req.body[k])
      db.prepare(
        `UPDATE ${safe} SET ${keys.map(k => `${k}=?`).join(",")}, updated_at=CURRENT_TIMESTAMP WHERE id=?`
      ).run(...vals, req.params.id)
      res.json({ ok: true })
    } catch (e) { res.status(500).json({ error: e.message }) }
  })

  app.delete(`/api/${safe}/:id`, (req, res) => {
    try {
      db.prepare(`DELETE FROM ${safe} WHERE id = ?`).run(req.params.id)
      res.json({ ok: true })
    } catch (e) { res.status(500).json({ error: e.message }) }
  })
}

// Register CRUD for items (add more tables here)
crudRoutes("items")

app.listen(PORT, () => console.log(`API: http://localhost:${PORT}`))
