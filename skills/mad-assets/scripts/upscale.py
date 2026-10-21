"""Rebuild a low-res manga plate at high resolution: descreen -> 4x anime super-resolution -> line sharpening.

  python3 upscale.py in.png out.png [--scale 4] [--descreen 1.0] [--tile 256] [--sharpen 0.5]

Model: Real-ESRGAN x4plus_anime_6B (~/.u2net/RealESRGAN_x4plus_anime_6B.pth, loaded with spandrel).
Screentone (halftone dots) is removed first so it does not get "upscaled" into big dots: a light
bilateral/median pass at source resolution, strength --descreen (0 = off).
CPU tiled inference; ~10–40 s for an 800 px panel.
"""
import argparse
import os
import sys
import time

import cv2
import numpy as np
import torch

MODEL = os.path.expanduser("~/.u2net/RealESRGAN_x4plus_anime_6B.pth")
_M = None


def model():
    global _M
    if _M is None:
        from spandrel import ModelLoader
        _M = ModelLoader().load_from_file(MODEL).model.eval()
        torch.set_num_threads(os.cpu_count() or 4)
    return _M


def descreen(bgr, k=1.0):
    if k <= 0:
        return bgr
    d = cv2.bilateralFilter(bgr, 5, 30 * k, 3)
    med = cv2.medianBlur(bgr, 3)
    # keep real ink lines: where the image is strongly dark & edged, prefer the original
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    edge = cv2.Laplacian(cv2.GaussianBlur(g, (0, 0), 1.0), cv2.CV_32F)
    ink = np.clip((80 - g) / 60, 0, 1) * np.clip(np.abs(edge) / 25, 0, 1)
    ink = cv2.GaussianBlur(ink, (0, 0), 0.8)[..., None]
    soft = (0.5 * d + 0.5 * med).astype(np.float32)
    return (bgr * ink + soft * (1 - ink)).astype(np.uint8)


def sr(bgr, tile=256, pad=16):
    m = model()
    x = torch.from_numpy(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255).permute(2, 0, 1)[None]
    _, _, H, W = x.shape
    out = torch.zeros((1, 3, H * 4, W * 4))
    with torch.no_grad():
        for y0 in range(0, H, tile):
            for x0 in range(0, W, tile):
                ya, yb = max(0, y0 - pad), min(H, y0 + tile + pad)
                xa, xb = max(0, x0 - pad), min(W, x0 + tile + pad)
                o = m(x[:, :, ya:yb, xa:xb])
                oy, ox = (y0 - ya) * 4, (x0 - xa) * 4
                h, w = min(tile, H - y0) * 4, min(tile, W - x0) * 4
                out[:, :, y0 * 4:y0 * 4 + h, x0 * 4:x0 * 4 + w] = o[:, :, oy:oy + h, ox:ox + w]
    rgb = (out[0].permute(1, 2, 0).clamp(0, 1).numpy() * 255).astype(np.uint8)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def rebuild(bgr, scale=4, k_descreen=1.0, tile=256, sharpen=0.5):
    x = descreen(bgr, k_descreen)
    y = sr(x, tile)
    if scale != 4:
        y = cv2.resize(y, (bgr.shape[1] * scale, bgr.shape[0] * scale), interpolation=cv2.INTER_AREA)
    if sharpen > 0:
        b = cv2.GaussianBlur(y, (0, 0), 1.2)
        y = cv2.addWeighted(y, 1 + sharpen, b, -sharpen, 0)
    return y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--descreen", type=float, default=1.0)
    ap.add_argument("--tile", type=int, default=256)
    ap.add_argument("--sharpen", type=float, default=0.5)
    a = ap.parse_args()
    t = time.time()
    im = cv2.imread(a.inp, cv2.IMREAD_COLOR)
    y = rebuild(im, a.scale, a.descreen, a.tile, a.sharpen)
    cv2.imwrite(a.out, y)
    print(f"{a.inp} {im.shape[1]}x{im.shape[0]} -> {y.shape[1]}x{y.shape[0]} in {time.time() - t:.0f}s")


if __name__ == "__main__":
    sys.exit(main())
