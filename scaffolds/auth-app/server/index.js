import express from "express"
import cors from "cors"
import Database from "better-sqlite3"
import bcrypt from "bcryptjs"
import jwt from "jsonwebtoken"
import { config } from "dotenv"
import { dirname, join } from "path"
import { fileURLToPath } from "url"

config()

const __dirname = dirname(fileURLToPath(import.meta.url))
const PORT = process.env.PORT || 3001
const JWT_SECRET = process.env.JWT_SECRET || "dev-secret-change-in-production"

// SQLite
const db = new Database(join(__dirname, "data.db"))
db.pragma("journal_mode = WAL")
db.pragma("foreign_keys = ON")

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    email      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    body       TEXT DEFAULT '',
    status     TEXT DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
`)

const app = express()
app.use(cors())
app.use(express.json())

// ── Auth middleware ───────────────────────────────────────────────────────────
function requireAuth(req, res, next) {
  const authHeader = req.headers.authorization
  if (!authHeader?.startsWith("Bearer ")) {
    return res.status(401).json({ error: "Unauthorized — include Authorization: Bearer <token>" })
  }
  try {
    req.user = jwt.verify(authHeader.slice(7), JWT_SECRET)
    next()
  } catch {
    res.status(401).json({ error: "Invalid or expired token" })
  }
}

// ── Auth routes ───────────────────────────────────────────────────────────────
app.post("/api/auth/register", async (req, res) => {
  const { email, password } = req.body
  if (!email || !password) return res.status(400).json({ error: "Email and password required" })
  if (password.length < 8) return res.status(400).json({ error: "Password must be at least 8 characters" })
  try {
    const hash = await bcrypt.hash(password, 10)
    const { lastInsertRowid } = db.prepare(
      "INSERT INTO users (email, password_hash) VALUES (?, ?)"
    ).run(email, hash)
    const token = jwt.sign({ id: lastInsertRowid, email }, JWT_SECRET, { expiresIn: "7d" })
    res.status(201).json({ token, user: { id: lastInsertRowid, email } })
  } catch (e) {
    if (e.message.includes("UNIQUE")) return res.status(409).json({ error: "Email already registered" })
    res.status(500).json({ error: e.message })
  }
})

app.post("/api/auth/login", async (req, res) => {
  const { email, password } = req.body
  const user = db.prepare("SELECT * FROM users WHERE email = ?").get(email)
  if (!user || !(await bcrypt.compare(password, user.password_hash))) {
    return res.status(401).json({ error: "Invalid email or password" })
  }
  const token = jwt.sign({ id: user.id, email: user.email }, JWT_SECRET, { expiresIn: "7d" })
  res.json({ token, user: { id: user.id, email: user.email } })
})

app.get("/api/auth/me", requireAuth, (req, res) => {
  const user = db.prepare("SELECT id, email, created_at FROM users WHERE id = ?").get(req.user.id)
  user ? res.json(user) : res.status(404).json({ error: "User not found" })
})

// ── Per-user CRUD factory ─────────────────────────────────────────────────────
// All data scoped to req.user.id — users only see their own data.
function authCrud(table) {
  const safe = table.replace(/[^a-z_]/gi, "")

  app.get(`/api/${safe}`, requireAuth, (req, res) => {
    try {
      const rows = db.prepare(
        `SELECT * FROM ${safe} WHERE user_id = ? ORDER BY created_at DESC`
      ).all(req.user.id)
      res.json(rows)
    } catch (e) { res.status(500).json({ error: e.message }) }
  })

  app.post(`/api/${safe}`, requireAuth, (req, res) => {
    try {
      const cols = Object.keys(req.body).filter(k => k !== "id" && k !== "user_id" && k !== "created_at")
      const vals = cols.map(c => req.body[c])
      const placeholders = cols.map(() => "?").join(", ")
      const { lastInsertRowid } = db.prepare(
        `INSERT INTO ${safe} (user_id, ${cols.join(", ")}) VALUES (?, ${placeholders})`
      ).run(req.user.id, ...vals)
      const row = db.prepare(`SELECT * FROM ${safe} WHERE id = ?`).get(lastInsertRowid)
      res.status(201).json(row)
    } catch (e) { res.status(500).json({ error: e.message }) }
  })

  app.put(`/api/${safe}/:id`, requireAuth, (req, res) => {
    try {
      const existing = db.prepare(`SELECT * FROM ${safe} WHERE id = ? AND user_id = ?`).get(req.params.id, req.user.id)
      if (!existing) return res.status(404).json({ error: "Not found" })
      const cols = Object.keys(req.body).filter(k => k !== "id" && k !== "user_id" && k !== "created_at")
      const updates = cols.map(c => `${c} = ?`).join(", ")
      const vals = cols.map(c => req.body[c])
      db.prepare(`UPDATE ${safe} SET ${updates}, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?`
      ).run(...vals, req.params.id, req.user.id)
      res.json(db.prepare(`SELECT * FROM ${safe} WHERE id = ?`).get(req.params.id))
    } catch (e) { res.status(500).json({ error: e.message }) }
  })

  app.delete(`/api/${safe}/:id`, requireAuth, (req, res) => {
    try {
      const result = db.prepare(`DELETE FROM ${safe} WHERE id = ? AND user_id = ?`).run(req.params.id, req.user.id)
      result.changes ? res.json({ ok: true }) : res.status(404).json({ error: "Not found" })
    } catch (e) { res.status(500).json({ error: e.message }) }
  })
}

// Register CRUD for the default 'items' table
authCrud("items")

app.get("/api/health", (req, res) => res.json({ ok: true }))

app.listen(PORT, () => console.log(`Auth server on :${PORT} — JWT_SECRET: ${JWT_SECRET === "dev-secret-change-in-production" ? "⚠️ DEV ONLY" : "✓ custom"}`))
