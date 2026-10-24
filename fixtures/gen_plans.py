"""Deterministic fixture floor plans — generated, never hand-edited.

Three hand-authored layouts drawn at 2x the parse grid (192x144, 4px
walls, 4px door gaps), written as flat-color PNGs by walkthru.pngio.
Run:  python3 fixtures/gen_plans.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from walkthru import pngio

W, H = 192, 144
WALLC, FLOORC = (0, 0, 0), (255, 255, 255)


def canvas():
    return [[FLOORC] * W for _ in range(H)]


def rect(rows, x0, y0, x1, y1, color):
    """Inclusive fill."""
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            rows[y][x] = color


def border(rows, t=4):
    rect(rows, 0, 0, W - 1, t - 1, WALLC)
    rect(rows, 0, H - t, W - 1, H - 1, WALLC)
    rect(rows, 0, 0, t - 1, H - 1, WALLC)
    rect(rows, W - t, 0, W - 1, H - 1, WALLC)


def flat1():
    """Three rooms in a row, doors between them."""
    r = canvas()
    border(r)
    for x in (72, 116):  # two 4px dividers
        rect(r, x, 4, x + 3, H - 5, WALLC)
    rect(r, 72, 68, 123, 71, FLOORC)  # one strip carves both door gaps
    return r


def venue():
    """Big hall + 4 service rooms along the right side."""
    r = canvas()
    border(r)
    rect(r, 120, 4, 123, H - 5, WALLC)  # hall / service divider
    for i, ygap in enumerate((10, 46, 82, 118)):
        rect(r, 120, ygap, 123, ygap + 3, FLOORC)  # door into room i
    for y in (34, 70, 106):  # walls between service rooms
        rect(r, 124, y, W - 5, y + 3, WALLC)
    return r


def offices():
    """Four quadrant offices around a cross corridor."""
    r = canvas()
    border(r)
    # corridor walls (horizontal bands) with door gaps
    for y in (60, 80):
        rect(r, 4, y, W - 5, y + 3, WALLC)
    for x in (30, 150):
        rect(r, x, 60, x + 3, 63, FLOORC)
        rect(r, x, 80, x + 3, 83, FLOORC)
    # vertical corridor walls (no gaps: entry via horizontal corridor)
    for x in (84, 104):
        rect(r, x, 4, x + 3, 59, WALLC)
        rect(r, x, 84, x + 3, H - 5, WALLC)
    # carve the corridor crossings so H and V corridors form one space
    for y in (60, 80):
        rect(r, 88, y, 103, y + 3, FLOORC)
    return r


LAYOUTS = {"flat1.png": flat1, "venue.png": venue, "offices.png": offices}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    for name, fn in LAYOUTS.items():
        path = os.path.join(here, name)
        pngio.write_png(path, W, H, fn())
        print("wrote", path)


if __name__ == "__main__":
    main()
