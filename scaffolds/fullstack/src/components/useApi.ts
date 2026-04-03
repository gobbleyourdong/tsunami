import { useState, useEffect, useCallback } from "react"

const API_BASE = "/api"

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

interface UseApiState<T> {
  data: T[]
  loading: boolean
  error: string | null
}

/** React hook for CRUD operations against the Express API.
 *
 * Usage:
 *   const { data, loading, error, create, update, remove, refresh } = useApi<Item>("items")
 */
export function useApi<T extends { id?: number }>(resource: string) {
  const [state, setState] = useState<UseApiState<T>>({ data: [], loading: true, error: null })

  const refresh = useCallback(async () => {
    setState(s => ({ ...s, loading: true, error: null }))
    try {
      const data = await api<T[]>(`/${resource}`)
      setState({ data, loading: false, error: null })
    } catch (e: any) {
      setState(s => ({ ...s, loading: false, error: e.message }))
    }
  }, [resource])

  useEffect(() => { refresh() }, [refresh])

  const create = useCallback(async (item: Partial<T>) => {
    const result = await api<{ id: number }>(`/${resource}`, {
      method: "POST", body: JSON.stringify(item),
    })
    await refresh()
    return result
  }, [resource, refresh])

  const update = useCallback(async (id: number, item: Partial<T>) => {
    await api(`/${resource}/${id}`, {
      method: "PUT", body: JSON.stringify(item),
    })
    await refresh()
  }, [resource, refresh])

  const remove = useCallback(async (id: number) => {
    await api(`/${resource}/${id}`, { method: "DELETE" })
    await refresh()
  }, [resource, refresh])

  return { ...state, create, update, remove, refresh }
}
