"""Собирает версию для хостинга: вшивает ВСЕ картинки, включая внешние.

    python build-web.py

Отличие от build-standalone.py: та копия рассчитана на локальный показ и
оставляет фотографии напитков ссылками на фотосток. Хостинг-площадки часто
запрещают загрузку с чужих доменов (строгий CSP), поэтому здесь внешние
снимки тоже скачиваются и кладутся в файл. Шрифты Google остаются ссылкой —
их площадка пропускает.
"""
import base64
import mimetypes
import os
import re
import sys
import urllib.request

SRC = 'index.html'
OUT = 'web.html'
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.imgcache')
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) build-web.py'}

# как index.html строит адрес снимка напитка (для веба берём поменьше)
UNSPLASH_TPL = 'https://images.unsplash.com/%s?auto=format&fit=crop&w=420&q=58'

# Всё уходит в один файл, поэтому вес критичен: площадка отдаёт страницу целиком.
# Ширина подобрана под фактический размер на экране с запасом на retina;
# подложка сильно размывается в CSS, ей хватает совсем маленькой картинки.
SHRINK = {
    'interior.jpg': (480, 45),   # фон под стеклом, blur(28px)
    'splash.jpg':   (760, 60),
    'auth.jpg':     (760, 60),
    'facade.jpg':   (560, 60),
    'bonus-band.jpg': (560, 60),
}
SHRINK_DEFAULT = (560, 60)


def shrink(raw, rule, blur=0):
    """Ужимает картинку под фактический размер показа.

    blur — радиус предварительного размытия. Подложку выгоднее размыть здесь:
    в CSS `filter: blur(28px)` пересчитывается на каждом кадре и на слабых
    машинах подвешивает страницу, а результат визуально тот же.
    """
    from io import BytesIO
    from PIL import Image, ImageFilter
    max_w, quality = rule
    im = Image.open(BytesIO(raw))
    if im.mode != 'RGB':
        im = im.convert('RGB')
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    buf = BytesIO()
    im.save(buf, 'JPEG', quality=quality, optimize=True, progressive=True)
    out = buf.getvalue()
    return out if len(out) < len(raw) or blur else raw


def fetch(url):
    """Скачивает один раз и кэширует в .imgcache, чтобы пересборка была мгновенной."""
    os.makedirs(CACHE, exist_ok=True)
    key = re.sub(r'[^A-Za-z0-9]+', '_', url)[:120]
    path = os.path.join(CACHE, key)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return open(path, 'rb').read()
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
        ctype = r.headers.get('Content-Type', '').split(';')[0].strip()
    open(path, 'wb').write(data)
    open(path + '.type', 'w').write(ctype or 'image/jpeg')
    return data


def ctype_of(url):
    key = re.sub(r'[^A-Za-z0-9]+', '_', url)[:120]
    p = os.path.join(CACHE, key + '.type')
    if os.path.exists(p):
        return open(p).read().strip() or 'image/jpeg'
    return 'image/jpeg'


def data_uri(mime, raw):
    return 'data:%s;base64,%s' % (mime, base64.b64encode(raw).decode('ascii'))


