/* Сервис-воркер «Кофейни на высоте».
   Оболочка приложения и фотографии заведения кладутся в кэш при установке —
   приложение открывается без сети. index.html берётся из сети в первую очередь
   (так обновления доходят сразу), из кэша — только если сети нет. Снимки
   напитков с фотостока и шрифты кэшируются по мере обращения. */
const VERSION = 'knv-2026-09-12-1';
const SHELL = [
  './', 'index.html', 'manifest.webmanifest',
  'icons/icon-192.png', 'icons/icon-512.png', 'icons/icon-180.png',
  'assets/interior.jpg', 'assets/splash.jpg', 'assets/auth.jpg', 'assets/facade.jpg',
  'assets/bonus-band.jpg', 'assets/gal-gorge.jpg', 'assets/gal-sharoy.jpg', 'assets/gal-tower.jpg',
  'assets/audio/morning.mp3', 'assets/audio/cover-morning.jpg', 'assets/audio/playlist.json',
  'assets/fonts/fonts.css',
  'assets/fonts/Manrope-400-cyrillic.woff2', 'assets/fonts/Manrope-400-latin.woff2',
  'assets/fonts/Manrope-500-cyrillic.woff2', 'assets/fonts/Manrope-500-latin.woff2',
  'assets/fonts/Manrope-600-cyrillic.woff2', 'assets/fonts/Manrope-600-latin.woff2',
  'assets/fonts/Manrope-700-cyrillic.woff2', 'assets/fonts/Manrope-700-latin.woff2',
  'assets/fonts/Manrope-800-cyrillic.woff2', 'assets/fonts/Manrope-800-latin.woff2',
  'assets/fonts/CormorantGaramond-500-cyrillic.woff2', 'assets/fonts/CormorantGaramond-500-latin.woff2',
  'assets/fonts/CormorantGaramond-600-cyrillic.woff2', 'assets/fonts/CormorantGaramond-600-latin.woff2'
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

const AUDIO_RE = /\.(mp3|m4a|aac|ogg|oga|wav)$/i;

// Кусок файла по заголовку Range: статус 206 и Content-Range, иначе браузер
// считает ответ негодным и молча отказывается играть.
async function partial(res, range) {
  const buf = await res.arrayBuffer();
  const m = /bytes=(\d*)-(\d*)/.exec(range || '');
  if (!m) return new Response(buf, { status: 200, headers: res.headers });
  const total = buf.byteLength;
  let start = m[1] ? +m[1] : 0;
  let end = m[2] ? +m[2] : total - 1;
  if (!m[1] && m[2]) { start = Math.max(0, total - +m[2]); end = total - 1; }   // bytes=-N — хвост файла
  if (start >= total || start > end) return new Response(null, { status: 416, headers: { 'Content-Range': 'bytes */' + total } });
  end = Math.min(end, total - 1);
  return new Response(buf.slice(start, end + 1), {
    status: 206,
    headers: {
      'Content-Type': res.headers.get('content-type') || 'audio/mpeg',
      'Content-Length': String(end - start + 1),
      'Content-Range': 'bytes ' + start + '-' + end + '/' + total,
      'Accept-Ranges': 'bytes'
    }
  });
}
// Дорожка берётся из кэша, а чего нет — скачивается целиком и кладётся туда же:
// после первого прослушивания музыка играет и без сети.
async function audio(req, url) {
  const cache = await caches.open(VERSION);
  let res = await cache.match(url.pathname);
  if (!res) {
    try {
      const net = await fetch(url.pathname, { cache: 'no-store' });
      if (!net || !net.ok) return net || new Response(null, { status: 504 });
      await cache.put(url.pathname, net.clone());
      res = net;
    } catch (err) {
      return new Response(null, { status: 504 });
    }
  }
  const range = req.headers.get('range');
  return range ? partial(res.clone(), range) : res.clone();
}

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const sameOrigin = url.origin === self.location.origin;
  const isPage = req.mode === 'navigate' || (sameOrigin && /\/(index\.html)?$/.test(url.pathname));

  // Плейлист — сеть вперёд, кэш про запас: новая дорожка доходит до гостей сразу,
  // а без сети играет тот список, что был в прошлый раз.
  if (/playlist\.json$/i.test(url.pathname)) {
    e.respondWith(fetch(req, { cache: 'no-store' })
      .then(res => { if (res && res.ok) { const copy = res.clone(); caches.open(VERSION).then(c => c.put(url.pathname, copy)); } return res; })
      .catch(() => caches.match(url.pathname).then(hit => hit || new Response('[]', { headers: { 'Content-Type': 'application/json' } }))));
    return;
  }

  // Звук — отдельная дорога. Браузер просит дорожку кусками (заголовок Range), а
  // обычный ответ из кэша целиком Safari не принимает: дорожка не заиграет и не
  // будет перематываться. Поэтому свои дорожки отдаём сами и режем на куски
  // руками, а чужие домены не трогаем вовсе.
  if (req.destination === 'audio' || AUDIO_RE.test(url.pathname)) {
    if (!sameOrigin) return;
    e.respondWith(audio(req, url));
    return;
  }

  if (isPage) {
    // Сеть → кэш: свежая версия при связи, рабочая — без неё. Ждём сеть не дольше
    // трёх секунд: на «подключённом», но мёртвом Wi-Fi приложение иначе не открылось
    // бы вовсе. В кэш попадает только настоящая страница со своего домена — не
    // ошибка 404 при выкладке и не страница входа в Wi-Fi кафе.
    const net = fetch(req).then(res => {
      const html = /text\/html/.test(res.headers.get('content-type') || '');
      if (res.ok && !res.redirected && res.type === 'basic' && html) { const copy = res.clone(); caches.open(VERSION).then(c => c.put('index.html', copy)); return res; }
      return caches.match('index.html').then(hit => hit || res);
    });
    const slow = new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), 3000));
    e.respondWith(Promise.race([net, slow]).catch(() => caches.match('index.html').then(hit => hit || net)));
    return;
  }
  // всё остальное — кэш → сеть с докладыванием в кэш (фото, шрифты, иконки)
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
    if (res && (res.ok || res.type === 'opaque')) { const copy = res.clone(); caches.open(VERSION).then(c => c.put(req, copy)); }
    return res;
  }).catch(() => hit)));
});
