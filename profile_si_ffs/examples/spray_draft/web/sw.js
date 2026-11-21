// Only the local app shell is cached. The catalog's browser copy lives in
// IndexedDB, so a cached HTTP reply cannot masquerade as a live server check.
const CACHE = 'ofarm-spray-draft-shell-v12';
const ASSETS = ['/', '/app.js', '/style.css'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('ofarm-spray-draft-shell-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || !ASSETS.includes(url.pathname)) return;
  event.respondWith(fetch(event.request).then(async response => {
    if (response.ok) {
      const cache = await caches.open(CACHE);
      await cache.put(event.request, response.clone());
    }
    return response;
  }).catch(async () => {
    const cached = await caches.match(event.request);
    return cached || new Response('Load this local app once online before using it offline.', { status: 503 });
  }));
});
