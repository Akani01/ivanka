// Cache only the public offline page. Never cache user APIs, checkout, admin or media.
const CACHE = "ivanka-offline-v1";
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.add("/static/store/offline.html")),
  );
  self.skipWaiting();
});
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k.startsWith("ivanka-") && k !== CACHE)
            .map((k) => caches.delete(k)),
        ),
      ),
  );
  self.clients.claim();
});
self.addEventListener("fetch", (e) => {
  if (
    e.request.mode === "navigate" &&
    e.request.method === "GET" &&
    new URL(e.request.url).pathname === "/"
  ) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match("/static/store/offline.html")),
    );
  }
});
