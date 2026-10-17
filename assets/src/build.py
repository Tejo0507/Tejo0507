"""Generates every SVG in assets/ for the profile README.

One visual unit runs through all of them: a square cell coloured on the
diverging RdBu scale used for activation heatmaps. Warm is positive, cool is
negative, the midpoint is left empty so the page shows through.

    python assets/src/build.py [path/to/font.ttf]

Needs Pillow for the hero lettering (rasterised once, then committed). The
default font is Bahnschrift Bold, which ships with Windows.
"""

import math
import random
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent

# 9-class diverging scale, index 4 is the neutral midpoint (never drawn).
SCALE = {
    "light": ["#2166ac", "#4393c3", "#92c5de", "#d1e5f0", None,
              "#fddbc7", "#f4a582", "#d6604d", "#b2182b"],
    "dark": ["#79b4ef", "#4f8ccb", "#33618f", "#1f3550", None,
             "#4a2621", "#7c3a30", "#b9533f", "#f2735c"],
}
INK = {"light": "#1f2328", "dark": "#e6edf3"}
MUTED = {"light": "#59636e", "dark": "#9198a1"}
FAINT = {"light": "#d1d9e0", "dark": "#3d444d"}
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
REDUCED = "@media (prefers-reduced-motion: reduce)"


def bucket(v):
    return max(0, min(8, round(v * 4) + 4))


def cells_path(cells, pitch, size):
    return "".join(f"M{x * pitch:g} {y * pitch:g}h{size:g}v{size:g}h-{size:g}z" for x, y in cells)


def svg(w, h, label, body, style=""):
    css = f"<style>{style}</style>" if style else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{label}">{css}{body}</svg>\n')


def text(x, y, s, theme, size=15, fill=None, anchor="start", weight=400, extra=""):
    fill = fill or MUTED[theme]
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" {extra}>{s}</text>')


def write(name, theme, content):
    (OUT / f"{name}-{theme}.svg").write_text(content, encoding="utf-8")


def gaussian_blur(grid, sigma):
    r = max(1, int(3 * sigma))
    k = [math.exp(-(i * i) / (2 * sigma * sigma)) for i in range(-r, r + 1)]
    s = sum(k)
    k = [v / s for v in k]
    h, w = len(grid), len(grid[0])

    def at(g, y, x):
        return g[min(h - 1, max(0, y))][min(w - 1, max(0, x))]

    tmp = [[sum(k[i] * at(grid, y, x + i - r) for i in range(len(k))) for x in range(w)] for y in range(h)]
    return [[sum(k[i] * at(tmp, y + i - r, x) for i in range(len(k))) for x in range(w)] for y in range(h)]


# --- hero: the name decoded out of an activation map ------------------------

def lettering(word, cols, rows, font_path, sub=8):
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(font_path, 400)
    try:
        font.set_variation_by_name("Bold")
    except (OSError, AttributeError):
        pass
    l, t, r, b = font.getbbox(word)
    scale = (rows - 3) * sub / (b - t)
    font = ImageFont.truetype(font_path, int(400 * scale))
    try:
        font.set_variation_by_name("Bold")
    except (OSError, AttributeError):
        pass
    l, t, r, b = font.getbbox(word)
    img = Image.new("L", (cols * sub, rows * sub), 0)
    ImageDraw.Draw(img).text((2 * sub - l, int(1.5 * sub) - t), word, font=font, fill=255)
    px = img.load()
    return [[sum(px[x * sub + i, y * sub + j] for i in range(sub) for j in range(sub)) / (255 * sub * sub)
             for x in range(cols)] for y in range(rows)]


