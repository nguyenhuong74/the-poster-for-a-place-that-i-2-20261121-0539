#!/usr/bin/env python3
"""VELDARA - a travel poster for a place that does not exist.

Draws, in pure Python 3 standard library, a 1024x1024 travel poster for
Veldara: a lantern-lit village perched on a cliff-top valley above a sea
of clouds, where the Skyfall waterfall pours off the cliff edge and
vanishes into the cloud sea below, at golden hour.

No network, no third-party packages, no randomness: the same bytes come
out every run. Writes /output/entry.png (creating /output if needed).
"""

import hashlib
import os
import struct
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- pixels

buf = bytearray(W * H * 3)


def px(x, y, r, g, b):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b


def blend_px(x, y, r, g, b, a):
    """Paint colour (r,g,b) over the pixel at (x,y) with opacity a (0..1)."""
    if 0 <= x < W and 0 <= y < H and a > 0.0:
        i = (y * W + x) * 3
        buf[i] = int(buf[i] * (1.0 - a) + r * a)
        buf[i + 1] = int(buf[i + 1] * (1.0 - a) + g * a)
        buf[i + 2] = int(buf[i + 2] * (1.0 - a) + b * a)


def rect(x0, y0, x1, y1, col):
    r, g, b = col
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(W, x1)
    y1 = min(H, y1)
    for y in range(y0, y1):
        base = (y * W + x0) * 3
        for x in range(x0, x1):
            i = base + (x - x0) * 3
            buf[i] = r
            buf[i + 1] = g
            buf[i + 2] = b


def hline(x0, x1, y, col):
    if 0 <= y < H:
        for x in range(max(0, x0), min(W, x1)):
            px(x, y, *col)


def disc(cx, cy, rad, col):
    r, g, b = col
    for y in range(max(0, cy - rad), min(H, cy + rad + 1)):
        dy = y - cy
        dx = int((rad * rad - dy * dy) ** 0.5)
        for x in range(max(0, cx - dx), min(W, cx + dx + 1)):
            px(x, y, r, g, b)


def disc_blend(cx, cy, rad, col, a):
    r, g, b = col
    for y in range(max(0, cy - rad), min(H, cy + rad + 1)):
        dy = y - cy
        dx = int((rad * rad - dy * dy) ** 0.5)
        for x in range(max(0, cx - dx), min(W, cx + dx + 1)):
            blend_px(x, y, r, g, b, a)


def ellipse(cx, cy, rx, ry, col):
    r, g, b = col
    for y in range(max(0, cy - ry), min(H, cy + ry + 1)):
        dy = (y - cy) / ry
        dx = int(rx * (1.0 - dy * dy) ** 0.5)
        for x in range(max(0, cx - dx), min(W, cx + dx + 1)):
            px(x, y, r, g, b)


