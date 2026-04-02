const API_BASE = "http://localhost:3001/api"

/** Fetch helper — wraps fetch with JSON parsing and error handling. */
async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

/** CRUD helpers — use these in your components. */
export function useApi<T = any>(resource: string) {
  return {
    async list(): Promise<T[]> {
      return api<T[]>(`/${resource}`)
    },

    async get(id: number): Promise<T> {
      return api<T>(`/${resource}/${id}`)
    },

    async create(data: Partial<T>): Promise<{ id: number }> {
      return api<{ id: number }>(`/${resource}`, {
        method: "POST",
        body: JSON.stringify(data),
      })
    },

    async update(id: number, data: Partial<T>): Promise<void> {
      await api(`/${resource}/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      })
    },

    async remove(id: number): Promise<void> {
      await api(`/${resource}/${id}`, { method: "DELETE" })
    },
  }
}
