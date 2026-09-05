/* Сервис-воркер «Кофейни на высоте».
   Оболочка приложения и фотографии заведения кладутся в кэш при установке —
   приложение открывается без сети. index.html берётся из сети в первую очередь
   (так обновления доходят сразу), из кэша — только если сети нет. Снимки
   напитков с фотостока и шрифты кэшируются по мере обращения. */
const VERSION = 'knv-2026-09-05-1';
const SHELL = [
  './', 'index.html', 'manifest.webmanifest',
  'icons/icon-192.png', 'icons/icon-512.png', 'icons/icon-180.png',
  'assets/interior.jpg', 'assets/splash.jpg', 'assets/auth.jpg', 'assets/facade.jpg',
  'assets/bonus-band.jpg', 'assets/gal-gorge.jpg', 'assets/gal-sharoy.jpg', 'assets/gal-tower.jpg'
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const sameOrigin = url.origin === self.location.origin;
  const isPage = req.mode === 'navigate' || (sameOrigin && /\/(index\.html)?$/.test(url.pathname));

  if (isPage) {
    // сеть → кэш: свежая версия при связи, рабочая — без неё
    e.respondWith(fetch(req).then(res => { const copy = res.clone(); caches.open(VERSION).then(c => c.put('index.html', copy)); return res; })
      .catch(() => caches.match('index.html')));
    return;
  }
  // всё остальное — кэш → сеть с докладыванием в кэш (фото, шрифты, иконки)
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
    if (res && (res.ok || res.type === 'opaque')) { const copy = res.clone(); caches.open(VERSION).then(c => c.put(req, copy)); }
    return res;
  }).catch(() => hit)));
});
