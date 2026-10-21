"""Colour a black-and-white manga panel with a gradient map, key out paper-white background,
and generate a matching backdrop.

  python3 stylize.py clean.png -o char.png --palette green_glow [--key] [--backdrop bg.png --bg-size 2400x1350]
  python3 stylize.py a.png --align-to b.png -o a_aligned.png --points "x,y x,y x,y" "x,y x,y x,y"

Palettes map luminance -> colour (stops 0..1). Add your own in PALETTES.
--key   : near-white regions connected to the image border become transparent
          (works for close-ups where AI cutout fails; the art itself stays opaque).
"""
import argparse
import sys

import cv2
import numpy as np

PALETTES = {
    # dark hair -> warm skin -> cream highlights; meant to sit on a green backlit backdrop
    "green_glow": [(0.0, (14, 10, 16)), (0.25, (42, 26, 24)), (0.55, (150, 96, 70)),
                   (0.78, (240, 188, 138)), (0.92, (252, 226, 186)), (1.0, (255, 246, 228))],
    "sepia": [(0.0, (20, 14, 10)), (0.5, (130, 96, 64)), (1.0, (250, 236, 210))],
    "cold": [(0.0, (8, 10, 20)), (0.5, (70, 90, 130)), (1.0, (230, 240, 255))],
    "blood": [(0.0, (10, 2, 4)), (0.45, (110, 12, 20)), (0.8, (230, 160, 150)), (1.0, (255, 240, 235))],
    "dusk": [(0.0, (20, 8, 30)), (0.4, (120, 40, 80)), (0.75, (240, 150, 110)), (1.0, (255, 235, 200))],
}

BACKDROPS = {
    "green_glow": dict(base=(4, 22, 10), light=(150, 255, 120), core=(240, 255, 200)),
    "blood": dict(base=(18, 2, 4), light=(220, 30, 40), core=(255, 200, 180)),
    "cold": dict(base=(2, 6, 18), light=(80, 140, 255), core=(220, 235, 255)),
    "dusk": dict(base=(16, 4, 20), light=(255, 120, 80), core=(255, 230, 190)),
}


def gradient_map(gray01, stops):
    xs = np.array([s[0] for s in stops], np.float32)
    lut = np.zeros((256, 3), np.float32)
    v = np.linspace(0, 1, 256)
    for c in range(3):
        lut[:, c] = np.interp(v, xs, [s[1][c] for s in stops])
    idx = np.clip(gray01 * 255, 0, 255).astype(np.uint8)
    return lut[idx] / 255.0  # RGB 0..1


def key_paper(gray, thresh=0.9, feather=3):
    """Alpha = 0 for near-white regions touching the border."""
    H, W = gray.shape
    white = (gray >= thresh).astype(np.uint8)
    n, lab = cv2.connectedComponents(white, connectivity=4)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(border)).astype(np.uint8)
    bg = cv2.morphologyEx(bg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    alpha = 1.0 - bg.astype(np.float32)
    if feather:
        alpha = cv2.GaussianBlur(alpha, (0, 0), feather)
    return alpha


def backdrop(w, h, scheme="green_glow", seed=3, columns=9, text=None, font=None):
    """Blurred vertical light columns + bokeh: the 'forest light' look."""
    rng = np.random.default_rng(seed)
    sc = BACKDROPS.get(scheme, BACKDROPS["green_glow"])
    base = np.array(sc["base"], np.float32) / 255
    light = np.array(sc["light"], np.float32) / 255
    core = np.array(sc["core"], np.float32) / 255
    img = np.ones((h, w, 3), np.float32) * base
    lum = np.zeros((h, w), np.float32)
    xs = np.linspace(0, w, columns + 2)[1:-1] + rng.uniform(-w * 0.04, w * 0.04, columns)
    for x in xs:
        width = rng.uniform(0.02, 0.06) * w
        strength = rng.uniform(0.25, 0.8) * (1 - abs(x - w / 2) / (w / 2)) ** 0.5
        col = np.exp(-((np.arange(w) - x) / width) ** 2) * strength
        lum += col[None, :] * (0.6 + 0.4 * np.linspace(1, 0.4, h))[:, None]
    # central glow behind the subject
    yy, xx = np.mgrid[0:h, 0:w]
    lum += 0.9 * np.exp(-(((xx - w / 2) / (w * 0.18)) ** 2 + ((yy - h * 0.45) / (h * 0.55)) ** 2))
    for _ in range(60):
        cx, cy, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.004, 0.02) * w
        cv2.circle(lum, (int(cx), int(cy)), int(r), float(rng.uniform(0.1, 0.4)), -1, cv2.LINE_AA)
    lum = cv2.GaussianBlur(lum, (0, 0), w * 0.01)
    lum = np.clip(lum, 0, 1.6)[..., None]
    img = img + light * np.clip(lum, 0, 1) + (core - light) * np.clip(lum - 0.8, 0, 1)
    return np.clip(img, 0, 1)


