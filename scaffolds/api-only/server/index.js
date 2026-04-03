import express from "express"
import cors from "cors"
import Database from "better-sqlite3"
import { dirname, join } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const PORT = process.env.PORT || 3001

const db = new Database(join(__dirname, "data.db"))
db.pragma("journal_mode = WAL")
db.pragma("foreign_keys = ON")

// Schema — replace with your tables
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

// Health
app.get("/health", (req, res) => res.json({ ok: true }))

// Generic CRUD factory
function crud(table) {
  const safe = table.replace(/[^a-z_]/gi, "")

  app.get(`/${safe}`, (req, res) => {
    const rows = db.prepare(`SELECT * FROM ${safe} ORDER BY created_at DESC`).all()
    res.json(rows)
  })

  app.get(`/${safe}/:id`, (req, res) => {
    const row = db.prepare(`SELECT * FROM ${safe} WHERE id = ?`).get(req.params.id)
    row ? res.json(row) : res.status(404).json({ error: "not found" })
  })

  app.post(`/${safe}`, (req, res) => {
    const keys = Object.keys(req.body).filter(k => k !== "id")
    const vals = keys.map(k => typeof req.body[k] === "object" ? JSON.stringify(req.body[k]) : req.body[k])
    const result = db.prepare(
      `INSERT INTO ${safe} (${keys.join(",")}) VALUES (${keys.map(() => "?").join(",")})`
    ).run(...vals)
    res.status(201).json({ id: result.lastInsertRowid })
  })

  app.put(`/${safe}/:id`, (req, res) => {
    const keys = Object.keys(req.body).filter(k => k !== "id")
    const vals = keys.map(k => typeof req.body[k] === "object" ? JSON.stringify(req.body[k]) : req.body[k])
    db.prepare(
      `UPDATE ${safe} SET ${keys.map(k => `${k}=?`).join(",")}, updated_at=CURRENT_TIMESTAMP WHERE id=?`
    ).run(...vals, req.params.id)
    res.json({ ok: true })
  })

  app.delete(`/${safe}/:id`, (req, res) => {
    db.prepare(`DELETE FROM ${safe} WHERE id = ?`).run(req.params.id)
    res.json({ ok: true })
  })
}

// Register routes
crud("items")

app.listen(PORT, () => console.log(`API: http://localhost:${PORT}`))
