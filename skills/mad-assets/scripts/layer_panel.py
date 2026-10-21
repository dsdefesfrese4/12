"""Clean and layer a manga panel for parallax / puppet animation.

  python3 layer_panel.py panel.png -o assets/layers [--no-bubbles] [--keep-bubbles] [--extra-mask m.png]

Steps
  1. bubbles : detect speech bubbles / narration boxes -> mask
  2. clean   : inpaint the bubbles away (LaMa anime-manga model if available, else OpenCV)
  3. fg      : cut out the character(s) with rembg isnet-anime -> RGBA
  4. bg      : inpaint the character hole so the background can move independently
  5. bubbles : also saved as a separate RGBA layer so they can be animated back in

Outputs in <out>/<name>/: clean.png, fg.png, bg.png, bubbles.png, mask_bubbles.png, mask_fg.png, preview.jpg
"""
import argparse
import os
import sys

import cv2
import numpy as np

LAMA_PATHS = [os.path.expanduser("~/.u2net/anime-manga-big-lama.pt"), os.path.expanduser("~/.u2net/big-lama.pt")]


# ------------------------------------------------------------ bubble detection

def bubble_mask(img, min_area=0.004, max_area=0.35, white=225, min_glyphs=5):
    """Speech bubbles = white blobs, fairly convex, with dark glyphs inside."""
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    wm = (gray >= white).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(wm, connectivity=4)
    mask = np.zeros((H, W), np.uint8)
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < min_area * W * H or area > max_area * W * H:
            continue
        comp = (lab == i).astype(np.uint8)
        cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        c = max(cnts, key=cv2.contourArea)
        filled = np.zeros_like(comp)
        cv2.drawContours(filled, [c], -1, 1, -1)
        filled_area = filled.sum()
        hull_area = cv2.contourArea(cv2.convexHull(c))
        solidity = filled_area / max(1, hull_area)
        holes = filled_area - area  # dark pixels enclosed = text
        text_ratio = holes / max(1, filled_area)
        touches = x <= 1 or y <= 1 or x + w >= W - 1 or y + h >= H - 1
        if solidity < 0.80 or text_ratio < 0.015 or text_ratio > 0.45:
            continue
        if touches and solidity < 0.9:
            continue
        # dark glyphs should be small strokes, not big blobs of art
        inner = (filled > 0) & (comp == 0)
        k, _, st2, _ = cv2.connectedComponentsWithStats(inner.astype(np.uint8), connectivity=8)
        if k > 1 and st2[1:, 4].max() > 0.25 * filled_area:
            continue
        # text = many small strokes; a white character's face (eyes + mouth) has only a few
        if k - 1 < min_glyphs:
            continue
        mask |= filled
    # grow to cover the bubble outline and tail
    k = max(3, int(min(H, W) * 0.012)) | 1
    mask = cv2.dilate(mask, np.ones((k, k), np.uint8))
    return mask * 255


# ------------------------------------------------------------ inpainting

_LAMA = None


def lama_model():
    global _LAMA
    if _LAMA is None:
        try:
            import torch
            for p in LAMA_PATHS:
                if os.path.exists(p):
                    _LAMA = torch.jit.load(p, map_location="cpu").eval()
                    break
        except Exception as e:  # torch missing or broken -> fall back
            print(f"[layer_panel] LaMa unavailable ({e.__class__.__name__}), using OpenCV inpaint", file=sys.stderr)
            _LAMA = False
        if _LAMA is None:
            _LAMA = False
    return _LAMA


