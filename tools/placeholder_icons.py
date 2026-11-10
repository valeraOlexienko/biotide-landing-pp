#!/usr/bin/env python3
"""Write placeholder PNGs so a fresh site renders without broken images.

    python3 tools/placeholder_icons.py [--color 2563eb] [--letter S]

Creates (and overwrites) in images/:
  logo.png               512x512   solid tile with the first letter cut out
  apple-touch-icon.png   180x180   same
  favicon.png            64x64     same
  placeholder-screen.png 603x1311  a phone-shaped grey rectangle (hero / trio stand-in)

Standard library only (zlib + struct), no PIL. Replace every one of these with
the real assets before launch; the TODO lists them. The social image is a
separate step (tools/og-image.html + tools/render_og.sh).
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "public" if (REPO / "public").is_dir() else REPO
IMAGES = ROOT / "images"

# 5x7 bitmap capitals, enough for an initial.
GLYPHS = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "01010", "00100", "00100", "00100", "01010", "10001"],
    "Y": ["10001", "01010", "00100", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
}


def png(width: int, height: int, pixel) -> bytes:
    """Encode an RGBA image from a pixel(x, y) -> (r, g, b, a) function."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(pixel(x, y))

    def chunk(kind: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + kind + data
        return c + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def rounded(x: int, y: int, w: int, h: int, r: int) -> bool:
    """Inside a rounded rectangle of size w x h with corner radius r."""
    cx = min(max(x, r), w - 1 - r)
    cy = min(max(y, r), h - 1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def icon(size: int, rgb: tuple[int, int, int], letter: str) -> bytes:
    glyph = GLYPHS.get(letter.upper(), GLYPHS["A"])
    cell = size // 11  # 5 columns + margins
    gx = (size - 5 * cell) // 2
    gy = (size - 7 * cell) // 2
    radius = size * 22 // 100

    def pixel(x: int, y: int):
        if not rounded(x, y, size, size, radius):
            return (0, 0, 0, 0)
        col, row = (x - gx) // cell, (y - gy) // cell
        if 0 <= col < 5 and 0 <= row < 7 and glyph[row][col] == "1":
            return (255, 255, 255, 255)
        return (*rgb, 255)

    return png(size, size, pixel)


def screen(w: int, h: int) -> bytes:
    radius = w * 14 // 100

    def pixel(x: int, y: int):
        if not rounded(x, y, w, h, radius):
            return (0, 0, 0, 0)
        # a faint status bar and a few "cards" so it reads as a screen, not a block
        if y < h * 5 // 100:
            return (28, 32, 40, 255)
        band = (y * 7 // h) % 2 == 0 and w * 6 // 100 < x < w * 94 // 100 and (y % (h // 7)) > h // 60
        return (52, 58, 70, 255) if band else (36, 40, 50, 255)

    return png(w, h, pixel)


def main(argv: list[str]) -> int:
    color = "2563eb"
    letter = "A"
    args = iter(argv)
    for a in args:
        if a == "--color":
            color = next(args, color).lstrip("#")
        elif a == "--letter":
            letter = next(args, letter)[:1] or letter
    rgb = tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
    IMAGES.mkdir(parents=True, exist_ok=True)
    (IMAGES / "logo.png").write_bytes(icon(512, rgb, letter))
    (IMAGES / "apple-touch-icon.png").write_bytes(icon(180, rgb, letter))
    (IMAGES / "favicon.png").write_bytes(icon(64, rgb, letter))
    (IMAGES / "placeholder-screen.png").write_bytes(screen(603, 1311))
    print("  placeholder images written to", IMAGES.relative_to(REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
