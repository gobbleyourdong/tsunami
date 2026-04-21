export function registerServiceWorker(): void {
  if (typeof navigator === "undefined") return
  if (!("serviceWorker" in navigator)) return
  if (typeof window === "undefined") return
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js", { scope: "/" })
      .catch(err => console.warn("sw register failed:", err))
  })
}