def hero(font_path):
    cols, rows, pitch, size = 125, 30, 8, 6.5
    rnd = random.Random(507)
    mask = lettering("tejo", cols, rows, font_path)
    surround = gaussian_blur(mask, 1.6)
    noise = gaussian_blur([[rnd.gauss(0, 1) for _ in range(cols)] for _ in range(rows)], 0.9)
    peak = max(abs(v) for row in noise for v in row)

    def residue(x):
        # the map is quiet next to the name and stays faintly active towards the right edge
        t = min(1.0, max(0.0, (x / cols - 0.42) / 0.58))
        return 0.06 + 0.42 * t * t * (3 - 2 * t)

    # final state: centre-surround response of the letters, plus residue
    final = [[1.25 * mask[y][x] - 1.1 * surround[y][x] + 0.5 * mask[y][x] * surround[y][x]
              + residue(x) * noise[y][x] / peak for x in range(cols)] for y in range(rows)]
    start = [[0.95 * noise[y][x] / peak for x in range(cols)] for y in range(rows)]

    band, step, lead, cycle = 3, 0.048, 0.4, 12
    bands = math.ceil(cols / band)
    w, h = cols * pitch, rows * pitch
    for theme, scale in SCALE.items():
        groups = []
        for b in range(bands):
            delay = lead + b * step
            for cls, field in (("n", start), ("f", final)):
                by = {}
                for x in range(b * band, min(cols, (b + 1) * band)):
                    for y in range(rows):
                        i = bucket(field[y][x])
                        if scale[i]:
                            by.setdefault(i, []).append((x, y))
                paths = "".join(f'<path fill="{scale[i]}" d="{cells_path(c, pitch, size)}"/>' for i, c in sorted(by.items()))
                groups.append(f'<g class="{cls}" style="animation-delay:{delay:.2f}s">{paths}</g>')
        probe = f'<rect class="p" x="-1" y="0" width="2" height="{h - 2}" fill="{INK[theme]}" style="animation-delay:{lead}s"/>'
        sweep = bands * step
        style = (
            f".n,.f{{animation:{cycle}s infinite both}}.n{{animation-name:out}}.f{{opacity:0;animation-name:in}}"
            f".p{{opacity:0;animation:probe {cycle}s linear infinite both}}"
            "@keyframes in{0%{opacity:0}5%{opacity:1}86%{opacity:1}93%{opacity:0}100%{opacity:0}}"
            "@keyframes out{0%{opacity:1}5%{opacity:0}86%{opacity:0}93%{opacity:1}100%{opacity:1}}"
            f"@keyframes probe{{0%{{transform:translateX(0);opacity:.55}}"
            f"{sweep / cycle * 100:.1f}%{{transform:translateX({w}px);opacity:.55}}"
            f"{sweep / cycle * 100 + 0.5:.1f}%{{opacity:0;transform:translateX({w}px)}}100%{{opacity:0;transform:translateX({w}px)}}}}"
            f"{REDUCED}{{.n,.f,.p{{animation:none}}.n,.p{{opacity:0}}.f{{opacity:1}}}}"
        )
        write("hero", theme, svg(w, h - 2, "tejo, resolved out of an activation map", "".join(groups) + probe, style))


# --- morphism engine: only proved bridges are admitted ----------------------

def morphism():
    for theme, s in SCALE.items():
        p, c = 22, 18
        body = []
        # input payload: a JSON object whose score is a string
        body.append(text(0, 22, "JSON object", theme, 15, INK[theme], weight=600))
        body.append(text(0, 44, "score: \u201c91.34\u201d", theme, 14))
        body.append(f'<path fill="{s[6]}" d="{cells_path([(0, y) for y in range(3, 11)], p, c)}"/>')
        body.append(f'<path fill="{s[5]}" d="{cells_path([(1, y) for y in range(3, 11)], p, c)}"/>')
        # three candidate bridges drafted by the local model
        ys = (78, 140, 202)
        for k, y in enumerate(ys):
            ok = k == 1
            fill = s[7] if ok else s[2]
            body.append(f'<path d="M44 152 C 90 152, 90 {y + 9}, 130 {y + 9}" fill="none" stroke="{FAINT[theme]}" stroke-width="1.5"/>')
            body.append(f'<path fill="{fill}" d="{cells_path([(6 + i, 0) for i in range(5)], p, c)}" transform="translate(0 {y})"/>')
            if ok:
                body.append(f'<path d="M238 {y + 9} H 302" stroke="{s[7]}" stroke-width="2"/>')
            else:
                body.append(f'<path d="M238 {y + 9} H 256" stroke="{FAINT[theme]}" stroke-width="1.5"/>')
        body.append(text(132, ys[0] - 10, "candidate bridges", theme, 13))
        # the Z3 gate
        body.append(f'<rect x="258" y="66" width="4" height="168" fill="{INK[theme]}"/>')
        body.append(text(260, 254, "Z3", theme, 14, INK[theme], "middle", 600))
        body.append(text(304, 78, "unproved bridges", theme, 13))
        body.append(text(304, 96, "never run", theme, 13))
        # output: normalized float, plus what is kept
        body.append(f'<path fill="{s[8]}" d="{cells_path([(0, 0), (1, 0)], p, c)}" transform="translate(304 140)"/>')
        body.append(text(304, 186, "0.9134", theme, 15, INK[theme], weight=600))
        body.append(text(304, 206, "float, normalized", theme, 13))
        body.append(text(304, 226, "proof saved, cached", theme, 13))
        write("morphism", theme, svg(440, 262, "A string score is repaired into a float; of three candidate bridges, only the one Z3 proves is admitted", "".join(body)))


