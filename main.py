#!/usr/bin/env python3
"""Sum up 25 November 2026's world news in one image.

Reads six verified stories from news.json and renders a one-page
newspaper-style poster to output/entry.png (and to /output/entry.png when
that directory is writable).

Standard library only: no third-party packages, no network, no secrets.
The glyphs in font.json are antialiased masks extracted at build time from
a system TrueType font by tools/make_font.py; this program only scales and
stamps them, and writes the PNG with zlib + struct. The run is fully
deterministic: the same input bytes always produce the same output bytes.

Run:  python3 main.py
"""

import base64
import json
import os
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.abspath(__file__))

W, H = 1280, 1920
MARGIN = 76
CW = W - 2 * MARGIN  # content width

PAPER = (250, 247, 242)
INK = (26, 26, 26)
MUTED = (96, 93, 88)
HAIRLINE = (216, 213, 206)
ACCENT = (178, 34, 34)
WHITE = (255, 255, 255)

MASTER_SIZE = 80  # font.json glyphs were rendered at this size


# ---------------------------------------------------------------- font ----

def _scale_1d(values, n_out):
    """Area-average resample of a 1-D row of floats to n_out samples."""
    n_in = len(values)
    out = []
    for i in range(n_out):
        x0 = i * n_in / n_out
        x1 = (i + 1) * n_in / n_out
        total = 0.0
        j0 = int(x0)
        j1 = int(x1)
        for j in range(j0, min(n_in, j1 + 1)):
            w = min(x1, j + 1) - max(x0, j)
            if w > 0:
                total += values[j] * w
        out.append(total / (x1 - x0))
    return out


def scale_mask(src, w, h, tw, th):
    """Area-average downscale of an 8-bit mask (bytes, w x h) to tw x th."""
    rows = []
    for y in range(h):
        row = [src[y * w + x] for x in range(w)]
        rows.append(_scale_1d(row, tw))
    out = bytearray(tw * th)
    for x in range(tw):
        col = [rows[y][x] for y in range(h)]
        scol = _scale_1d(col, th)
        for y in range(th):
            out[y * tw + x] = int(scol[y] + 0.5)
    return bytes(out)


class Font:
    def __init__(self, data):
        self.cell_h = data["cell_height"]
        self.ascent = data["ascent"]
        self.sets = {"regular": data["regular"], "bold": data["bold"]}
        self._raw = {}
        self._scaled = {}

    def _raw_mask(self, ch, weight):
        key = (ch, weight)
        if key not in self._raw:
            g = self.sets[weight].get(ch) or self.sets[weight]["?"]
            raw = zlib.decompress(base64.b64decode(g["data"])) if g["data"] else b""
            self._raw[key] = (g, raw)
        return self._raw[key]

    def scaled(self, ch, weight, size):
        """Return (width, height, mask, x_offset, advance) at the given size."""
        key = (ch, weight, size)
        hit = self._scaled.get(key)
        if hit is not None:
            return hit
        g, raw = self._raw_mask(ch, weight)
        s = size / MASTER_SIZE
        tw = max(1, round(g["w"] * s))
        th = max(1, round(self.cell_h * s))
        if g["w"] == 0 or not raw:
            mask = b""
        else:
            mask = scale_mask(raw, g["w"], self.cell_h, tw, th)
        out = (tw, th, mask, round(g["x"] * s), g["adv"] * s)
        self._scaled[key] = out
        return out

    def ascent_px(self, size):
        return round(self.ascent * size / MASTER_SIZE)

    def measure(self, text, weight, size):
        total = 0.0
        for ch in text:
            total += self.scaled(ch, weight, size)[4]
        return total

    def draw(self, cv, x, baseline_y, text, weight, size, fg, bg):
        """Draw text left-aligned; returns the pen x after the last glyph."""
        asc = self.ascent_px(size)
        for ch in text:
            tw, th, mask, xoff, adv = self.scaled(ch, weight, size)
            if mask:
                stamp(cv, mask, tw, th, round(x + xoff), baseline_y - asc, fg, bg)
            x += adv
        return x


# -------------------------------------------------------------- canvas ----

_lut_cache = {}


