const CACHE_NAME = 'kartoteka-pwa-v1';
const PRECACHE_URLS = [
  '/',
  '/register',
  '/dashboard',
  '/portfolio',
  '/static/style.css',
  '/static/js/app.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((cacheName) => cacheName !== CACHE_NAME)
          .map((cacheName) => caches.delete(cacheName))
      )
    ).then(() => self.clients.claim())
  );
});

const STATIC_EXTENSIONS = [
  '.css',
  '.js',
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.svg',
  '.ico',
  '.webp',
  '.woff',
  '.woff2',
  '.ttf',
  '.otf'
];

const HTML_ROUTES = ['/', '/register', '/dashboard', '/portfolio'];

const isStaticAsset = (url) => {
  return STATIC_EXTENSIONS.some((ext) => url.pathname.endsWith(ext));
};

const isCacheableHtmlRoute = (url) => {
  return HTML_ROUTES.includes(url.pathname);
};

self.addEventListener('fetch', (event) => {
  const { request } = event;

  if (request.method !== 'GET') {
    return;
  }

  const requestUrl = new URL(request.url);
  const isSameOrigin = requestUrl.origin === self.location.origin;
  const hasAuthHeader = request.headers.has('Authorization');
  const isDynamicApiRequest =
    hasAuthHeader ||
    (isSameOrigin && (requestUrl.pathname.startsWith('/users/') || requestUrl.pathname.startsWith('/cards/')));

  if (isDynamicApiRequest) {
    event.respondWith(fetch(request));
    return;
  }

  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }

      return fetch(request)
        .then((response) => {
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }

          if (isSameOrigin && (isStaticAsset(requestUrl) || isCacheableHtmlRoute(requestUrl))) {
            const cloned = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(request, cloned);
            });
          }

          return response;
        })
        .catch(() => caches.match('/'));
    })
  );
});