# --- answer-stable tail: generation keeps going after the answer settles ----

def tail():
    rnd = random.Random(11)
    pitch, size, cols = 14, 11, 30
    tokens, x, y = [], 0, 0
    while y < 9:
        n = rnd.choice((1, 2, 2, 3, 3, 4, 5))
        if x + n > cols:
            x, y = 0, y + 1
            if y >= 9:
                break
        tokens.extend((x + i, y) for i in range(n))
        x += n + 1
    settle = int(len(tokens) * 0.36)
    per, hold, cycle = 0.045, 2.6, 0
    appear = len(tokens) * per
    cycle = appear + hold + 1.2
    for theme, s in SCALE.items():
        body = []
        for k, (cx, cy) in enumerate(tokens):
            if k < settle:
                fill = s[rnd.choice((5, 5, 6, 6, 7))]
            elif k == settle:
                fill = s[8]
            else:
                fill = s[rnd.choice((2, 3, 3, 3))]
            body.append(f'<rect class="t" x="{cx * pitch}" y="{30 + cy * pitch * 1.6:g}" width="{size}" height="{size}" '
                        f'fill="{fill}" style="animation-delay:{k * per:.3f}s"/>')
        sx, sy = tokens[settle]
        mx, my = sx * pitch + size / 2, 30 + sy * pitch * 1.6
        body.append(f'<g class="t" style="animation-delay:{settle * per:.3f}s">'
                    f'<path d="M{mx} {my - 4} V 12" stroke="{INK[theme]}" stroke-width="1.5"/>'
                    + text(mx + 6, 18, "answer settles", theme, 13, INK[theme]) + "</g>")
        ly = 30 + 9 * pitch * 1.6 + 6
        body.append(f'<g class="t" style="animation-delay:{(settle + 20) * per:.3f}s">'
                    + text(0, ly + 8, "everything after it is the answer-stable tail", theme, 13) + "</g>")
        f = 100 / cycle
        style = (f".t{{opacity:0;animation:t {cycle:.2f}s infinite both}}"
                 f"@keyframes t{{0%{{opacity:0}}{0.6 * f:.2f}%{{opacity:1}}{(appear + hold) * f:.2f}%{{opacity:1}}"
                 f"{(appear + hold + 0.6) * f:.2f}%{{opacity:0}}100%{{opacity:0}}}}"
                 f"{REDUCED}{{.t{{animation:none;opacity:1}}}}")
        write("tail", theme, svg(440, int(ly + 16), "A reasoning trace drawn as tokens; after the answer settles, generation keeps going", "".join(body), style))


# --- paradox lab: pumping v and y pushes the string out of a^n b^n c^n -------

