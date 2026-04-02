import { useEffect, useRef, useState, useCallback } from "react"

interface UseWebSocketOptions {
  url?: string
  onMessage?: (data: any) => void
  reconnect?: boolean
}

/** WebSocket hook — auto-connects, auto-reconnects, typed messages. */
export function useWebSocket({
  url = "ws://localhost:3001",
  onMessage,
  reconnect = true,
}: UseWebSocketOptions = {}) {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<any>(null)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  useEffect(() => {
    let ws: WebSocket
    let reconnectTimer: number

    function connect() {
      ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        if (reconnect) reconnectTimer = window.setTimeout(connect, 2000)
      }
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          setLastMessage(data)
          onMessageRef.current?.(data)
        } catch {}
      }
    }

    connect()
    return () => {
      reconnect = false
      clearTimeout(reconnectTimer)
      ws?.close()
    }
  }, [url])

  const send = useCallback((data: any) => {
    if (wsRef.current?.readyState === 1) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  return { connected, send, lastMessage }
}