def inpaint(img, mask):
    if mask.max() == 0:
        return img.copy()
    m = lama_model()
    if m:
        import torch
        H, W = img.shape[:2]
        ph, pw = (8 - H % 8) % 8, (8 - W % 8) % 8
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        rgb = np.pad(rgb, ((0, ph), (0, pw), (0, 0)), mode="reflect")
        mk = np.pad(mask, ((0, ph), (0, pw)), mode="reflect")
        t_img = torch.from_numpy(rgb).permute(2, 0, 1)[None].float() / 255.0
        t_m = (torch.from_numpy(mk)[None, None].float() > 127).float()
        with torch.no_grad():
            out = m(t_img, t_m)
        res = out[0].permute(1, 2, 0).clamp(0, 1).numpy()
        if res.max() > 1.5:
            res = res / 255.0
        res = (res * 255).astype(np.uint8)[:H, :W]
        res = cv2.cvtColor(res, cv2.COLOR_RGB2BGR)
        keep = (mask[..., None] == 0)
        return np.where(keep, img, res)
    return cv2.inpaint(img, mask, 7, cv2.INPAINT_TELEA)


# ------------------------------------------------------------ cutout

_SESS = None


def cutout(img, model="isnet-anime"):
    global _SESS
    from rembg import new_session, remove
    if _SESS is None:
        _SESS = new_session(model)
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    rgba = remove(rgb, session=_SESS, post_process_mask=True)
    a = np.asarray(rgba)[..., 3]
    return a


def process(path, out_root, do_bubbles=True, extra_mask=None, fg=True, min_fg=0.02):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    name = os.path.splitext(os.path.basename(path))[0]
    od = os.path.join(out_root, name)
    os.makedirs(od, exist_ok=True)
    H, W = img.shape[:2]
    bm = bubble_mask(img) if do_bubbles else np.zeros((H, W), np.uint8)
    if extra_mask:
        em = cv2.imread(extra_mask, cv2.IMREAD_GRAYSCALE)
        bm = np.maximum(bm, cv2.resize(em, (W, H)))
    clean = inpaint(img, bm)
    cv2.imwrite(os.path.join(od, "mask_bubbles.png"), bm)
    cv2.imwrite(os.path.join(od, "clean.png"), clean)
    bub = np.dstack([img, bm])
    cv2.imwrite(os.path.join(od, "bubbles.png"), bub)
    files = {"clean": "clean.png", "bubbles": "bubbles.png"}
    if fg:
        a = cutout(clean)
        if (a > 127).mean() >= min_fg:
            cv2.imwrite(os.path.join(od, "mask_fg.png"), a)
            cv2.imwrite(os.path.join(od, "fg.png"), np.dstack([clean, a]))
            hole = cv2.dilate((a > 40).astype(np.uint8) * 255, np.ones((15, 15), np.uint8))
            bg = inpaint(clean, hole)
            cv2.imwrite(os.path.join(od, "bg.png"), bg)
            files.update(fg="fg.png", bg="bg.png")
    # preview strip: original | clean | bg | fg on checker
    tiles = [img, clean]
    if "bg" in files:
        tiles.append(cv2.imread(os.path.join(od, "bg.png")))
        chk = ((np.indices((H, W)).sum(axis=0) // 16) % 2 * 60 + 150).astype(np.uint8)
        chk = cv2.cvtColor(chk, cv2.COLOR_GRAY2BGR)
        af = (a.astype(np.float32) / 255)[..., None]
        tiles.append((clean * af + chk * (1 - af)).astype(np.uint8))
    cv2.imwrite(os.path.join(od, "preview.jpg"), np.hstack(tiles) if W < H else np.vstack(tiles))
    print(f"{path} -> {od}  {sorted(files)}")
    return od, files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("panels", nargs="+")
    ap.add_argument("-o", "--out", default="assets/layers")
    ap.add_argument("--keep-bubbles", action="store_true", help="do not remove speech bubbles")
    ap.add_argument("--no-fg", action="store_true", help="skip character cutout")
    ap.add_argument("--extra-mask", help="white = also remove (e.g. sound effects)")
    a = ap.parse_args()
    for p in a.panels:
        process(p, a.out, not a.keep_bubbles, a.extra_mask, not a.no_fg)


if __name__ == "__main__":
    sys.exit(main())