def poly(points, col):
    """Scanline fill of a simple polygon given as [(x, y), ...]."""
    r, g, b = col
    ys = [p[1] for p in points]
    for y in range(max(0, min(ys)), min(H, max(ys) + 1)):
        xs = []
        n = len(points)
        for k in range(n):
            x0, y0 = points[k]
            x1, y1 = points[(k + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            for x in range(max(0, int(xs[k])), min(W, int(xs[k + 1]) + 1)):
                px(x, y, r, g, b)


def line(x0, y0, x1, y1, col):
    """Bresenham line, 1px wide."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        px(x, y, *col)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def lerp(c0, c1, t):
    return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))


def vgrad(y0, y1, c_top, c_bot):
    for y in range(max(0, y0), min(H, y1)):
        t = (y - y0) / max(1, y1 - y0 - 1)
        col = lerp(c_top, c_bot, t)
        hline(0, W, y, col)


# ------------------------------------------------------------------ font
# Hand-drawn 5x7 bitmap glyphs, one string per row, '#' = ink.
GLYPHS = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "##.##", ".###.", "..#..", "..#.."),
}


def text_width(s, scale, gap):
    return len(s) * 5 * scale + (len(s) - 1) * gap


def draw_text(s, x, y, scale, gap, col):
    for ci, ch in enumerate(s):
        glyph = GLYPHS.get(ch)
        if glyph is None:
            continue
        ox = x + ci * (5 * scale + gap)
        for row in range(7):
            for c in range(5):
                if glyph[row][c] == "#":
                    rect(ox + c * scale, y + row * scale,
                         ox + (c + 1) * scale, y + (row + 1) * scale, col)


# ------------------------------------------------------------------ scene

def draw_poster():
    # --- sky: deep indigo dusk at the top melting into amber at the horizon
    vgrad(0, 340, (26, 38, 79), (94, 74, 122))
    vgrad(340, 660, (94, 74, 122), (240, 163, 94))

    # --- a few early stars high up
    for sx, sy in [(90, 60), (210, 110), (330, 45), (470, 90), (560, 40),
                   (880, 70), (950, 140), (760, 110), (150, 180), (640, 55)]:
        px(sx, sy, 255, 240, 200)
        px(sx + 1, sy, 255, 240, 200)
        px(sx, sy + 1, 255, 240, 200)

    # --- low sun with a soft halo, sinking toward the cloud sea
    disc_blend(700, 505, 225, (255, 190, 110), 0.10)
    disc_blend(700, 505, 165, (255, 205, 130), 0.16)
    disc_blend(700, 505, 125, (255, 220, 150), 0.28)
    disc(700, 505, 92, (255, 236, 178))

    # --- distant ridge, far side of the valley, catching the last light
    poly([(0, 660), (0, 620), (120, 585), (260, 615), (400, 580),
          (560, 620), (700, 590), (860, 625), (1024, 595), (1024, 660)],
         (96, 70, 110))
    poly([(0, 660), (0, 640), (180, 615), (360, 640), (540, 610),
          (760, 645), (1024, 618), (1024, 660)], (70, 52, 96))

    # --- the cloud sea: a warm base, then billowing rows of cloud
    vgrad(660, 1024, (250, 205, 150), (232, 168, 128))
    cloud_rows = [
        (700, (255, 233, 196), 150, 46),
        (780, (251, 217, 168), 170, 52),
        (860, (244, 193, 147), 180, 56),
        (950, (233, 169, 131), 190, 60),
    ]
    for cy, col, rx, ry in cloud_rows:
        x = -140
        while x < W + 140:
            ellipse(x, cy, rx, ry, col)
            x += 250
        # second offset row for fullness
        x = -20
        while x < W + 140:
            ellipse(x, cy + 26, rx - 40, ry - 14, col)
            x += 260

    # --- Veldara's cliff: terraced rock rising out of the clouds, left side
    terraces = [
        # (y_top, y_bot, x_right_top, x_right_bot, colour)
        (606, 668, 448, 470, (122, 85, 96)),
        (668, 730, 470, 492, (107, 71, 83)),
        (730, 800, 492, 514, (92, 61, 73)),
        (800, 880, 514, 536, (78, 53, 64)),
        (880, 1024, 536, 560, (64, 45, 56)),
    ]
    for y0, y1, xr0, xr1, col in terraces:
        poly([(0, y0), (xr0, y0), (xr1, y1), (0, y1)], col)
    # sunlit rim along the cliff top edge
    poly([(0, 606), (448, 606), (452, 614), (0, 614)], (255, 205, 140))

    # --- the Skyfall: the waterfall pouring off the cliff edge into cloud
    poly([(398, 606), (432, 606), (438, 700), (428, 800), (404, 800),
          (392, 700)], (207, 232, 242))
    poly([(406, 606), (420, 606), (424, 700), (418, 790), (408, 790),
          (402, 700)], (240, 248, 250))
    ellipse(416, 806, 46, 16, (245, 238, 225))
    ellipse(416, 800, 30, 10, (255, 250, 238))

    # --- the village on the cliff top: small houses, warm lit windows
    houses = [
        (52, 566, 30, 26), (96, 572, 26, 22), (136, 562, 32, 28),
        (182, 570, 26, 22), (222, 564, 30, 26), (266, 572, 26, 22),
        (306, 566, 30, 26),
    ]
    for hx, hy, hw, hh in houses:
        rect(hx, hy, hx + hw, hy + hh, (242, 216, 160))          # wall
        poly([(hx - 3, hy), (hx + hw // 2, hy - 14), (hx + hw + 3, hy)],
             (58, 47, 69))                                        # roof
        rect(hx + 6, hy + 8, hx + 12, hy + 15, (255, 214, 106))   # window
        rect(hx + hw - 12, hy + 8, hx + hw - 6, hy + 15, (255, 214, 106))
    # the watchtower at the cliff edge, lantern lit
    rect(352, 540, 368, 606, (242, 216, 160))
    poly([(348, 540), (360, 522), (372, 540)], (58, 47, 69))
    rect(356, 552, 364, 560, (255, 214, 106))
    disc(360, 516, 5, (255, 214, 106))
    disc_blend(360, 516, 12, (255, 214, 106), 0.35)

    # --- dark pines on the cliff top
    for tx in (30, 160, 250, 330):
        poly([(tx, 606), (tx + 10, 566), (tx + 20, 606)], (38, 52, 48))
        poly([(tx + 3, 592), (tx + 10, 560), (tx + 17, 592)], (38, 52, 48))

    # --- birds crossing the evening sky
    bird_col = (46, 42, 66)
    for bx, by, s in [(180, 300, 14), (240, 260, 11), (520, 330, 13),
                      (860, 280, 12), (920, 350, 10)]:
        line(bx - s, by, bx, by - 6, bird_col)
        line(bx, by - 6, bx + s, by, bird_col)

    # --- the place name, large, set into the sky above the valley
    name = "VELDARA"
    scale = 13
    gap = 13
    nx = (W - text_width(name, scale, gap)) // 2
    ny = 84
    shadow = (30, 38, 79)
    for dx, dy in ((-4, 0), (4, 0), (0, -4), (0, 4), (-3, -3), (3, 3)):
        draw_text(name, nx + dx, ny + dy, scale, gap, shadow)
    draw_text(name, nx, ny, scale, gap, (255, 242, 207))

    # --- thin cream frame, like a printed poster border
    for t in range(3):
        rect(26 + t, 26 + t, W - 26 - t, 29 + t, (255, 242, 207))
        rect(26 + t, H - 29 - t, W - 26 - t, H - 26 - t, (255, 242, 207))
        rect(26 + t, 26 + t, 29 + t, H - 26 - t, (255, 242, 207))
        rect(W - 29 - t, 26 + t, W - 26 - t, H - 26 - t, (255, 242, 207))


# -------------------------------------------------------------------- PNG

def chunk(tag, data):
    out = struct.pack(">I", len(data)) + tag + data
    out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return out


def encode_png():
    raw = bytearray()
    prev = bytes(W * 3)
    for y in range(H):
        row = bytes(buf[y * W * 3:(y + 1) * W * 3])
        if y == 0:
            raw.append(0)
            raw += row
        else:
            raw.append(2)  # filter Up: store difference from the row above
            raw += bytes((b - p) & 0xFF for b, p in zip(row, prev))
        prev = row
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    return png


def main():
    draw_poster()
    data = encode_png()
    os.makedirs("/output", exist_ok=True)
    with open("/output/entry.png", "wb") as f:
        f.write(data)
    print("wrote /output/entry.png")
    print("bytes:", len(data))
    print("sha256:", hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main()