def pumping():
    pitch, size = 31, 27
    frames = [(1, True), (2, False), (3, False), (0, False)]
    hold = 2.4
    cycle = hold * len(frames)
    sup = {0: "\u2070", 1: "\u00b9", 2: "\u00b2", 3: "\u00b3", 4: "\u2074", 5: "\u2075"}
    for theme, s in SCALE.items():
        body = []
        for k, (i, member) in enumerate(frames):
            parts = [("a", "u", 2), ("a", "v", i), ("b", "y", i), ("b", "z", 2), ("c", "z", 3)]
            g, x = [], 0
            for ch, role, n in parts:
                for _ in range(n):
                    fill = s[7] if role == "v" else s[1] if role == "y" else None
                    if fill:
                        g.append(f'<rect x="{x * pitch}" y="40" width="{size}" height="{size}" fill="{fill}"/>')
                        col = "#ffffff"
                    else:
                        g.append(f'<rect x="{x * pitch + 0.75}" y="40.75" width="{size - 1.5}" height="{size - 1.5}" fill="none" stroke="{FAINT[theme]}" stroke-width="1.5"/>')
                        col = INK[theme]
                    g.append(text(x * pitch + size / 2, 59, ch, theme, 16, col, "middle", 600))
                    x += 1
            a, b = 2 + i, 2 + i
            word = f"a{sup[a]}b{sup[b]}c\u00b3"
            verdict = "is in L" if member else "is not in L"
            g.append(text(0, 22, f"i = {i}", theme, 15, INK[theme], weight=600))
            g.append(text(0, 104, f"{word} {verdict}", theme, 15, INK[theme] if not member else None))
            g.append(f'<rect x="0" y="122" width="{size}" height="5" fill="{s[7]}"/>')
            g.append(text(size + 8, 128, "v, pumped", theme, 13))
            g.append(f'<rect x="110" y="122" width="{size}" height="5" fill="{s[1]}"/>')
            g.append(text(110 + size + 8, 128, "y, pumped", theme, 13))
            body.append(f'<g class="fr" style="animation-delay:{k * hold - cycle:.1f}s">{"".join(g)}</g>')
        on = hold / cycle * 100
        style = (f".fr{{opacity:0;animation:fr {cycle:.1f}s infinite}}"
                 f"@keyframes fr{{0%{{opacity:1}}{on - 3:.1f}%{{opacity:1}}{on:.1f}%{{opacity:0}}{100 - 3:.1f}%{{opacity:0}}100%{{opacity:1}}}}"
                 f"{REDUCED}{{.fr{{animation:none}}.fr:nth-of-type(2){{opacity:1}}}}")
        write("pumping", theme, svg(440, 140, "Pumping v and y in aaabbbccc: only i = 1 stays in the language", "".join(body), style))


# --- IS-95: the order-64 Walsh family ---------------------------------------

def walsh():
    # gapless: at README scale a 0.5px gutter turns into moire
    n, pitch, size = 64, 4.5, 4.5
    h = [[1]]
    while len(h) < n:
        h = [r + r for r in h] + [r + [-v for v in r] for r in h]
    notes = [(0, "W0, pilot"), (1, "W1 to W7, paging"), (32, "W32, sync")]
    for theme, s in SCALE.items():
        pos = [(x, y) for y in range(n) for x in range(n) if h[y][x] > 0]
        neg = [(x, y) for y in range(n) for x in range(n) if h[y][x] < 0]
        body = [f'<g transform="translate(0 8)"><path fill="{s[7]}" d="{cells_path(pos, pitch, size)}"/>',
                f'<path fill="{s[1]}" d="{cells_path(neg, pitch, size)}"/>']
        right = n * pitch
        for row, label in notes:
            y = row * pitch + size / 2
            if row == 1:
                body.append(f'<path d="M{right + 4} {y - 1.5} h6 v{6 * pitch + 3} h-6" fill="none" stroke="{INK[theme]}" stroke-width="1.2"/>')
                y = row * pitch + 3 * pitch + 2
            body.append(f'<path d="M{right + 10} {y} H {right + 30}" stroke="{INK[theme]}" stroke-width="1.2"/>')
            body.append(text(right + 36, y + 5, label, theme, 13, INK[theme] if row != 1 else None))
        body.append(text(right + 36, right - 4, "+1 and \u22121 chips", theme, 13))
        body.append(f'<rect x="{right + 36}" y="{right - 28}" width="10" height="10" fill="{s[7]}"/>')
        body.append(f'<rect x="{right + 50}" y="{right - 28}" width="10" height="10" fill="{s[1]}"/></g>')
        write("walsh", theme, svg(440, int(right) + 16, "The 64 Walsh codes as a grid of +1 and -1 chips, with the pilot, paging and sync rows marked", "".join(body)))


# --- closing strip: the hero's grid running down to nothing -----------------

def coda():
    cols, rows, pitch, size = 125, 3, 8, 6.5
    rnd = random.Random(28)
    for theme, s in SCALE.items():
        by = {}
        for x in range(cols):
            energy = max(0.0, 1 - x / 80) ** 1.6
            for y in range(rows):
                i = bucket(rnd.gauss(0, 0.55) * energy)
                if s[i]:
                    by.setdefault(i, []).append((x, y))
        body = "".join(f'<path fill="{s[i]}" d="{cells_path(c, pitch, size)}"/>' for i, c in sorted(by.items()))
        write("coda", theme, svg(cols * pitch, rows * pitch - 2, "", body))


if __name__ == "__main__":
    hero(sys.argv[1] if len(sys.argv) > 1 else "C:/Windows/Fonts/bahnschrift.ttf")
    morphism()
    tail()
    pumping()
    walsh()
    coda()
