import { useSyncExternalStore } from "react"

export type Note = {
  id: string
  title: string
  body: string
  created_at: string
  updated_at: string
}

const STORAGE_KEY = "notes.v1"

function load(): Note[] {
  if (typeof window === "undefined") return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return seed()
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : seed()
  } catch {
    return seed()
  }
}

function seed(): Note[] {
  const t = new Date().toISOString()
  return [
    {
      id: "n-welcome",
      title: "Welcome to Notes",
      body:
        "This is a scaffolded note. Delete me, or tap the + button to add your own.\n\n" +
        "Notes are stored in localStorage — no backend yet. Wire one up in\n" +
        "src/lib/notes-store.ts if you want sync across devices.",
      created_at: t,
      updated_at: t,
    },
  ]
}

let state: Note[] = load()
const listeners = new Set<() => void>()

function emit() {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  }
  listeners.forEach(l => l())
}

export function subscribe(fn: () => void): () => void {
  listeners.add(fn)
  return () => { listeners.delete(fn) }
}

export function getNotes(): Note[] {
  return state
}

export function findNote(id: string): Note | undefined {
  return state.find(n => n.id === id)
}

export function newNote(): Note {
  const t = new Date().toISOString()
  const note: Note = {
    id: `n-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title: "",
    body: "",
    created_at: t,
    updated_at: t,
  }
  state = [note, ...state]
  emit()
  return note
}

export function updateNote(id: string, patch: Partial<Pick<Note, "title" | "body">>): void {
  const t = new Date().toISOString()
  state = state.map(n =>
    n.id === id ? { ...n, ...patch, updated_at: t } : n,
  )
  emit()
}

export function deleteNote(id: string): void {
  state = state.filter(n => n.id !== id)
  emit()
}

export function useNotes(): Note[] {
  const snapshot = useSyncExternalStore(subscribe, getNotes, getNotes)
  return [...snapshot].sort((a, b) => b.updated_at.localeCompare(a.updated_at))
}
