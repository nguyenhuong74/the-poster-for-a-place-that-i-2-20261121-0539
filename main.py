#!/usr/bin/env python3
"""VELMARA - Isle of the Glass Tides.

A travel poster for a place that does not exist, drawn from scratch with
only the Python standard library. Writes a 1024x1024 PNG to
/output/entry.png (or $OUTPUT_PATH when set, for local testing).

The place: Velmara, a floating isle above a glass sea, crowned by a
crystal spire whose light guides sailors home at sunset.
"""

import os
import struct
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- palette
CREAM = (250, 240, 210)
GOLD = (245, 196, 110)
PALE_GOLD = (250, 214, 150)


def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def clamp(v, lo=0, hi=255):
    return lo if v < lo else hi if v > hi else v


# ------------------------------------------------------------------- image
class Canvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = color[0]
            self.px[i + 1] = color[1]
            self.px[i + 2] = color[2]

    def blend(self, x, y, color, alpha):
        """Alpha-blend color over the pixel at (x, y). alpha in 0..1."""
        if 0 <= x < self.w and 0 <= y < self.h and alpha > 0:
            i = (y * self.w + x) * 3
            for k in range(3):
                self.px[i + k] = clamp(
                    int(self.px[i + k] * (1.0 - alpha) + color[k] * alpha)
                )

    def hline(self, x0, x1, y, color):
        if y < 0 or y >= self.h:
            return
        x0 = max(0, x0)
        x1 = min(self.w - 1, x1)
        for x in range(x0, x1 + 1):
            self.set(x, y, color)

    def vgrad(self, y0, y1, stops):
        """Vertical gradient between (pos, color) stops, pos in 0..1."""
        span = max(1, y1 - y0)
        for y in range(y0, y1 + 1):
            t = (y - y0) / span
            for s in range(len(stops) - 1):
                p0, c0 = stops[s]
                p1, c1 = stops[s + 1]
                if p0 <= t <= p1:
                    f = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
                    col = lerp(c0, c1, f)
                    break
            else:
                col = stops[-1][1]
            self.hline(0, self.w - 1, y, col)

    def circle(self, cx, cy, r, color, alpha=1.0):
        for y in range(cy - r, cy + r + 1):
            dy = y - cy
            dx = int((r * r - dy * dy) ** 0.5) if abs(dy) <= r else 0
            for x in range(cx - dx, cx + dx + 1):
                if alpha >= 1.0:
                    self.set(x, y, color)
                else:
                    self.blend(x, y, color, alpha)

    def polygon(self, points, color, alpha=1.0):
        """Scanline fill of a simple polygon."""
        ys = [p[1] for p in points]
        for y in range(max(0, min(ys)), min(self.h - 1, max(ys)) + 1):
            xs = []
            n = len(points)
            for i in range(n):
                x0, y0 = points[i]
                x1, y1 = points[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / (y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                for x in range(int(xs[k]), int(xs[k + 1]) + 1):
                    if alpha >= 1.0:
                        self.set(x, y, color)
                    else:
                        self.blend(x, y, color, alpha)

    def ellipse(self, cx, cy, rx, ry, color, alpha=1.0):
        for y in range(cy - ry, cy + ry + 1):
            dy = (y - cy) / ry
            if abs(dy) > 1:
                continue
            dx = int(rx * (1 - dy * dy) ** 0.5)
            for x in range(cx - dx, cx + dx + 1):
                if alpha >= 1.0:
                    self.set(x, y, color)
                else:
                    self.blend(x, y, color, alpha)

    def line(self, x0, y0, x1, y1, color):
        """Bresenham line, for thin strokes such as birds."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy


# ------------------------------------------------------------- bitmap font
# 5x7 glyphs, rows of 5 bits, '#' = on.
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
}


def text_width(text, scale):
    return len(text) * 6 * scale - scale


def draw_text(cv, text, x, y, scale, color):
    for ci, ch in enumerate(text):
        glyph = FONT.get(ch.upper(), FONT[" "])
        ox = x + ci * 6 * scale
        for row in range(7):
            for col in range(5):
                if glyph[row][col] == "1":
                    for dy in range(scale):
                        for dx in range(scale):
                            cv.set(ox + col * scale + dx, y + row * scale + dy, color)


def draw_text_centered(cv, text, cx, y, scale, color, shadow=None):
    w = text_width(text, scale)
    x = cx - w // 2
    if shadow is not None:
        draw_text(cv, text, x + scale // 3 + 2, y + scale // 3 + 3, scale, shadow)
    draw_text(cv, text, x, y, scale, color)
    return w


# ------------------------------------------------------------ deterministic
def lcg(seed):
    """Tiny deterministic pseudo-random generator (LCG)."""
    state = seed & 0xFFFFFFFF

    def next_int(n):
        nonlocal state
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        return state % n

    return next_int


# ------------------------------------------------------------------- scene
def build():
    cv = Canvas(W, H)

    # --- sky: indigo dusk melting into a golden sunset band
    cv.vgrad(0, 648, [
        (0.00, (22, 26, 72)),
        (0.30, (66, 46, 104)),
        (0.52, (150, 66, 102)),
        (0.68, (214, 104, 84)),
        (0.84, (240, 158, 92)),
        (1.00, (250, 202, 128)),
    ])

    # --- stars in the upper sky (fixed seed: fully deterministic)
    rnd = lcg(20261121)
    for _ in range(150):
        sx = rnd(W)
        sy = rnd(300)
        bright = 140 + rnd(115)
        size = 1 if rnd(4) else 2
        for dy in range(size):
            for dx in range(size):
                cv.blend(sx + dx, sy + dy, (255, 244, 214), bright / 255.0 * 0.9)

    # --- two moons, kept clear of the title: big moon top-right,
    # small crescent low on the left
    cv.circle(888, 92, 58, (246, 238, 214))
    cv.circle(870, 78, 46, (232, 220, 190))
    cv.circle(866, 74, 10, (214, 200, 168))
    cv.circle(906, 108, 7, (214, 200, 168))
    cv.circle(900, 66, 6, (222, 208, 176))
    cv.circle(140, 316, 28, (250, 240, 205))
    cv.circle(150, 310, 24, (66, 46, 104))  # crescent cut-out

    # --- distant mountain ridges, layered silhouettes
    cv.polygon([(0, 648), (120, 520), (240, 600), (360, 500), (520, 620),
                (700, 540), (860, 630), (1024, 560), (1024, 648)],
               (58, 40, 86))
    cv.polygon([(0, 648), (90, 580), (220, 630), (380, 566), (540, 636),
                (720, 580), (900, 640), (1024, 600), (1024, 648)],
               (44, 30, 70))

    # --- low sun, glowing, sinking into the glass sea; drawn after the
    # ridges so its disc stays visible above the horizon line
    cv.circle(300, 606, 78, (250, 190, 110), alpha=0.25)
    cv.circle(300, 606, 60, (252, 205, 120), alpha=0.45)
    cv.circle(300, 606, 46, (255, 218, 138))

    # --- the glass sea
    cv.vgrad(648, 1023, [
        (0.00, (30, 74, 96)),
        (0.35, (20, 56, 80)),
        (0.70, (14, 38, 60)),
        (1.00, (10, 26, 46)),
    ])

    # sun path shimmering on the water (soft blended streaks)
    for i in range(46):
        y = 660 + i * 8
        wdt = 26 + (i * 7) % 90
        alpha = 0.5 - i * 0.01
        if alpha <= 0:
            break
        for x in range(300 - wdt // 2, 300 + wdt // 2 + 1):
            cv.blend(x, y, (250, 196, 120), alpha)

    # --- the floating isle of Velmara (the landmark)
    # rocky underside tapering to a point, hovering above the sea
    cv.polygon([(300, 560), (724, 560), (660, 640), (590, 716), (540, 762),
                (512, 782), (484, 762), (434, 716), (364, 640)],
               (46, 38, 72))
    cv.polygon([(330, 560), (694, 560), (640, 630), (580, 700), (540, 748),
                (512, 766), (484, 748), (444, 700), (384, 630)],
               (60, 50, 90))
    # grassy plateau top
    cv.ellipse(512, 560, 216, 26, (74, 128, 92))
    cv.ellipse(512, 556, 216, 22, (96, 152, 108))
    # rock strata lines on the underside
    for k, yy in enumerate((600, 640, 680, 716)):
        cv.hline(360 + k * 22, 664 - k * 22, yy, (38, 32, 62))

    # --- the crystal spire: tall, glowing, the isle's beacon
    cv.polygon([(512, 330), (470, 560), (554, 560)], (168, 224, 238), alpha=0.85)
    cv.polygon([(512, 330), (492, 560), (522, 560)], (214, 242, 250), alpha=0.9)
    cv.polygon([(512, 330), (506, 560), (518, 560)], (255, 255, 255), alpha=0.95)
    cv.circle(512, 322, 16, (255, 250, 210))
    cv.circle(512, 322, 30, (255, 236, 170), alpha=0.35)
    # light beams fanning from the spire tip (kept faint and narrow so
    # they do not cut through the title above)
    cv.polygon([(512, 322), (448, 210), (472, 210)], (255, 240, 190), alpha=0.07)
    cv.polygon([(512, 322), (552, 210), (576, 210)], (255, 240, 190), alpha=0.07)
    cv.polygon([(512, 322), (500, 200), (524, 200)], (255, 240, 190), alpha=0.10)

    # --- small domed houses on the plateau, warm windows lit
    # (dome drawn first so the house body hides its lower half)
    for hx, hw, hh in ((352, 46, 34), (420, 56, 42), (596, 52, 38), (664, 44, 32)):
        cv.circle(hx + hw // 2, 560 - hh, hw // 2, (240, 190, 120))
        cv.polygon([(hx, 560), (hx, 560 - hh), (hx + hw // 2, 560 - hh - 18),
                    (hx + hw, 560 - hh), (hx + hw, 560)], (232, 214, 178))
        cv.circle(hx + hw // 2, 560 - hh - hw // 2 - 2, 3, (240, 190, 120))
        for wx in range(hx + 8, hx + hw - 6, 14):
            cv.hline(wx, wx + 6, 560 - 16, (255, 214, 120))

    # --- waterfalls spilling off the isle into the sea: solid pale
    # streaks with a bright core, plus a splash ring where they land
    for fx in (392, 512, 632):
        for y in range(566, 698):
            cv.blend(fx - 5, y, (170, 220, 236), 0.9)
            cv.blend(fx - 4, y, (170, 220, 236), 0.9)
            cv.blend(fx - 3, y, (190, 228, 240), 0.9)
            cv.blend(fx - 2, y, (190, 228, 240), 0.9)
            cv.blend(fx - 1, y, (225, 242, 248), 0.95)
            cv.blend(fx, y, (225, 242, 248), 0.95)
            cv.blend(fx + 1, y, (225, 242, 248), 0.95)
            cv.blend(fx + 2, y, (190, 228, 240), 0.9)
            cv.blend(fx + 3, y, (190, 228, 240), 0.9)
            cv.blend(fx + 4, y, (170, 220, 236), 0.9)
            cv.blend(fx + 5, y, (170, 220, 236), 0.9)
        cv.ellipse(fx, 704, 26, 8, (200, 232, 242), alpha=0.8)

    # --- the isle's reflection in the glass sea
    cv.polygon([(430, 800), (594, 800), (560, 900), (512, 940), (464, 900)],
               (34, 48, 76), alpha=0.55)
    cv.hline(470, 554, 830, (96, 152, 108))
    cv.hline(486, 538, 868, (168, 224, 238))

    # --- two small sailboats on the glass sea
    for bx, by, s in ((180, 760, 1.0), (830, 820, 0.8)):
        hull_w = int(64 * s)
        cv.polygon([(bx - hull_w // 2, by), (bx + hull_w // 2, by),
                    (bx + hull_w // 3, by + int(14 * s)),
                    (bx - hull_w // 3, by + int(14 * s))], (40, 26, 48))
        cv.polygon([(bx, by - int(52 * s)), (bx, by - 2),
                    (bx + int(34 * s), by - 2)], (250, 240, 210))
        cv.polygon([(bx - 2, by - int(52 * s)), (bx - 2, by - 2),
                    (bx - int(26 * s), by - 2)], (232, 190, 130))

    # --- birds crossing the sunset, drawn as two thin strokes
    for bx, by, s in ((240, 380, 16), (300, 350, 12), (700, 300, 14),
                       (760, 340, 11), (150, 440, 12)):
        cv.line(bx - s, by, bx, by - 6, (30, 24, 52))
        cv.line(bx, by - 6, bx + s, by, (30, 24, 52))

    # --- foreground cliff silhouettes framing the bottom corners
    cv.polygon([(0, 1024), (0, 880), (120, 920), (210, 980), (260, 1024)],
               (16, 14, 34))
    cv.polygon([(1024, 1024), (1024, 900), (920, 936), (830, 990), (790, 1024)],
               (16, 14, 34))

    # --- type: the place name, big and legible, then one quiet line
    draw_text_centered(cv, "VELMARA", 512, 96, 14, CREAM, shadow=(28, 20, 52))
    draw_text_centered(cv, "ISLE OF THE GLASS TIDES", 512, 226, 4,
                       PALE_GOLD, shadow=(28, 20, 52))
    cv.hline(512 - 150, 512 + 150, 262, GOLD)
    cv.hline(512 - 150, 512 + 150, 263, GOLD)

    return cv


# --------------------------------------------------------------------- png
def write_png(cv, path):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)  # filter: none
        raw += cv.px[y * stride:(y + 1) * stride]
    data = zlib.compress(bytes(raw), 9)

    def chunk(kind, payload):
        out = struct.pack(">I", len(payload)) + kind + payload
        out += struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", data)
    png += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    out = os.environ.get("OUTPUT_PATH", "/output/entry.png")
    cv = build()
    size = write_png(cv, out)
    print(f"wrote {out} ({cv.w}x{cv.h}, {size} bytes)")


if __name__ == "__main__":
    main()
