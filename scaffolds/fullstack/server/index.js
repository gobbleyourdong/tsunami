import express from "express"
import cors from "cors"
import Database from "better-sqlite3"
import { dirname, join } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const PORT = process.env.PORT || 3001

// Database — SQLite, local-first, no cloud needed
const db = new Database(join(__dirname, "data.db"))
db.pragma("journal_mode = WAL")
db.pragma("foreign_keys = ON")

// Create tables if they don't exist
// TODO: Add your schema here
db.exec(`
  CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    data TEXT DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`)

const app = express()
app.use(cors())
app.use(express.json())

// API routes — TODO: Add your endpoints here
app.get("/api/items", (req, res) => {
  const items = db.prepare("SELECT * FROM items ORDER BY created_at DESC").all()
  res.json(items)
})

app.post("/api/items", (req, res) => {
  const { name, data } = req.body
  const result = db.prepare("INSERT INTO items (name, data) VALUES (?, ?)").run(name, JSON.stringify(data || {}))
  res.json({ id: result.lastInsertRowid })
})

app.put("/api/items/:id", (req, res) => {
  const { name, data } = req.body
  db.prepare("UPDATE items SET name = ?, data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?")
    .run(name, JSON.stringify(data || {}), req.params.id)
  res.json({ ok: true })
})

app.delete("/api/items/:id", (req, res) => {
  db.prepare("DELETE FROM items WHERE id = ?").run(req.params.id)
  res.json({ ok: true })
})

app.listen(PORT, () => {
  console.log(`API server on http://localhost:${PORT}`)
})
