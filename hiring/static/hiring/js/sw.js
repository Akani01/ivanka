// ============================================
// SERVICE WORKER - PRODUCTION READY
// ============================================

const CACHE_VERSION = 'v2.0.0';
const CACHE_NAME = `OppoGlobe-${CACHE_VERSION}`;

// URLs to cache on install - FIXED PATHS
const STATIC_CACHE_URLS = [
    '/',
    '/static/hiring/manifest.json',
    '/static/hiring/js/pwa.js',
    '/static/hiring/js/notifications-global.js',
    '/static/hiring/audio/notification.mp3',
    '/static/hiring/icons/icon-192.png',
    '/static/hiring/icons/icon-512.png',
    '/static/hiring/icons/icon-72.png',
    '/offline/',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css'
];

// Install event - cache static assets with error handling
self.addEventListener('install', event => {
    console.log('[Service Worker] Installing...');
    
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[Service Worker] Caching static assets');
                // Use Promise.allSettled to handle individual failures
                return Promise.allSettled(
                    STATIC_CACHE_URLS.map(url => 
                        cache.add(url).catch(err => {
                            console.warn(`[Service Worker] Failed to cache: ${url}`, err);
                        })
                    )
                );
            })
            .then(() => {
                console.log('[Service Worker] Skip waiting');
                return self.skipWaiting();
            })
    );
});

// Activate event - clean old caches
self.addEventListener('activate', event => {
    console.log('[Service Worker] Activating...');
    
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames
                        .filter(cacheName => {
                            return cacheName !== CACHE_NAME;
                        })
                        .map(cacheName => {
                            console.log(`[Service Worker] Deleting old cache: ${cacheName}`);
                            return caches.delete(cacheName);
                        })
                );
            })
            .then(() => {
                console.log('[Service Worker] Claiming clients');
                return self.clients.claim();
            })
    );
});

// Fetch event - network first, cache fallback
self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);
    
    // Skip cross-origin requests (except CDN)
    if (url.origin !== location.origin && !url.origin.includes('cdn')) {
        return;
    }
    
    // Skip API requests - they should always go to network
    if (url.pathname.startsWith('/api/')) {
        return;
    }
    
    // Skip admin requests
    if (url.pathname.startsWith('/admin/')) {
        return;
    }
    
    // Skip static files that are already cached (with better handling)
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(request)
                .then(response => {
                    if (response) {
                        return response;
                    }
                    return fetch(request)
                        .then(response => {
                            if (response && response.status === 200) {
                                const responseClone = response.clone();
                                caches.open(CACHE_NAME)
                                    .then(cache => {
                                        cache.put(request, responseClone);
                                    });
                            }
                            return response;
                        })
                        .catch(() => {
                            // Return a placeholder for images if offline
                            if (url.pathname.match(/\.(png|jpg|jpeg|gif|svg)$/)) {
                                return caches.match('/static/hiring/icons/icon-192.png');
                            }
                            return new Response('Network error', { status: 503 });
                        });
                })
        );
        return;
    }
    
    // HTML pages - network first, fallback to cache
    event.respondWith(
        fetch(request)
            .then(response => {
                // Cache the fresh response
                if (response && response.status === 200) {
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME)
                        .then(cache => {
                            cache.put(request, responseClone);
                        });
                }
                return response;
            })
            .catch(() => {
                // Network failed, try cache
                return caches.match(request)
                    .then(cachedResponse => {
                        if (cachedResponse) {
                            return cachedResponse;
                        }
                        // If not in cache, return offline page
                        return caches.match('/offline/')
                            .then(offlineResponse => {
                                if (offlineResponse) {
                                    return offlineResponse;
                                }
                                // Fallback offline response
                                return new Response(`
                                    <!DOCTYPE html>
                                    <html>
                                        <head><title>Offline</title></head>
                                        <body style="text-align:center;padding-top:50px;font-family:sans-serif;">
                                            <h1>🔌 You're Offline</h1>
                                            <p>Please check your internet connection.</p>
                                        </body>
                                    </html>
                                `, {
                                    headers: { 'Content-Type': 'text/html' }
                                });
                            });
                    });
            })
    );
});

// Handle OppoGlobe push notifications globally.
self.addEventListener('push', event => {
    let data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            data = {
                title: 'OppoGlobe',
                body: event.data.text()
            };
        }
    }

    const title = data.title || data.head || 'OppoGlobe';
    const targetUrl = data.action_url || data.url || '/';
    const silent = data.silent === true || data.sound === false;

    const options = {
        body: data.body || 'You have a new notification',
        icon: data.icon || '/static/hiring/icons/icon-192.png',
        badge: data.badge || '/static/hiring/icons/icon-72x72.png',
        tag: data.tag || undefined,
        renotify: true,
        silent: silent,
        vibrate: silent ? undefined : [200, 100, 200],
        data: {
            ...data,
            url: targetUrl,
            action_url: targetUrl,
            dateOfArrival: Date.now()
        },
        actions: [
            { action: 'open', title: 'Open App' },
            { action: 'close', title: 'Dismiss' }
        ]
    };

    const notifyOpenPages = clients.matchAll({
        type: 'window',
        includeUncontrolled: true
    }).then(clientList => Promise.all(clientList.map(client =>
        client.postMessage({
            type: 'OPPOGLOBE_PUSH_RECEIVED',
            payload: {
                ...data,
                title,
                url: targetUrl,
                action_url: targetUrl,
                silent,
                received_at: Date.now()
            }
        })
    )));

    event.waitUntil(Promise.all([
        self.registration.showNotification(title, options),
        notifyOpenPages
    ]));
});

// Handle notification click
self.addEventListener('notificationclick', event => {
    event.notification.close();
    
    const action = event.action;
    const url = event.notification.data.url || '/';
    
    if (action === 'open' || !action) {
        event.waitUntil(
            clients.matchAll({
                type: 'window',
                includeUncontrolled: true
            })
            .then(clientList => {
                // Check if there's a client already open
                for (const client of clientList) {
                    if (client.url === url && 'focus' in client) {
                        return client.focus();
                    }
                }
                // Otherwise open a new window
                if (clients.openWindow) {
                    return clients.openWindow(url);
                }
            })
        );
    }
});

// Handle messages from the client
self.addEventListener('message', event => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

console.log('[Service Worker] Loaded successfully');