"""Split manga/comic pages into individual panels.

  python3 split_panels.py page1.jpg page2.jpg -o assets/panels [--ltr] [--min-area 0.03]

Works on pages whose panels are separated by light (white) gutters, which covers
almost all manga. Reading order defaults to Japanese (right-to-left, top-to-bottom).
Writes <page>_p01.png ... plus panels.json with bounding boxes, and a debug overlay.
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np


def find_panels(img, min_area=0.03, gutter_thresh=235, pad=0):
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    # content = anything that is not near-white
    content = (gray < gutter_thresh).astype(np.uint8) * 255
    # close small gaps inside panels (speech bubbles touching edges, thin lines)
    k = max(3, int(min(H, W) * 0.006)) | 1
    content = cv2.morphologyEx(content, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    # recursive XY-cut on white gutters works better than contours for manga
    boxes = []
    _xycut(content, 0, 0, W, H, boxes, depth=0, min_gap=max(4, int(min(H, W) * 0.008)))
    out = []
    for (x, y, w, h) in boxes:
        if w * h < min_area * W * H:
            continue
        sub = content[y:y + h, x:x + w]
        ys, xs = np.nonzero(sub)
        if len(xs) == 0:
            continue
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        bx, by = max(0, x + x0 - pad), max(0, y + y0 - pad)
        bw, bh = min(W, x + x1 + 1 + pad) - bx, min(H, y + y1 + 1 + pad) - by
        if bw * bh >= min_area * W * H:
            out.append((int(bx), int(by), int(bw), int(bh)))
    return out


def _xycut(m, x, y, w, h, boxes, depth, min_gap):
    sub = m[y:y + h, x:x + w]
    if depth > 12 or w < 20 or h < 20:
        boxes.append((x, y, w, h))
        return
    # try horizontal gutters first (rows that are almost empty), then vertical
    for axis in (1, 0):
        prof = (sub > 0).mean(axis=axis)
        empty = prof < 0.01
        cuts = _runs(empty, min_gap)
        L = len(prof)
        inner = [(a, b) for a, b in cuts if a > 0 and b < L]
        if inner:
            edges = [0] + [v for a, b in inner for v in ((a + b) // 2,)] + [L]
            for s, e in zip(edges, edges[1:]):
                if e - s < 10:
                    continue
                if axis == 1:
                    _xycut(m, x, y + s, w, e - s, boxes, depth + 1, min_gap)
                else:
                    _xycut(m, x + s, y, e - s, h, boxes, depth + 1, min_gap)
            return
    boxes.append((x, y, w, h))


def _runs(mask, min_len):
    runs, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start >= min_len:
                runs.append((start, i))
            start = None
    if start is not None and len(mask) - start >= min_len:
        runs.append((start, len(mask)))
    return runs


def reading_order(boxes, rtl=True):
    # group into rows by vertical overlap, then sort within a row
    boxes = sorted(boxes, key=lambda b: b[1])
    rows = []
    for b in boxes:
        placed = False
        for r in rows:
            ry0 = min(x[1] for x in r)
            ry1 = max(x[1] + x[3] for x in r)
            ov = min(ry1, b[1] + b[3]) - max(ry0, b[1])
            if ov > 0.5 * min(b[3], ry1 - ry0):
                r.append(b)
                placed = True
                break
        if not placed:
            rows.append([b])
    out = []
    for r in rows:
        out += sorted(r, key=lambda b: -b[0] if rtl else b[0])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="+")
    ap.add_argument("-o", "--out", default="assets/panels")
    ap.add_argument("--ltr", action="store_true", help="left-to-right reading order (western/Chinese comics)")
    ap.add_argument("--min-area", type=float, default=0.03)
    ap.add_argument("--thresh", type=int, default=235, help="gutter brightness threshold")
    ap.add_argument("--pad", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    meta = {}
    for page in a.pages:
        img = cv2.imread(page, cv2.IMREAD_COLOR)
        if img is None:
            print(f"skip unreadable {page}", file=sys.stderr)
            continue
        boxes = reading_order(find_panels(img, a.min_area, a.thresh, a.pad), rtl=not a.ltr)
        name = os.path.splitext(os.path.basename(page))[0]
        dbg = img.copy()
        meta[name] = []
        for i, (x, y, w, h) in enumerate(boxes, 1):
            p = os.path.join(a.out, f"{name}_p{i:02d}.png")
            cv2.imwrite(p, img[y:y + h, x:x + w])
            meta[name].append({"file": p, "box": [x, y, w, h]})
            cv2.rectangle(dbg, (x, y), (x + w, y + h), (0, 0, 255), 4)
            cv2.putText(dbg, str(i), (x + 12, y + 50), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 0, 255), 4)
            print(f"{p}  {w}x{h}")
        cv2.imwrite(os.path.join(a.out, f"{name}_debug.jpg"), dbg)
    with open(os.path.join(a.out, "panels.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.exit(main())
