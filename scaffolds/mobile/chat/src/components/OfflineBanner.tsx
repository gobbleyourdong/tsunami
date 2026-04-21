import { useEffect, useState } from "react"

export default function OfflineBanner() {
  const [offline, setOffline] = useState(
    typeof navigator !== "undefined" ? !navigator.onLine : false,
  )

  useEffect(() => {
    function online() { setOffline(false) }
    function offlineHandler() { setOffline(true) }
    window.addEventListener("online", online)
    window.addEventListener("offline", offlineHandler)
    return () => {
      window.removeEventListener("online", online)
      window.removeEventListener("offline", offlineHandler)
    }
  }, [])

  if (!offline) return null
  return <div className="offline-banner">You're offline — messages will queue locally.</div>
}
