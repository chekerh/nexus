/* Nexus-UGC Service Worker — v2 */

const CACHE_VERSION = 'v3';
const CACHE = {
  static: `nexus-static-${CACHE_VERSION}`,
  pages: `nexus-pages-${CACHE_VERSION}`,
  fonts: `nexus-fonts-${CACHE_VERSION}`,
};

const PRECACHE_URLS = [
  /* Core pages */
  '/',
  '/index.html',
  '/login.html',
  '/offline.html',
  '/accounts.html',
  '/billing.html',
  '/brainrot.html',
  '/calendar.html',
  '/campaigns.html',
  '/personas.html',
  '/queue.html',
  '/settings.html',
  '/setup.html',
  '/templates.html',
  '/privacy.html',
  '/terms.html',
  '/verify-email.html',
  '/reset-password.html',
  /* Core JS */
  '/api.js',
  '/ui.js',
  '/particles.js',
  '/choko.js',
  '/choko-knowledge.js',
  '/i18n.js',
  '/script.js',
  '/calendar.js',
  '/campaigns.js',
  '/persona.js',
  '/admin.js',
  /* Core CSS */
  '/style.css',
  '/choko.css',
  '/admin.css',
  /* Icons */
  '/icons/icon-192.svg',
  '/icons/icon-512.svg',
  '/manifest.json',
  /* i18n */
  '/locales/en.json',
  '/locales/fr.json',
  '/locales/ar.json',
];

/* ── Install: pre-cache critical assets ── */
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE.static).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

/* ── Activate: clean old caches ── */
self.addEventListener('activate', (event) => {
  const keep = Object.values(CACHE);
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => !keep.includes(k)).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

/* ── Message: skip waiting on update ── */
self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

/* ── Fetch: caching strategy ── */
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (url.origin !== self.location.origin) return;

  const path = url.pathname;

  /* API calls — network only, never cache */
  if (path.startsWith('/api/')) {
    return event.respondWith(fetch(request).catch(() => new Response(null, { status: 503 })));
  }

  /* Static assets (CSS, JS, images, icons) — cache first */
  if (
    path.endsWith('.css') ||
    path.endsWith('.js') ||
    path.endsWith('.svg') ||
    path.endsWith('.png') ||
    path.endsWith('.jpg') ||
    path.endsWith('.woff2') ||
    path.endsWith('.woff') ||
    path.endsWith('.ttf') ||
    path.endsWith('.json')
  ) {
    return event.respondWith(cacheFirst(request, CACHE.static));
  }

  /* HTML pages — network first, fallback to cache or offline page */
  if (path.endsWith('.html') || path === '/') {
    return event.respondWith(networkFirstWithOfflineFallback(request, CACHE.pages));
  }

  /* Everything else — network first */
  event.respondWith(networkFirst(request, CACHE.pages));
});

/* ── Cache-first strategy ── */
async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response(null, { status: 503 });
  }
}

/* ── Network-first strategy ── */
async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response(null, { status: 503 });
  }
}

/* ── Network-first with offline fallback for navigation ── */
async function networkFirstWithOfflineFallback(request, cacheName) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    const offline = await caches.match('/offline.html');
    if (offline) return offline;
    return new Response(null, { status: 503 });
  }
}
