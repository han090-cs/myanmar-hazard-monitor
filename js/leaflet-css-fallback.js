/* Capture stylesheet load errors before they happen and walk through Leaflet CDN mirrors. */
(function () {
  'use strict';
  var mirrors = [
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
    'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css',
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css'
  ];
  var next = 1;
  var sri = 'sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=';
  window.addEventListener('error', function (event) {
    var target = event && event.target;
    if (!target || target.id !== 'leaflet-css' || next >= mirrors.length) return;
    target.integrity = sri;
    target.crossOrigin = 'anonymous';
    target.href = mirrors[next++];
  }, true);
})();
