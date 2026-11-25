#!/usr/bin/env python3
"""Build-time font extraction for the news-image entry.

Renders printable ASCII glyphs from a system TrueType font with Pillow and
saves them as antialiased 8-bit masks in font.json (zlib + base64).

This script runs ONCE, here, while building the entry. It is NOT run by the
grader: main.py is standard-library only and reads the font.json this script
produces. Run:  python3 tools/make_font.py
"""

import base64
import json
import os
import sys
import zlib

from PIL import Image, ImageDraw, ImageFont

MASTER_PX = 80  # glyph cell height reference; main.py downscales from this
CHARS = [chr(c) for c in range(32, 127)]

FONT_CANDIDATES = {
    "regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ],
    "bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ],
}


def pick(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    raise SystemExit("no usable font found in: %s" % (paths,))


def extract(font_path):
    font = ImageFont.truetype(font_path, MASTER_PX)
    ascent, descent = font.getmetrics()
    cell_h = ascent + descent
    glyphs = {}
    for ch in CHARS:
        if ch == " ":
            glyphs[ch] = {"w": 0, "x": 0, "adv": int(round(font.getlength(ch))), "data": ""}
            continue
        w = int(font.getlength(ch)) + 8
        img = Image.new("L", (w, cell_h), 0)
        draw = ImageDraw.Draw(img)
        draw.text((4, 0), ch, font=font, fill=255, anchor="la")
        bbox = img.getbbox()
        adv = int(round(font.getlength(ch)))
        if bbox is None:
            glyphs[ch] = {"w": 0, "x": 0, "adv": adv, "data": ""}
            continue
        x0, _y0, x1, _y1 = bbox
        crop = img.crop((x0, 0, x1, cell_h))
        raw = crop.tobytes()
        enc = base64.b64encode(zlib.compress(raw, 9)).decode("ascii")
        glyphs[ch] = {"w": x1 - x0, "x": x0 - 4, "adv": adv, "data": enc}
    return {"ascent": ascent, "cell_height": cell_h, "glyphs": glyphs}


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = {"cell_height": None, "ascent": None, "regular": None, "bold": None}
    for weight, candidates in FONT_CANDIDATES.items():
        path = pick(candidates)
        print("using %s font: %s" % (weight, path))
        data = extract(path)
        out["cell_height"] = data["cell_height"]
        out["ascent"] = data["ascent"]
        out[weight] = data["glyphs"]
    dest = os.path.join(root, "font.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print("wrote %s (%d bytes)" % (dest, os.path.getsize(dest)))


if __name__ == "__main__":
    sys.exit(main())
