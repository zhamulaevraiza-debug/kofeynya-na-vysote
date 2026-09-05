"""Иконки PWA без внешних библиотек: тёмный квадрат и золотые горы, как в логотипе.

    python make-icons.py

Пишет icons/icon-192.png, icons/icon-512.png (maskable — фон во всю площадь)
и icons/icon-180.png для apple-touch-icon.
"""
import os
import struct
import zlib

BG = (0x1a, 0x15, 0x12)
GOLD = (0xd9, 0xbc, 0x8c)
CREAM = (0xf3, 0xed, 0xe4)

# Ломаная логотипа в координатах 0..100 (две горы и маленькая правая), толщина в % стороны.
PEAKS = [(0.10, 0.66), (0.30, 0.34), (0.41, 0.50), (0.50, 0.38), (0.63, 0.60)]
SMALL = [(0.58, 0.66), (0.72, 0.46), (0.88, 0.66)]


def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    l2 = vx * vx + vy * vy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / l2))
    dx, dy = px - (ax + t * vx), py - (ay + t * vy)
    return (dx * dx + dy * dy) ** 0.5


def polyline_dist(px, py, pts):
    return min(seg_dist(px, py, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]) for i in range(len(pts) - 1))


def render(size):
    w = size * 0.075  # толщина линии
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            px, py = (x + 0.5) / size, (y + 0.5) / size
            d = min(polyline_dist(px, py, PEAKS), polyline_dist(px, py, SMALL)) * size
            # мягкий край: 1 px антиалиасинга
            a = max(0.0, min(1.0, (w / 2 + 0.5) - d))
            r = int(BG[0] + (GOLD[0] - BG[0]) * a)
            g = int(BG[1] + (GOLD[1] - BG[1]) * a)
            b = int(BG[2] + (GOLD[2] - BG[2]) * a)
            row += bytes((r, g, b))
        rows.append(bytes(row))
    return rows


def png(size, rows):
    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    raw = b''.join(b'\x00' + r for r in rows)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, 'icons')
    os.makedirs(out, exist_ok=True)
    for size in (180, 192, 512):
        path = os.path.join(out, 'icon-%d.png' % size)
        with open(path, 'wb') as fh:
            fh.write(png(size, render(size)))
        print('  %s  %.1f KB' % (os.path.basename(path), os.path.getsize(path) / 1024))


if __name__ == '__main__':
    main()
