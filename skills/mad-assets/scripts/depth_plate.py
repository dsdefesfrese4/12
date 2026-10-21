"""Turn a manga panel into a 3D-ready plate: erase text boxes / bubbles (and optionally people), estimate depth.

  python3 depth_plate.py <project> <panel_id> [--erase x0,y0,x1,y1 ...] [--no-bubbles] [--erase-people] [--out plates3d]

Writes <out>/<id>.png (clean RGB) and <out>/<id>_depth.npy (relative inverse depth, 0 = far, 1 = near, same size).
Depth model: Depth-Anything-V2-Small (HF). Erasing uses LaMa (mad-assets/layer_panel.py).
Rects are normalised [x0, y0, x1, y1].
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layer_panel import bubble_mask, inpaint  # noqa: E402

_PIPE = None


def depth(img_bgr):
    global _PIPE
    from PIL import Image
    if _PIPE is None:
        from transformers import pipeline
        _PIPE = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device="cpu")
    d = _PIPE(Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)))["predicted_depth"]
    d = np.array(d.squeeze().cpu() if hasattr(d, "cpu") else d, dtype=np.float32)
    d = cv2.resize(d, (img_bgr.shape[1], img_bgr.shape[0]), interpolation=cv2.INTER_CUBIC)
    lo, hi = np.percentile(d, 1), np.percentile(d, 99.5)
    return np.clip((d - lo) / (hi - lo + 1e-6), 0, 1).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("pid")
    ap.add_argument("--erase", nargs="*", default=[])
    ap.add_argument("--no-bubbles", action="store_true")
    ap.add_argument("--erase-people", action="store_true")
    ap.add_argument("--out", default="plates3d")
    a = ap.parse_args()
    root = a.project
    p = os.path.join(root, "panels", a.pid + ".png")
    if not os.path.exists(p):
        p = os.path.join(root, "pages", a.pid + ".jpg")
    im = cv2.imread(p)
    H, W = im.shape[:2]
    m = np.zeros((H, W), np.uint8)
    if not a.no_bubbles:
        m |= bubble_mask(im)
    for r in a.erase:
        x0, y0, x1, y1 = (float(v) for v in r.split(","))
        m[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)] = 255
    if a.erase_people:
        mk = os.path.join(root, "cutouts_auto", a.pid + "_mask.png")
        if os.path.exists(mk):
            pm = cv2.resize(cv2.imread(mk, 0), (W, H))
            m |= cv2.dilate((pm > 100).astype(np.uint8) * 255, np.ones((15, 15), np.uint8))
    m = cv2.dilate(m, np.ones((7, 7), np.uint8))
    clean = inpaint(im, m) if m.any() else im
    od = os.path.join(root, a.out)
    os.makedirs(od, exist_ok=True)
    cv2.imwrite(os.path.join(od, a.pid + ".png"), clean)
    d = depth(clean)
    np.save(os.path.join(od, a.pid + "_depth.npy"), d)
    v = cv2.applyColorMap((d * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
    cv2.imwrite(os.path.join(od, a.pid + "_check.jpg"), np.hstack([clean, v]))
    print(a.pid, W, H, "erased %.1f%%" % (100 * (m > 0).mean()))


if __name__ == "__main__":
    sys.exit(main())
