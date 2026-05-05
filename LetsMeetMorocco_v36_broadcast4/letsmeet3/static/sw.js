const CACHE = 'lmm-v1';
const STATIC = [
  '/',
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/img/logo.png',
  '/offline.html'
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC)));
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    fetch(e.request)
      .then(res => {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return res;
      })
      .catch(() => caches.match(e.request)
        .then(cached => cached || caches.match('/offline.html'))
      )
  );
});
