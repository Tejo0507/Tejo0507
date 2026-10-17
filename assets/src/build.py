"""Generates assets/hero-light.svg and assets/hero-dark.svg.

The line is set in Gill Sans and converted to outlines, so the image needs no
font on the viewer's machine. Under it, a tangled scribble straightens into a
single rule once, on load (SMIL, so it runs inside GitHub's <img>).

    python assets/src/build.py [path/to/GillSans.ttf]

Needs fontTools.
"""

import math
import random
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

OUT = Path(__file__).resolve().parent.parent
LINES = ["I work on things", "that interest me,", "and keep things simple."]
INK = {"light": "#1f2328", "dark": "#e6edf3"}

SIZE = 92          # font size in viewBox units
LEADING = 1.08
WIDTH = 1000


def set_lines(font_path):
    font = TTFont(font_path)
    cmap, glyphs, hmtx = font.getBestCmap(), font.getGlyphSet(), font["hmtx"]
    kern = font["kern"].kernTables[0].kernTable if "kern" in font else {}
    scale = SIZE / font["head"].unitsPerEm
    ascent = font["hhea"].ascent * scale

    pen = SVGPathPen(glyphs)
    widths = []
    for row, line in enumerate(LINES):
        baseline = ascent * 0.78 + row * SIZE * LEADING
        x, prev = 0.0, None
        for ch in line:
            name = cmap[ord(ch)]
            if prev:
                x += kern.get((prev, name), 0)
            glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x * scale, baseline)))
            x += hmtx[name][0]
            prev = name
        widths.append(x * scale)
    return pen.getCommands(), max(widths), baseline


def catmull_rom(points):
    """Smooth path through points; same command count for any input of the same length."""
    d = [f"M{points[0][0]:.1f} {points[0][1]:.1f}"]
    for i in range(len(points) - 1):
        p0 = points[max(0, i - 1)]
        p1, p2 = points[i], points[i + 1]
        p3 = points[min(len(points) - 1, i + 2)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}")
    return "".join(d)


def scribble(length, y, n=180):
    rnd = random.Random(507)
    knot, rule = [], []
    phase = 0.0
    for i in range(n):
        t = i / (n - 1)
        # loops that drift forward unevenly, like a pen knotting a cord
        phase += 0.42 + 0.25 * rnd.random()
        r = 16 + 22 * math.sin(math.pi * t) + 6 * rnd.random()
        x = length * (0.08 + 0.62 * t) + r * math.cos(phase) + 30 * math.sin(3.1 * t * math.pi)
        yy = y + r * 0.62 * math.sin(phase) + 7 * math.sin(7 * t)
        knot.append((x, yy))
        rule.append((length * t, y))
    return catmull_rom(knot), catmull_rom(rule)


def build(font_path):
    text, longest, last_baseline = set_lines(font_path)
    rule_y = last_baseline + 72
    knot, rule = scribble(longest, rule_y)
    height = math.ceil(rule_y + 40)
    for theme, ink in INK.items():
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" '
            f'role="img" aria-label="I work on things that interest me, and keep things simple.">'
            "<style>.still{display:none}"
            "@media (prefers-reduced-motion: reduce){.moving{display:none}.still{display:inline}}</style>"
            f'<path fill="{ink}" d="{text}"/>'
            f'<g fill="none" stroke="{ink}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">'
            f'<path class="moving" d="{knot}">'
            f'<animate attributeName="d" values="{knot};{rule}" dur="2.6s" begin="0.9s" fill="freeze" '
            'calcMode="spline" keyTimes="0;1" keySplines="0.7 0 0.25 1"/></path>'
            f'<path class="still" d="{rule}"/></g></svg>\n'
        )
        (OUT / f"hero-{theme}.svg").write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "C:/Windows/Fonts/GIL_____.TTF")
