/// <reference lib="WebWorker" />
/** Same shape as the mobile/chat service worker. */
declare const self: ServiceWorkerGlobalScope

const CACHE_VERSION = "notes-v1"
const STATIC = ["/", "/index.html", "/manifest.json"]

self.addEventListener("install", (event: ExtendableEvent) => {
  event.waitUntil(caches.open(CACHE_VERSION).then(c => c.addAll(STATIC)))
  self.skipWaiting()
})

self.addEventListener("activate", (event: ExtendableEvent) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_VERSION).map(k => caches.delete(k))),
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
