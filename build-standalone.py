"""Собирает автономную копию приложения: фотографии вшиваются в файл.

    python build-standalone.py

index.html берёт фото из папки assets, поэтому напрямую с диска (file://)
показывает пустые места. Здесь каждая фотография кодируется в data: URI и
кладётся в таблицу A один раз, а ссылки на assets/ заменяются на A['имя'].
Результат открывается двойным кликом и пересылается одним файлом.
"""
import base64
import mimetypes
import os
import re
import sys

SRC = 'index.html'
OUT = 'Кофейня на высоте — автономная.html'
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    os.chdir(HERE)
    html = open(SRC, encoding='utf-8', newline='').read()

    names = sorted(set(re.findall(r'assets/([A-Za-z0-9_\-]+\.[a-z]+)', html)))
    if not names:
        sys.exit('в index.html нет ссылок на assets/')

    entries = []
    for name in names:
        path = os.path.join('assets', name)
        if not os.path.exists(path):
            sys.exit('нет файла ' + path)
        mime = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        data = base64.b64encode(open(path, 'rb').read()).decode('ascii')
        entries.append("  '%s': 'data:%s;base64,%s'" % (name, mime, data))
        print('  вшито %-18s %7.1f KB' % (name, os.path.getsize(path) / 1024))

    table = 'const A = {\n' + ',\n'.join(entries) + '\n};\n'

    # ссылки в шаблонных строках и в обычных строковых литералах
    html = re.sub(r'src="assets/([A-Za-z0-9_\-]+\.[a-z]+)"',
                  lambda m: 'src="${A[\'%s\']}"' % m.group(1), html)
    html = re.sub(r"'assets/([A-Za-z0-9_\-]+\.[a-z]+)'",
                  lambda m: "A['%s']" % m.group(1), html)

    left = re.findall(r'assets/[A-Za-z0-9_\-]+\.[a-z]+', html)
    if left:
        sys.exit('остались необработанные ссылки: %s' % set(left))

    anchor = "'use strict';\n"
    if anchor not in html:
        sys.exit('не найдено место для таблицы изображений')
    html = html.replace(anchor, anchor + table, 1)

    open(OUT, 'w', encoding='utf-8', newline='').write(html)
    print('\n%s — %.1f MB' % (OUT, os.path.getsize(OUT) / 1024 / 1024))


if __name__ == '__main__':
    main()
