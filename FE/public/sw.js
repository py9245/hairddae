const APP_SHELL_CACHE = 'hairtte-app-shell-v2';
const RUNTIME_CACHE = 'hairtte-runtime-v2';
const OFFLINE_FALLBACK_URL = '/offline.html';
const APP_SHELL_URLS = [
  '/',
  '/offline.html',
  '/manifest.webmanifest',
  '/pwa-icon-192.png',
  '/pwa-icon-512.png',
  '/pwa-maskable-512.png',
  '/apple-touch-icon.png',
  '/favicon-32.png',
];
const API_PREFIXES = ['/api/', '/ws/inference/', '/rtc/inference/'];
const RUNTIME_ASSET_PREFIXES = ['/models/', '/mediapipe/', '/hair/', '/icon/', '/font/'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(APP_SHELL_CACHE).then((cache) => cache.addAll(APP_SHELL_URLS)),
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== APP_SHELL_CACHE && key !== RUNTIME_CACHE)
          .map((key) => caches.delete(key)),
      ),
    ),
  );
  self.clients.claim();
});

self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

self.addEventListener('fetch', (event) => {
  const { request } = event;

  if (request.method !== 'GET') {
    return;
  }

  const url = new URL(request.url);

  if (url.origin !== self.location.origin) {
    return;
  }

  if (API_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(handleNavigationRequest(request));
    return;
  }

  if (
    request.destination === 'style' ||
    request.destination === 'script' ||
    request.destination === 'font' ||
    request.destination === 'image' ||
    RUNTIME_ASSET_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))
  ) {
    event.respondWith(handleStaleWhileRevalidate(request));
  }
});

async function handleNavigationRequest(request) {
  try {
    const response = await fetch(request, { cache: 'no-store' });
    const cache = await caches.open(RUNTIME_CACHE);
    cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }

    return (
      (await caches.match('/')) ||
      (await caches.match(OFFLINE_FALLBACK_URL)) ||
      Response.error()
    );
  }
}

async function handleStaleWhileRevalidate(request) {
  const cache = await caches.open(RUNTIME_CACHE);
  const cachedResponse = await caches.match(request);

  const networkResponsePromise = fetch(request)
    .then((response) => {
      if (response && response.ok) {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => null);

  if (cachedResponse) {
    void networkResponsePromise;
    return cachedResponse;
  }

  const networkResponse = await networkResponsePromise;
  return networkResponse || Response.error();
}
