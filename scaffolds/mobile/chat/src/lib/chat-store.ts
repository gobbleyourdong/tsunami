import { useSyncExternalStore } from "react"

export type Message = {
  id: string
  body: string
  sender: "me" | "them"
  sent_at: string
}

const STORAGE_KEY = "chat.messages.v1"

function load(): Message[] {
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

function seed(): Message[] {
  const now = Date.now()
  return [
    { id: "m-1", body: "Hey — this is a scaffolded chat.", sender: "them", sent_at: new Date(now - 60_000).toISOString() },
    { id: "m-2", body: "Replace this transport with your backend or WebSocket.", sender: "them", sent_at: new Date(now - 30_000).toISOString() },
  ]
}

let state: Message[] = load()
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

export function getMessages(): Message[] {
  return state
}

export function sendMessage(body: string): void {
  const trimmed = body.trim()
  if (!trimmed) return
  const msg: Message = {
    id: `m-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    body: trimmed,
    sender: "me",
    sent_at: new Date().toISOString(),
  }
  state = [...state, msg]
  emit()
  // Echo reply — replace with a real backend call.
  setTimeout(() => receiveMessage(`echo: ${trimmed}`), 350)
}

export function receiveMessage(body: string): void {
  const msg: Message = {
    id: `m-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    body,
    sender: "them",
    sent_at: new Date().toISOString(),
  }
  state = [...state, msg]
  emit()
}

export function clearMessages(): void {
  state = []
  emit()
}

export function useMessages(): Message[] {
  return useSyncExternalStore(subscribe, getMessages, getMessages)
}