def main():
    os.chdir(HERE)
    html = open(SRC, encoding='utf-8', newline='').read()
    entries = []
    total = 0

    # --- локальные фотографии ---
    names = sorted(set(re.findall(r'assets/([A-Za-z0-9_\-]+\.[a-z]+)', html)))
    for name in names:
        path = os.path.join('assets', name)
        if not os.path.exists(path):
            sys.exit('нет файла ' + path)
        src = open(path, 'rb').read()
        raw = shrink(src, SHRINK.get(name, SHRINK_DEFAULT), blur=22 if name == 'interior.jpg' else 0)
        entries.append(("'%s'" % name, data_uri('image/jpeg', raw)))
        total += len(raw)
        print('  локально  %-22s %6.1f -> %6.1f KB' % (name, len(src) / 1024, len(raw) / 1024))

    # --- снимки напитков через хелпер U('photo-...') ---
    ids = sorted(set(re.findall(r"U\('(photo-[A-Za-z0-9-]+)'\)", html)))
    for pid in ids:
        src = fetch(UNSPLASH_TPL % pid)
        raw = shrink(src, SHRINK_DEFAULT)
        entries.append(("'%s'" % pid, data_uri('image/jpeg', raw)))
        total += len(raw)
        print('  unsplash  %-22s %6.1f -> %6.1f KB' % (pid[:22], len(src) / 1024, len(raw) / 1024))

    # --- прямые внешние ссылки на картинки ---
    urls = sorted(set(re.findall(r'https://images\.(?:unsplash|pexels)\.com/[^"\'`)\s]+', html)))
    urls = [u for u in urls if '${' not in u]
    url_key = {}
    for i, u in enumerate(urls):
        src = fetch(u)
        raw = shrink(src, SHRINK_DEFAULT)
        url_key[u] = 'x%d' % i
        entries.append(("'x%d'" % i, data_uri('image/jpeg', raw)))
        total += len(raw)
        print('  внешняя   %-22s %6.1f -> %6.1f KB' % (u.split('/')[-1][:22], len(src) / 1024, len(raw) / 1024))

    table = 'const W = {\n' + ',\n'.join(
        "  %s: '%s'" % (k, v) for k, v in entries) + '\n};\n'

    # подстановки: сначала длинные литералы, потом хелпер и локальные пути
    for u, k in url_key.items():
        html = html.replace("'" + u + "'", "W['%s']" % k)
        html = html.replace('"' + u + '"', '"${W[\'%s\']}"' % k)
    html = re.sub(r"U\('(photo-[A-Za-z0-9-]+)'\)", lambda m: "W['%s']" % m.group(1), html)
    html = re.sub(r'src="assets/([A-Za-z0-9_\-]+\.[a-z]+)"',
                  lambda m: 'src="${W[\'%s\']}"' % m.group(1), html)
    html = re.sub(r"'assets/([A-Za-z0-9_\-]+\.[a-z]+)'",
                  lambda m: "W['%s']" % m.group(1), html)

    # подложка уже размыта на этапе сборки — снимаем дорогой рантайм-фильтр
    if 'filter:blur(28px) saturate(.7)' not in html:
        sys.exit('не найден фильтр подложки — проверьте index.html')
    html = html.replace('filter:blur(28px) saturate(.7)', 'filter:saturate(.7)')

    # Бесконечный ken-burns заставляет браузер перерисовывать слой без остановки,
    # а таких слоёв на главной несколько (фон входа, витрина, галерея). Поверх
    # стеклянных панелей с backdrop-filter это заметная постоянная нагрузка,
    # поэтому наплыв проигрывается один раз — визуально почти то же самое.
    html, n = re.subn(r'animation:kenburns [^;"]+ infinite alternate',
                      'animation:zoomIn 14s ease-out both', html)
    if n == 0:
        sys.exit('не найдены анимации kenburns — проверьте index.html')
    print('  бесконечных анимаций обезврежено: %d' % n)

    left = re.findall(r'https://images\.(?:unsplash|pexels)\.com/[^"\'`)\s]*', html)
    left = [x for x in left if '${' not in x]
    if left or 'assets/' in html:
        sys.exit('остались внешние ссылки: %s' % set(left + (['assets/'] if 'assets/' in html else [])))

    anchor = "'use strict';\n"
    html = html.replace(anchor, anchor + table, 1)
    open(OUT, 'w', encoding='utf-8', newline='').write(html)
    print('\n%s — %.1f MB (картинок вшито: %d, %.1f MB исходников)'
          % (OUT, os.path.getsize(OUT) / 1024 / 1024, len(entries), total / 1024 / 1024))


if __name__ == '__main__':
    main()
