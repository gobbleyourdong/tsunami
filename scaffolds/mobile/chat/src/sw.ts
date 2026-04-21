/// <reference lib="WebWorker" />
/**
 * Service worker — cache-first for built static assets, network-first
 * for everything else (so API calls still try the network, but a
 * cached version of the shell is there when offline).
 *
 * Version string bumps on every build; old caches get evicted during
 * `activate`. Keep the shape simple — swap in Workbox if you need
 * background sync, expiration, or IndexedDB queuing.
 */
declare const self: ServiceWorkerGlobalScope

const CACHE_VERSION = "chat-v1"
const STATIC = [
  "/",
  "/index.html",
  "/manifest.json",
]

self.addEventListener("install", (event: ExtendableEvent) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then(c => c.addAll(STATIC)),
  )
  self.skipWaiting()
})

self.addEventListener("activate", (event: ExtendableEvent) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_VERSION).map(k => caches.delete(k)),
      ),
    ),
  )
  self.clients.claim()
})

self.addEventListener("fetch", (event: FetchEvent) => {
  const req = event.request
  if (req.method !== "GET") return

  const url = new URL(req.url)
  const isStatic = url.origin === self.location.origin &&
    (url.pathname === "/" ||
     url.pathname.startsWith("/assets/") ||
     url.pathname === "/manifest.json" ||
     url.pathname === "/sw.js")

  if (isStatic) {
    event.respondWith(
      caches.match(req).then(hit => hit ?? fetch(req).then(res => {
        const clone = res.clone()
        caches.open(CACHE_VERSION).then(c => c.put(req, clone)).catch(() => {})
        return res
      })),
    )
    return
  }

  event.respondWith(
    fetch(req).catch(() => caches.match(req).then(r => r ?? Response.error())),
  )
})

export {}
