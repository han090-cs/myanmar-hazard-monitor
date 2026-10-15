/* Safe service worker for Myanmar Flood & Landslide Monitor.
   Never intercept third-party CDN requests: Leaflet/fonts must use the browser network directly. */
'use strict';
const CACHE_NAME = 'mm-hazard-static-v30261014-3';
const PRECACHE = [
  './',
  './index.html',
  './css/style.css',
  './js/app.js',
  './data/summary.json',
  './data/metadata.json',
  './data/flood_zones.geojson',
  './data/landslide_zones.geojson',
  './data/river_forecast.json',
  './data/public_info.json',
  './data/disaster_events.json',
  './manifest.webmanifest'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE.map(path => new Request(path, { cache: 'reload' }))))
      .catch(() => Promise.resolve())
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key.startsWith('mm-hazard-') && key !== CACHE_NAME).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);

  // Do not handle cross-origin requests. This avoids broken respondWith() errors
  // and lets the browser handle CDN CORS/SRI/network failures normally.
  if (url.origin !== self.location.origin || request.method !== 'GET') return;

  // HTML is network-first so fixes deploy promptly; static assets are cache-first.
  if (request.mode === 'navigate' || url.pathname.endsWith('/index.html') || url.pathname.endsWith('/')) {
    event.respondWith(
      fetch(request).then(response => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, copy)).catch(() => {});
        }
        return response;
      }).catch(() => caches.match(request).then(hit => hit || caches.match('./index.html')))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then(hit => {
      if (hit) return hit;
      return fetch(request).then(response => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, copy)).catch(() => {});
        }
        return response;
      });
    })
  );
});
