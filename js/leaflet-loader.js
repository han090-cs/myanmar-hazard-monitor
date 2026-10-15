/* CDN fallback loader for Leaflet; load the app only after Leaflet's script has settled. */
(function () {
  'use strict';
  var jsUrls = [
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
    'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js',
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js'
  ];
  function loadApp() {
    function injectApp() {
      function appendApp() {
        var app = document.createElement('script');
        app.src = 'js/app.js?v=20261014-4';
        app.defer = true;
        app.onerror = function () {
          var map = document.getElementById('map');
          if (map) map.textContent = 'App script could not load. Check that js/app.js exists and the site path is correct.';
        };
        document.body.appendChild(app);
      }
      if (location.protocol === 'file:') {
        var bundled = document.createElement('script');
        bundled.src = 'data/js/mapdata.js';
        bundled.onload = appendApp;
        bundled.onerror = appendApp;
        document.body.appendChild(bundled);
      } else appendApp();
    }
    if (window.MM_SW_REPAIR_PROMISE && typeof window.MM_SW_REPAIR_PROMISE.then === 'function') {
      window.MM_SW_REPAIR_PROMISE.then(injectApp, injectApp);
    } else injectApp();
  }

  function tryJs(index) {
    if (index >= jsUrls.length) {
      loadApp();
      return;
    }
    var script = document.createElement('script');
    script.src = jsUrls[index];
    script.integrity = 'sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=';
    script.crossOrigin = 'anonymous';
    script.async = true;
    script.onload = loadApp;
    script.onerror = function () { tryJs(index + 1); };
    document.head.appendChild(script);
  }
  if (window.MM_SW_REPAIR_PROMISE && typeof window.MM_SW_REPAIR_PROMISE.then === 'function') {
    window.MM_SW_REPAIR_PROMISE.then(function () { tryJs(0); }, function () { tryJs(0); });
  } else tryJs(0);
})();
