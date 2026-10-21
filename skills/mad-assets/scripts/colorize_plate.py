"""Flat block colouring of a (rebuilt) manga background plate — one colour per material region,
original line art and soft tone kept on top. Lighting/shadow is added later in the 3D renderer.

  python3 colorize_plate.py plate.png spec.yaml out.png [--preview prev.jpg]

spec.yaml
  base: "#8a8f96"              # colour for anything not claimed
  tone: 0.35                   # how much of the original grey shading survives (0 = pure flat)
  line: "#1a1416"              # ink colour
  regions:                     # later wins; points normalised [x, y]
    - {name: floor, color: "#7a5a3e", points: [[0.1, 0.8]], neg: [[0.4, 0.6]]}
    - {name: wall,  color: "#c9c2b0", points: [[0.5, 0.15]], box: [0, 0, 1, 0.4]}
    - {name: sky,   color: "#1c2340", rect: [0, 0, 1, 0.2]}            # plain rectangle
    - {name: glass, color: "#2a3a48", points: [[0.6, 0.4]], dark_only: 0.5}
"""
import argparse
import os
import sys

import cv2
import numpy as np
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mad-character", "scripts"))


def hexc(c):
    c = c.lstrip("#")
    return np.array([int(c[4:6], 16), int(c[2:4], 16), int(c[0:2], 16)], np.float32) / 255.0  # BGR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plate")
    ap.add_argument("spec")
    ap.add_argument("out")
    ap.add_argument("--preview")
    a = ap.parse_args()
    from segment import predict
    spec = yaml.safe_load(open(a.spec, encoding="utf-8"))
    im = cv2.imread(a.plate, cv2.IMREAD_COLOR)
    H, W = im.shape[:2]
    s = min(1.0, 1400 / max(H, W))
    small = cv2.resize(im, (int(W * s), int(H * s)), interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]
    rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
    gray_s = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    label = np.full((sh, sw), -1, np.int32)
    regs = spec["regions"]
    for i, r in enumerate(regs):
        m = np.zeros((sh, sw), np.uint8)
        if r.get("points"):
            pts = [[p[0] * sw, p[1] * sh] for p in r["points"]]
            neg = [[p[0] * sw, p[1] * sh] for p in (r.get("neg") or [])]
            box = [r["box"][0] * sw, r["box"][1] * sh, r["box"][2] * sw, r["box"][3] * sh] if r.get("box") else None
            m, sc = predict(rgb, pts, neg, box)
            print(f"{r['name']:<10} score {sc:.2f} area {m.mean() * 100:.1f}%")
        if r.get("rect"):
            x0, y0, x1, y1 = r["rect"]
            m[int(y0 * sh):int(y1 * sh), int(x0 * sw):int(x1 * sw)] = 1
        if r.get("poly"):
            cv2.fillPoly(m, [np.int32([[p[0] * sw, p[1] * sh] for p in r["poly"]])], 1)
        if r.get("clip"):
            x0, y0, x1, y1 = r["clip"]
            c = np.zeros_like(m)
            c[int(y0 * sh):int(y1 * sh), int(x0 * sw):int(x1 * sw)] = 1
            m &= c
        if r.get("dark_only"):
            m &= (gray_s < float(r["dark_only"])).astype(np.uint8)
        if r.get("light_only"):
            m &= (gray_s > float(r["light_only"])).astype(np.uint8)
        label[m > 0] = i
    # unclaimed pixels -> nearest region (lines between regions), else base
    un = label < 0
    if un.any() and (~un).any():
        best = np.full((sh, sw), np.inf, np.float32)
        for i in range(len(regs)):
            mk = label == i
            if not mk.any():
                continue
            d = cv2.distanceTransform((~mk).astype(np.uint8), cv2.DIST_L2, 5)
            upd = un & (d < best) & (d < float(spec.get("nearest_max", 12)))
            label[upd] = i
            best[upd] = d[upd]
    flat_s = np.zeros((sh, sw, 3), np.float32)
    flat_s[:] = hexc(spec.get("base", "#8a8f96"))
    for i, r in enumerate(regs):
        flat_s[label == i] = hexc(r["color"])
    flat = cv2.resize(flat_s, (W, H), interpolation=cv2.INTER_NEAREST)
    flat = cv2.medianBlur((flat * 255).astype(np.uint8), 5).astype(np.float32) / 255
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    tone = float(spec.get("tone", 0.35))
    # line art = strong darks; tone = remaining grey shading normalised around paper white
    if spec.get("ink", "edge") == "edge":
        # ink = locally darker strokes (lines, hatching), not large dark areas like a night sky
        sig = max(2.0, max(H, W) / 600)
        local = cv2.GaussianBlur(g, (0, 0), sig * 3)
        ink = np.clip((local - g - 0.05) / 0.18, 0, 1) * np.clip((0.75 - g) / 0.35, 0, 1)
        ink = ink[..., None]
    else:
        ink = np.clip((0.42 - g) / 0.3, 0, 1)[..., None]
    shade = (1 - tone) + tone * np.clip(g / 0.85, 0, 1.15)[..., None]
    out = flat * shade
    out = out * (1 - ink) + hexc(spec.get("line", "#1a1416")) * ink
    kh = float(spec.get("keep_highlights", 0))
    if kh:  # stars, sparkles, specular glints survive the flat fill
        hl = (np.clip((g - 0.78) / 0.17, 0, 1) * kh)[..., None]
        out = out * (1 - hl) + hexc(spec.get("highlight", "#fff6e8")) * hl
    out = np.clip(out * 255, 0, 255).astype(np.uint8)
    cv2.imwrite(a.out, out)
    if a.preview:
        v = cv2.resize(np.hstack([im, out]), None, fx=1200 / (2 * W), fy=1200 / (2 * W))
        cv2.imwrite(a.preview, v)
    print("->", a.out)


if __name__ == "__main__":
    sys.exit(main())