def _lut(fg, bg):
    key = (fg, bg)
    lut = _lut_cache.get(key)
    if lut is None:
        lut = tuple(
            tuple((fg[c] * a + bg[c] * (255 - a)) // 255 for a in range(256))
            for c in range(3)
        )
        _lut_cache[key] = lut
    return lut


def stamp(cv, mask, mw, mh, x, y, fg, bg):
    l0, l1, l2 = _lut(fg, bg)
    f0, f1, f2 = fg
    c0 = max(0, -x)
    c1 = min(mw, W - x)
    for r in range(mh):
        cy = y + r
        if cy < 0 or cy >= H:
            continue
        row = r * mw
        base = (cy * W + x) * 3
        for c in range(c0, c1):
            a = mask[row + c]
            if not a:
                continue
            o = base + c * 3
            if a == 255:
                cv[o] = f0
                cv[o + 1] = f1
                cv[o + 2] = f2
            else:
                cv[o] = l0[a]
                cv[o + 1] = l1[a]
                cv[o + 2] = l2[a]


def fill_rect(cv, x, y, w, h, color):
    row = bytes(color) * w
    for yy in range(y, y + h):
        base = (yy * W + x) * 3
        cv[base:base + w * 3] = row


def wrap(text, weight, size, max_w, font):
    words = text.split(" ")
    lines = []
    cur = ""
    for wd in words:
        trial = wd if not cur else cur + " " + wd
        if font.measure(trial, weight, size) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def write_png(path, w, h, rgb):
    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# -------------------------------------------------------------- layout ----

PRESETS = [
    # headline, headline_lh, summary, summary_lh, sources, chip
    (40, 50, 29, 39, 23, 40),
    (38, 47, 28, 37, 22, 38),
    (36, 45, 26, 35, 21, 36),
]


def layout_stories(font, stories, preset):
    hl, hl_lh, sm, sm_lh, src, chip_h = preset
    blocks = []
    total = 0
    for st in stories:
        head_lines = wrap(st["headline"], "bold", hl, CW, font)
        sum_lines = wrap(st["summary"], "regular", sm, CW, font)
        h = chip_h + 12 + len(head_lines) * hl_lh + 8
        h += len(sum_lines) * sm_lh + 8 + src + 4
        blocks.append((head_lines, sum_lines, h))
        total += h
    total += 34 * (len(stories) - 1)  # divider + gaps between stories
    return blocks, total


def render(font, news):
    cv = bytearray(bytes(PAPER) * (W * H))
    stories = news["stories"]

    # Header.
    fill_rect(cv, MARGIN, 56, CW, 6, ACCENT)
    y = 88
    title = "WORLD NEWS"
    tw = font.measure(title, "bold", 84)
    font.draw(cv, (W - tw) / 2, y + font.ascent_px(84), title, "bold", 84, INK, PAPER)
    y += font.ascent_px(84) + 26
    date_line = "Wednesday, 25 November 2026"
    tw = font.measure(date_line, "regular", 30)
    font.draw(cv, (W - tw) / 2, y + font.ascent_px(30), date_line, "regular", 30, INK, PAPER)
    y += font.ascent_px(30) + 14
    kicker = "Six stories that defined the day"
    tw = font.measure(kicker, "regular", 28)
    font.draw(cv, (W - tw) / 2, y + font.ascent_px(28), kicker, "regular", 28, MUTED, PAPER)
    y += font.ascent_px(28) + 26
    fill_rect(cv, MARGIN, y, CW, 2, HAIRLINE)
    y += 2 + 34

    # Stories: pick the first preset that fits above the footer.
    footer_reserve = 120
    for preset in PRESETS:
        blocks, total = layout_stories(font, stories, preset)
        if y + total <= H - footer_reserve:
            break
    hl, hl_lh, sm, sm_lh, src, chip_h = preset

    for i, st in enumerate(stories):
        if i:
            fill_rect(cv, MARGIN, y, CW, 1, HAIRLINE)
            y += 1 + 33
        head_lines, sum_lines, _h = blocks[i]
        # Tag chip.
        tag = st["tag"]
        tag_w = font.measure(tag, "bold", 24)
        chip_w = int(tag_w + 32)
        color = tuple(st["color"])
        fill_rect(cv, MARGIN, y, chip_w, chip_h, color)
        font.draw(
            cv, MARGIN + 16, y + (chip_h + font.ascent_px(24)) // 2 - 4,
            tag, "bold", 24, WHITE, color,
        )
        y += chip_h + 12
        # Headline.
        for line in head_lines:
            font.draw(cv, MARGIN, y + font.ascent_px(hl), line, "bold", hl, INK, PAPER)
            y += hl_lh
        y += 8
        # Summary.
        for line in sum_lines:
            font.draw(cv, MARGIN, y + font.ascent_px(sm), line, "regular", sm, INK, PAPER)
            y += sm_lh
        y += 8
        # Sources.
        src_line = "Sources: " + st["sources"]
        font.draw(cv, MARGIN, y + font.ascent_px(src), src_line, "regular", src, MUTED, PAPER)
        y += src + 4

    # Footer.
    fy = H - 108
    fill_rect(cv, MARGIN, fy, CW, 2, HAIRLINE)
    foot1 = "All stories verified against reporting from SCMP, Economic Times,"
    foot2 = "Qatar Tribune, The Manila Times and SBS  |  25 November 2026"
    for j, line in enumerate((foot1, foot2)):
        tw = font.measure(line, "regular", 22)
        font.draw(
            cv, (W - tw) / 2, fy + 18 + j * 30 + font.ascent_px(22),
            line, "regular", 22, MUTED, PAPER,
        )
    return cv


def main():
    with open(os.path.join(ROOT, "news.json"), encoding="utf-8") as f:
        news = json.load(f)
    with open(os.path.join(ROOT, "font.json"), encoding="utf-8") as f:
        font = Font(json.load(f))

    cv = render(font, news)

    out_dir = os.path.join(ROOT, "output")
    os.makedirs(out_dir, exist_ok=True)
    local_path = os.path.join(out_dir, "entry.png")
    nbytes = write_png(local_path, W, H, bytes(cv))

    abs_path = "/output/entry.png"
    try:
        os.makedirs("/output", exist_ok=True)
        write_png(abs_path, W, H, bytes(cv))
    except OSError:
        abs_path = None

    print(json.dumps({
        "width": W, "height": H, "bytes": nbytes,
        "stories": len(news["stories"]), "local": local_path,
        "absolute": abs_path,
    }))


if __name__ == "__main__":
    sys.exit(main())
