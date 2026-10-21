"""Step 1 of the character pipeline: complete the full figure.

Bubbles are cut out (holes, not filled), the canvas is extended, and holes + extension are
redrawn together in the source's own manga style with SD + ControlNet inpaint.

  python3 complete_figure.py page.jpg out_dir --bubbles mask_bubbles.png \
      --pad 150,250,350,250   (top,right,bottom,left px) --prompt "..." [--size 896 --seed 1]

Writes: cutout.png (RGBA, bubbles = transparent), canvas_mask.png, full.png, place.json
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sd_tools  # noqa: E402

STYLE = "monochrome, greyscale, manga, lineart, screentone, hatching, "
NEG = "color, colorful, text, speech bubble, frame, border, panel, extra arms, extra head, multiple girls"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("page")
    ap.add_argument("out")
    ap.add_argument("--bubbles", help="white = speech bubble / caption to cut out")
    ap.add_argument("--pad", default="150,250,350,250")
    ap.add_argument("--overlap", type=int, default=12, help="px of the original edge to let the model blend")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--size", type=int, default=896)
    ap.add_argument("--steps", type=int, default=26)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--hole-grow", type=int, default=30, help="grow bubble holes so no bubble outline survives")
    ap.add_argument("--redraw-paper", action="store_true", help="also redraw paper-white panel background")
    ap.add_argument("--neg", default="")
    ap.add_argument("--keep-mask", help="white = the character in the source; everything else becomes locked white paper")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    src = cv2.imread(a.page, cv2.IMREAD_COLOR)
    h, w = src.shape[:2]
    hole = np.zeros((h, w), np.uint8)
    if a.bubbles:
        b = cv2.imread(a.bubbles, cv2.IMREAD_GRAYSCALE)
        hole = (cv2.resize(b, (w, h), interpolation=cv2.INTER_NEAREST) > 127).astype(np.uint8) * 255
        if a.hole_grow:
            k = a.hole_grow * 2 + 1
            hole = cv2.dilate(hole, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    if a.redraw_paper:
        g = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
        white = (g >= 235).astype(np.uint8)
        n, lab = cv2.connectedComponents(white, connectivity=4)
        border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
        paper = np.isin(lab, list(border)).astype(np.uint8)
        paper = cv2.morphologyEx(paper, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
        hole = np.maximum(hole, cv2.dilate(paper, np.ones((9, 9), np.uint8)) * 255)
    cut = np.dstack([src, 255 - hole])
    cv2.imwrite(os.path.join(a.out, "cutout.png"), cut)
    t, r, btm, l = (int(v) for v in a.pad.split(","))
    CW, CH = w + l + r, h + t + btm
    canvas = np.full((CH, CW, 3), 255, np.uint8)
    canvas[t:t + h, l:l + w] = src
    canvas[t:t + h, l:l + w][hole > 0] = 255
    locked = np.zeros((h, w), np.uint8)
    if a.keep_mask:
        km = cv2.imread(a.keep_mask, cv2.IMREAD_GRAYSCALE)
        km = cv2.resize(km, (w, h), interpolation=cv2.INTER_NEAREST) > 127
        locked = (~km & (hole == 0)).astype(np.uint8)
        canvas[t:t + h, l:l + w][locked > 0] = 255
    mask = np.full((CH, CW), 255, np.uint8)
    o = a.overlap
    keep = np.zeros((h, w), np.uint8)
    keep[o if t else 0:h - (o if btm else 0), o if l else 0:w - (o if r else 0)] = 255
    keep[hole > 0] = 0
    mask[t:t + h, l:l + w] = 255 - keep
    cv2.imwrite(os.path.join(a.out, "canvas_mask.png"), mask)
    full = sd_tools.inpaint(canvas, mask, STYLE + a.prompt, steps=a.steps, size=a.size, seed=a.seed,
                            neg=NEG + ", " + a.neg)
    cv2.imwrite(os.path.join(a.out, f"full_s{a.seed}.png"), full)
    with open(os.path.join(a.out, "place.json"), "w") as f:
        json.dump({"src": a.page, "offset": [l, t], "src_size": [w, h], "canvas": [CW, CH]}, f)
    print(os.path.join(a.out, f"full_s{a.seed}.png"), CW, CH)


if __name__ == "__main__":
    sys.exit(main())
