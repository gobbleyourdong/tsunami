/**
 * Register the service worker once, after page load, so SW install
 * doesn't compete with first-paint. Silently no-ops where service
 * workers aren't available (http://, older browsers).
 */
export function registerServiceWorker(): void {
  if (typeof navigator === "undefined") return
  if (!("serviceWorker" in navigator)) return
  if (typeof window === "undefined") return

  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js", { scope: "/" })
      .catch(err => {
        console.warn("sw register failed:", err)
      })
  })
}
