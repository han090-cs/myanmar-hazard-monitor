/* One-time migration away from stale service workers from earlier project builds.
   This app intentionally does not register a service worker: forecast freshness and
   resilient network fallbacks are safer than an old worker caching broken CDN responses. */
(function () {
  'use strict';
  window.MM_SW_REPAIR_PROMISE = Promise.resolve().then(function () {
    if (!('serviceWorker' in navigator) || !navigator.serviceWorker.getRegistrations) return;
    var repairedKey = 'mm-hazard-sw-repaired-v3';
    if (sessionStorage.getItem(repairedKey)) return;
    return navigator.serviceWorker.getRegistrations().then(function (registrations) {
      var stale = registrations.filter(function (registration) {
        return [registration.active, registration.waiting, registration.installing].some(function (worker) {
          if (!worker || !worker.scriptURL) return false;
          try {
            var workerUrl = new URL(worker.scriptURL);
            return workerUrl.origin === location.origin && /\/sw\.js$/i.test(workerUrl.pathname);
          } catch (_) { return false; }
        });
      });
      if (!stale.length) return;
      return Promise.all(stale.map(function (registration) { return registration.unregister(); }))
        .then(function () {
          return caches.keys().then(function (keys) {
            return Promise.all(keys.filter(function (key) { return /^mm-hazard-/i.test(key); }).map(function (key) { return caches.delete(key); }));
          });
        }).then(function () {
          sessionStorage.setItem(repairedKey, '1');
          location.reload();
          return new Promise(function () {}); // Keep loading paused until the clean reload.
        });
    });
  }).catch(function (error) {
    if (window.console && console.warn) console.warn('Service-worker cleanup skipped:', error);
  });
})();
