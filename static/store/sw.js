/* Cache only a generic offline document, never accounts, APIs or checkout. */
const OFFLINE_URL = __OFFLINE_URL__;
const CACHE_NAME = 'ivanka-store-offline-v1-' + self.registration.scope;
self.addEventListener('install', event => {
 event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.add(OFFLINE_URL)));
});
self.addEventListener('activate', event => {
 event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('ivanka-store-offline-') && key !== CACHE_NAME).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
 if(event.request.method !== 'GET' || event.request.mode !== 'navigate')return;
 const url = new URL(event.request.url);
 if(url.origin !== self.location.origin)return;
 event.respondWith(fetch(event.request).catch(() => caches.open(CACHE_NAME).then(cache => cache.match(OFFLINE_URL)).then(response => response || Response.error())));
});