def align(src, dst, src_pts, dst_pts):
    M, _ = cv2.estimateAffinePartial2D(np.float32(src_pts), np.float32(dst_pts))
    # pad with paper white so the new border gets keyed out like the rest of the paper
    return cv2.warpAffine(src, M, (dst.shape[1], dst.shape[0]), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))


def edge_feather(h, w, amount, sides="lrt"):
    """Alpha ramp that fades the panel's rectangular border into the backdrop."""
    m = np.ones((h, w), np.float32)
    def ramp(n):
        k = max(1, int(n * amount))
        r = np.ones(n, np.float32)
        x = np.linspace(0, 1, k)
        r[:k] = x * x * (3 - 2 * x)
        return r
    if "l" in sides:
        m *= ramp(w)[None, :]
    if "r" in sides:
        m *= ramp(w)[::-1][None, :]
    if "t" in sides:
        m *= ramp(h)[:, None]
    if "b" in sides:
        m *= ramp(h)[::-1][:, None]
    return m


def _pts(s):
    return [tuple(float(v) for v in p.split(",")) for p in s.split()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--palette", default="green_glow")
    ap.add_argument("--key", action="store_true")
    ap.add_argument("--key-thresh", type=float, default=0.9)
    ap.add_argument("--upscale", type=float, default=1.0, help="Lanczos upscale + light sharpen first")
    ap.add_argument("--contrast", type=float, default=1.0)
    ap.add_argument("--feather", type=float, default=0.0, help="fade panel border, fraction of size (e.g. 0.12)")
    ap.add_argument("--feather-sides", default="lrt")
    ap.add_argument("--backdrop", help="also write a matching backdrop PNG here")
    ap.add_argument("--bg-size", default="2400x1350")
    ap.add_argument("--align-to", help="align this image onto another before styling")
    ap.add_argument("--points", nargs=2, help='"x,y x,y x,y" in this image, then in the target')
    a = ap.parse_args()
    img = cv2.imread(a.image, cv2.IMREAD_COLOR)
    if a.align_to:
        dst = cv2.imread(a.align_to, cv2.IMREAD_COLOR)
        img = align(img, dst, _pts(a.points[0]), _pts(a.points[1]))
    if a.upscale != 1.0:
        img = cv2.resize(img, None, fx=a.upscale, fy=a.upscale, interpolation=cv2.INTER_LANCZOS4)
        blur = cv2.GaussianBlur(img, (0, 0), 1.2)
        img = cv2.addWeighted(img, 1.4, blur, -0.4, 0)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    if a.contrast != 1.0:
        gray = np.clip((gray - 0.5) * a.contrast + 0.5, 0, 1)
    if a.palette == "none":
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    else:
        rgb = gradient_map(gray, PALETTES[a.palette])
    out = cv2.cvtColor((rgb * 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
    if a.key or a.feather:
        alpha = key_paper(gray, a.key_thresh) if a.key else np.ones_like(gray)
        if a.feather:
            alpha *= edge_feather(*gray.shape, a.feather, a.feather_sides)
        out = np.dstack([out, (alpha * 255).astype(np.uint8)])
    cv2.imwrite(a.out, out)
    print(a.out, out.shape)
    if a.backdrop:
        w, h = (int(v) for v in a.bg_size.split("x"))
        bg = backdrop(w, h, a.palette if a.palette in BACKDROPS else "green_glow")
        cv2.imwrite(a.backdrop, cv2.cvtColor((bg * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
        print(a.backdrop)


if __name__ == "__main__":
    sys.exit(main())
