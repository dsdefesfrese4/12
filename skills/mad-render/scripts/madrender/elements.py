"""Scene elements for scene3d. Each `kind` turns one layer spec into drawables (quads or screen rasters).

Common placement fields (any number can be an animated <value>):
  pos: [x, y, z]   rot: [rx, ry, rz]   width: w   anchor: center|top|bottom   billboard: false
  opacity, tint: "#hex", light: true, fog: true, dof: true

kinds
  image    src, crop, frame: border|polaroid, feather, key_white (paper -> transparent), invert
  slot     slot (cutouts/<slot>.png, else a placeholder silhouette from cutouts_auto/<slot>_mask.png), crop
  text     text, size (px of texture), color, stroke, vertical, font
  words    words: [...], count, layout: ring|cloud, center, radius, speed (rad/s), spread, size, color, height
  glow     color, width (additive light sprite)
  particles preset: ash|dust|stars|rain|snow|petals|embers, volume, count, vel, size, color, opacity
  ribbon   pos (top anchor), length, width, sway, color, twist
  strings  targets: [[x,y,z],...], top: y, color, sway
  vines    width, height, grow: <0..1>, seed, origins: [[u,v,angle_deg],...], branches, color, thorns
  shatter  src, explode: <0..1>, pieces, seed, spread, toward (camera), spin
  cage     bars, width, height, color, thickness
  blood    seed, width, color
  clock    width, speed (rev/s of the minute hand), color
"""
import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import effects as fx
from . import puppet
from .text import find_font


def premul(rgba):
    out = rgba.astype(np.float32).copy()
    out[..., :3] *= out[..., 3:4]
    return out


def _v(x, t, ctx, d=0.0):
    return puppet.value(x, t, ctx, d)


def _vec(x, t, ctx, d=(0, 0, 0)):
    if x is None:
        return np.array(d, np.float64)
    return np.array([_v(c, t, ctx, dd) for c, dd in zip(x, d)], np.float64)


def _rgb(c, d="#ffffff"):
    return np.array(fx.hex_rgb(c or d), np.float32)


def rot_matrix(rx, ry, rz):
    from .scene3d import rot_matrix as rm
    return rm(rx, ry, rz)


# ------------------------------------------------------------------ texture makers

def load_rgba(path, crop=None):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise FileNotFoundError(path)
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGRA)
    elif im.shape[2] == 3:
        im = cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
    if crop:
        H0, W0 = im.shape[:2]
        im = im[int(crop[1] * H0):int((crop[1] + crop[3]) * H0), int(crop[0] * W0):int((crop[0] + crop[2]) * W0)]
    rgba = cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA).astype(np.float32) / 255.0
    # cap texture size (memory); mip levels handle minification
    h, w = rgba.shape[:2]
    s = min(1.0, 2200 / max(h, w))
    if s < 1:
        rgba = cv2.resize(rgba, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return rgba


def gradient_map(rgba, stops):
    """Colourise a B/W plate: luminance -> shadow / mid / highlight colours (keeps ink, adds a palette)."""
    cols = [np.array(fx.hex_rgb(c), np.float32) for c in stops]
    xs = np.linspace(0, 1, len(cols))
    lum = rgba[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
    lut_x = np.linspace(0, 1, 256)
    lut = np.stack([np.interp(lut_x, xs, [c[i] for c in cols]) for i in range(3)], 1).astype(np.float32)
    rgba[..., :3] = lut[np.clip(lum * 255, 0, 255).astype(np.uint8)]
    return rgba


def decorate(rgba, L):
    if L.get("gmap"):
        rgba = gradient_map(rgba, L["gmap"])
    if L.get("key_white"):
        lum = rgba[..., :3].mean(axis=2)
        k = float(L.get("key_white", 0.9)) if not isinstance(L.get("key_white"), bool) else 0.9
        rgba[..., 3] *= np.clip((k + 0.06 - lum) / 0.12, 0, 1)
    if L.get("invert"):
        rgba[..., :3] = 1 - rgba[..., :3]
    fr = L.get("frame")
    if fr:
        h, w = rgba.shape[:2]
        b = int(max(h, w) * (0.035 if fr == "border" else 0.05))
        bb = int(b * (3.2 if fr == "polaroid" else 1))
        out = np.zeros((h + b + bb, w + 2 * b, 4), np.float32)
        out[..., :3] = _rgb(L.get("frame_color", "#f4f0e8"))
        out[..., 3] = 1
        out[b:b + h, b:b + w, :3] = rgba[..., :3] * rgba[..., 3:4] + out[b:b + h, b:b + w, :3] * (1 - rgba[..., 3:4])
        rgba = out
    fe = float(L.get("feather", 0))
    if fe > 0:
        h, w = rgba.shape[:2]
        def ramp(n):
            k = max(1, int(n * fe))
            r = np.ones(n, np.float32)
            x = np.linspace(0, 1, k)
            r[:k] = x * x * (3 - 2 * x)
            r[n - k:] = np.minimum(r[n - k:], r[:k][::-1])
            return r
        rgba[..., 3] *= ramp(h)[:, None] * ramp(w)[None, :]
    return rgba


def text_rgba(text, size=160, color="#ffffff", stroke=None, vertical=False, font=None, root=None):
    fp = find_font(font, root)
    f = ImageFont.truetype(fp, int(size)) if fp else ImageFont.load_default()
    sw = int(stroke.get("width", 0)) if stroke else 0
    sc = tuple(int(c * 255) for c in fx.hex_rgb(stroke.get("color", "#000000"))) if stroke else (0, 0, 0)
    col = tuple(int(c * 255) for c in fx.hex_rgb(color))
    chars = list(text) if vertical else [text]
    boxes = [f.getbbox(c, stroke_width=sw) for c in chars]
    if vertical:
        w = max(b[2] - b[0] for b in boxes) + sw * 2 + 8
        h = int(sum(size * 1.05 for _ in chars)) + sw * 2 + 8
    else:
        b = boxes[0]
        w, h = b[2] - b[0] + sw * 2 + 8, b[3] - b[1] + sw * 2 + 8
    im = Image.new("RGBA", (max(2, w), max(2, h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if vertical:
        y = 4
        for c, b in zip(chars, boxes):
            d.text(((w - (b[2] - b[0])) / 2 - b[0], y - b[1] * 0.2), c, font=f, fill=col + (255,), stroke_width=sw,
                   stroke_fill=sc + (255,))
            y += size * 1.05
    else:
        b = boxes[0]
        d.text((4 + sw - b[0], 4 + sw - b[1]), text, font=f, fill=col + (255,), stroke_width=sw, stroke_fill=sc + (255,))
    return np.asarray(im).astype(np.float32) / 255.0


def glow_rgba(size=256, color="#ffffff", power=2.0):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2) / (size / 2)
    g = np.clip(1 - r, 0, 1) ** power
    out = np.zeros((size, size, 4), np.float32)
    out[..., :3] = _rgb(color) * g[..., None]
    # alpha 0 => purely additive after premultiplication trick (rgb already "premultiplied")
    return out


def cage_rgba(bars=9, w=1200, h=1600, color="#1a1414", thick=0.022):
    out = np.zeros((h, w, 4), np.float32)
    col = _rgb(color)
    bw = max(3, int(w * thick))
    for i in range(bars):
        x = int((i + 0.5) * w / bars)
        out[:, x - bw // 2:x + bw // 2, :3] = col
        out[:, x - bw // 2:x + bw // 2, 3] = 1
        hl = max(1, bw // 5)
        out[:, x - bw // 2 + hl:x - bw // 2 + 2 * hl, :3] = np.minimum(1, col + 0.35)
    for y in (int(h * 0.04), int(h * 0.96)):
        out[y - bw // 2:y + bw // 2, :, :3] = col
        out[y - bw // 2:y + bw // 2, :, 3] = 1
    return out


def blood_rgba(seed=1, size=1024, color="#5e070b"):
    rng = np.random.default_rng(seed)
    m = np.zeros((size, size), np.float32)
    c = size / 2
    cv2.circle(m, (int(c), int(c)), int(size * 0.16), 1, -1, cv2.LINE_AA)
    for _ in range(26):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0.1, 0.45) * size
        r = rng.uniform(0.01, 0.06) * size * (1 - d / size)
        x, y = c + math.cos(a) * d, c + math.sin(a) * d
        cv2.circle(m, (int(x), int(y)), max(2, int(r)), 1, -1, cv2.LINE_AA)
        cv2.line(m, (int(c + math.cos(a) * size * 0.12), int(c + math.sin(a) * size * 0.12)), (int(x), int(y)), 1,
                 max(2, int(r * 0.7)), cv2.LINE_AA)
    for _ in range(140):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0.15, 0.5) * size
        cv2.circle(m, (int(c + math.cos(a) * d), int(c + math.sin(a) * d)), max(1, int(rng.uniform(1, 6))), 1, -1,
                   cv2.LINE_AA)
    m = cv2.GaussianBlur(m, (0, 0), 1.2)
    out = np.zeros((size, size, 4), np.float32)
    col = _rgb(color)
    shade = 0.75 + 0.25 * cv2.GaussianBlur(m, (0, 0), size * 0.02)
    out[..., :3] = col * shade[..., None]
    out[..., 3] = np.clip(m * 1.2, 0, 1)
    return out


def clock_rgba(angle, size=900, color="#f2ede2"):
    im = np.zeros((size, size, 4), np.float32)
    c = size // 2
    col = _rgb(color)
    face = np.zeros((size, size), np.float32)
    cv2.circle(face, (c, c), int(size * 0.47), 1, -1, cv2.LINE_AA)
    im[..., :3] = col
    im[..., 3] = face
    ink = np.zeros((size, size), np.float32)
    cv2.circle(ink, (c, c), int(size * 0.47), 1, int(size * 0.02), cv2.LINE_AA)
    for i in range(12):
        a = i / 12 * 2 * math.pi
        r0, r1 = size * 0.38, size * 0.44
        cv2.line(ink, (int(c + math.sin(a) * r0), int(c - math.cos(a) * r0)), (int(c + math.sin(a) * r1), int(c - math.cos(a) * r1)),
                 1, int(size * 0.015), cv2.LINE_AA)
    for a, L, th in ((angle, 0.38, 0.016), (angle / 12, 0.25, 0.026)):
        cv2.line(ink, (c, c), (int(c + math.sin(a) * size * L), int(c - math.cos(a) * size * L)), 1, int(size * th), cv2.LINE_AA)
    cv2.circle(ink, (c, c), int(size * 0.025), 1, -1, cv2.LINE_AA)
    im[..., :3] = im[..., :3] * (1 - ink[..., None]) + np.array([0.06, 0.05, 0.05], np.float32) * ink[..., None]
    return im


class Vines:
    """Thorny vine growth. Segments carry an appear-time in 0..1; rendering at `grow` draws what exists."""

    def __init__(self, seed, w, h, origins, branches, thorns=True):
        rng = np.random.default_rng(seed)
        self.w, self.h = w, h
        segs = []
        diag = math.hypot(w, h)

        def grow(x, y, ang, thick, t0, length, depth):
            n = int(length / (diag * 0.012)) + 2
            step = length / n
            curl = rng.uniform(-0.06, 0.06)
            for i in range(n):
                ang += curl + rng.normal(0, 0.12)
                curl += rng.normal(0, 0.01)
                nx, ny = x + math.cos(ang) * step, y + math.sin(ang) * step
                tt = t0 + (i / n) * (1 - t0) * (0.55 if depth == 0 else 0.4)
                th = thick * (1 - 0.8 * i / n)
                segs.append((x, y, nx, ny, max(1.0, th), tt, "s"))
                if thorns and i % 3 == 1 and th > 2:
                    side = 1 if rng.random() < 0.5 else -1
                    ta = ang + side * rng.uniform(0.8, 1.3)
                    tl = th * rng.uniform(1.4, 2.6)
                    segs.append((nx, ny, nx + math.cos(ta) * tl, ny + math.sin(ta) * tl, th * 0.55, tt + 0.01, "t"))
                if depth < 2 and rng.random() < 0.05:
                    grow(nx, ny, ang + rng.choice([-1, 1]) * rng.uniform(0.5, 1.1), th * 0.65, tt, length * rng.uniform(0.3, 0.55),
                         depth + 1)
                x, y = nx, ny

        for k in range(branches):
            ou, ov, oa = origins[k % len(origins)]
            grow(ou * w, ov * h, math.radians(oa) + rng.normal(0, 0.25), diag * rng.uniform(0.006, 0.011),
                 rng.uniform(0, 0.25), diag * rng.uniform(0.35, 0.6), 0)
        self.segs = segs

    def render(self, g, color="#090506"):
        m = np.zeros((self.h, self.w), np.float32)
        for x0, y0, x1, y1, th, tt, kind in self.segs:
            if tt <= g:
                cv2.line(m, (int(x0), int(y0)), (int(x1), int(y1)), 1.0, int(round(th)), cv2.LINE_AA)
        out = np.zeros((self.h, self.w, 4), np.float32)
        out[..., :3] = _rgb(color)
        out[..., 3] = m
        return out


_VINES = {}
_SHARDS = {}


def shatter_pieces(rgba, n, seed):
    h, w = rgba.shape[:2]
    s = min(1.0, 700 / max(h, w))
    small = cv2.resize(rgba, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else rgba
    h, w = small.shape[:2]
    rng = np.random.default_rng(seed)
    pts = np.stack([rng.uniform(0, w, n), rng.uniform(0, h, n)], 1)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    best = np.full((h, w), 1e9, np.float32)
    lab = np.zeros((h, w), np.int32)
    for i, (px, py) in enumerate(pts):
        d = (xx - px) ** 2 + (yy - py) ** 2
        upd = d < best
        best[upd] = d[upd]
        lab[upd] = i
    pieces = []
    for i in range(n):
        ys, xs = np.nonzero(lab == i)
        if len(xs) < 20:
            continue
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        tile = small[y0:y1, x0:x1].copy()
        mask = (lab[y0:y1, x0:x1] == i).astype(np.float32)
        mask = cv2.erode(mask, np.ones((2, 2), np.uint8))
        tile[..., 3] *= mask
        cx, cy = (x0 + x1) / 2 / w - 0.5, 0.5 - (y0 + y1) / 2 / h
        pieces.append((premul(tile), cx, cy, (x1 - x0) / w, rng.normal(0, 1, 3), rng.uniform(0.6, 1.4)))
    return pieces, h / w


PARTICLE_PRESETS = {
    "ash": dict(count=260, vel=[0.05, -0.25, 0], size=0.018, color="#1a1414", alpha=0.85, glow=False),
    "embers": dict(count=200, vel=[0.05, 0.35, 0], size=0.02, color="#ff6a2a", alpha=0.9, glow=True),
    "dust": dict(count=220, vel=[0.02, 0.06, 0], size=0.02, color="#fff4dc", alpha=0.55, glow=True),
    "stars": dict(count=900, vel=[0, 0, 0], size=0.012, color="#eef2ff", alpha=0.9, glow=True),
    "snow": dict(count=380, vel=[0.04, -0.35, 0], size=0.025, color="#f4f8ff", alpha=0.9, glow=False),
    "rain": dict(count=500, vel=[0.3, -5.0, 0], size=0.01, color="#c8d4e8", alpha=0.6, glow=False, streak=True),
    "petals": dict(count=160, vel=[0.25, -0.35, 0], size=0.05, color="#f6eef0", alpha=0.95, glow=False, flutter=True),
}


def particles(L, cam, t, ctx, R):
    pre = dict(PARTICLE_PRESETS.get(L.get("preset", "dust"), PARTICLE_PRESETS["dust"]))
    pre.update({k: v for k, v in L.items() if k in ("count", "vel", "size", "color", "alpha", "glow", "streak", "flutter")})
    vol = np.array(L.get("volume", [[-6, 6], [-4, 4], [0, 20]]), np.float64)
    n = int(pre["count"])
    rng = np.random.default_rng(int(L.get("seed", 7)))
    base = rng.uniform(0, 1, (n, 3))
    span = vol[:, 1] - vol[:, 0]
    vel = np.array(pre["vel"], np.float64) * float(L.get("speed", 1.0))
    ph = rng.uniform(0, 2 * math.pi, n)
    P = vol[:, 0] + ((base * span + vel * t + (rng.uniform(0.6, 1.4, (n, 1)) - 1) * vel * t) - vol[:, 0] + vol[:, 0]) % span
    P = vol[:, 0] + np.mod(base * span + vel * t * rng.uniform(0.6, 1.4, (n, 1)), span)
    if pre.get("flutter"):
        P[:, 0] += 0.25 * np.sin(t * 1.7 + ph)
        P[:, 2] += 0.15 * np.cos(t * 1.3 + ph)
    Pc = cam.to_cam(P)
    ok = Pc[:, 2] > 0.2
    Pc, ph2 = Pc[ok], ph[ok]
    if not len(Pc):
        return []
    scr = cam.project(Pc)
    W, H = cam.W, cam.H
    col = _rgb(pre["color"])
    out = []
    bins = int(L.get("bins", 3))
    qs = np.quantile(Pc[:, 2], np.linspace(0, 1, bins + 1))
    for b in range(bins):
        sel = (Pc[:, 2] >= qs[b]) & (Pc[:, 2] <= qs[b + 1] + 1e-9)
        if not sel.any():
            continue
        m = np.zeros((H, W), np.float32)
        for (x, y), z, p_ in zip(scr[sel], Pc[sel][:, 2], ph2[sel]):
            r = float(pre["size"]) * cam.f / z
            if x < -50 or y < -50 or x > W + 50 or y > H + 50:
                continue
            br = 1.0
            if L.get("preset") == "stars":
                br = 0.55 + 0.45 * math.sin(t * 2.5 + p_)
            if pre.get("streak"):
                L_ = vel * 0.04
                q = cam.project(cam.to_cam(np.array([[0, 0, 0]]) + 0)[0:0]) if False else None
                cv2.line(m, (int(x), int(y)), (int(x - vel[0] * 6 / z * cam.f * 0.01), int(y + abs(vel[1]) * 9 / z * cam.f * 0.01)), br,
                         max(1, int(r)), cv2.LINE_AA)
            elif pre.get("flutter"):
                ax = max(1, int(r))
                cv2.ellipse(m, (int(x), int(y)), (ax, max(1, int(r * 0.45))), (p_ * 57 + t * 90) % 180, 0, 360, br, -1, cv2.LINE_AA)
            else:
                cv2.circle(m, (int(x), int(y)), max(1, int(r)), br, -1, cv2.LINE_AA)
        m = cv2.GaussianBlur(m, (0, 0), 0.8)
        a = np.clip(m * float(pre["alpha"]) * _v(L.get("opacity", 1.0), t, ctx, 1.0), 0, 1)[..., None]
        img = np.zeros((H, W, 4), np.float32)
        img[..., :3] = col * a
        img[..., 3:4] = 0 if pre.get("glow") else a
        out.append({"type": "raster", "depth": float(np.median(Pc[sel][:, 2])), "img": img,
                    "fog": L.get("fog", True), "dof": L.get("dof", True)})
    return out


def lines_raster(polys, widths, color, cam, alpha=1.0, shade=None):
    """polys: list of (N,3) world polylines; widths world units; drawn in screen space."""
    W, H = cam.W, cam.H
    m = np.zeros((H, W), np.float32)
    cm = np.zeros((H, W), np.float32) if shade is not None else None
    depths = []
    for k, P in enumerate(polys):
        Pc = cam.to_cam(P)
        if (Pc[:, 2] < 0.15).any():
            Pc = Pc[Pc[:, 2] >= 0.15]
            if len(Pc) < 2:
                continue
        depths.append(float(Pc[:, 2].mean()))
        S = cam.project(Pc)
        for i in range(len(S) - 1):
            th = max(1, int(round(widths[k] * cam.f / Pc[i, 2])))
            cv2.line(m, tuple(int(v) for v in S[i]), tuple(int(v) for v in S[i + 1]), 1.0, th, cv2.LINE_AA)
            if cm is not None:
                cv2.line(cm, tuple(int(v) for v in S[i]), tuple(int(v) for v in S[i + 1]), float(shade[k][i]), th, cv2.LINE_AA)
    if not depths:
        return None
    a = np.clip(m * alpha, 0, 1)[..., None]
    img = np.zeros((H, W, 4), np.float32)
    rgb = _rgb(color)
    if cm is not None:
        img[..., :3] = rgb * a * (0.55 + 0.45 * cm[..., None])
    else:
        img[..., :3] = rgb * a
    img[..., 3:4] = a
    return {"type": "raster", "depth": float(np.mean(depths)), "img": img}


# ------------------------------------------------------------------ placement

def quad(levels, L, cam, t, ctx, aspect=None, extra_pos=None, extra_R=None, width=None, opacity=None):
    lv0 = levels[0]
    asp = aspect if aspect is not None else lv0.shape[0] / lv0.shape[1]
    w = width if width is not None else _v(L.get("width", 4), t, ctx, 4)
    h = w * asp
    pos = _vec(L.get("pos"), t, ctx, (0, 0, 8))
    if extra_pos is not None:
        pos = pos + extra_pos
    anchor = L.get("anchor", "center")
    oy = {"center": 0, "top": -h / 2, "bottom": h / 2}[anchor]
    local = np.array([[-w / 2, h / 2 + oy, 0], [w / 2, h / 2 + oy, 0], [w / 2, -h / 2 + oy, 0], [-w / 2, -h / 2 + oy, 0]])
    if L.get("billboard"):
        rz = math.radians(_v((L.get("rot") or [0, 0, 0])[2], t, ctx, 0))
        cr, sr = math.cos(rz), math.sin(rz)
        right = cam.right * cr + cam.up * sr
        up = cam.up * cr - cam.right * sr
        corners = pos + local[:, 0:1] * right + local[:, 1:2] * up
        Rm = np.stack([right, up, -cam.fw], 1)
    else:
        r = _vec(L.get("rot"), t, ctx, (0, 0, 0))
        Rm = rot_matrix(*r)
        if extra_R is not None:
            Rm = Rm @ extra_R
        corners = (local @ Rm.T) + pos
    op = opacity if opacity is not None else _v(L.get("opacity", 1.0), t, ctx, 1.0)
    depth = float(cam.to_cam(pos[None])[0, 2])
    d = {"type": "quad", "levels": levels, "corners": corners, "R": Rm, "depth": depth, "opacity": op,
         "light": L.get("light", True), "fog": L.get("fog", True), "dof": L.get("dof", True)}
    if L.get("tint"):
        d["tint"] = _rgb(L["tint"])
    return d


def slot_texture(R, L):
    P = R.P
    slot = L["slot"]
    cut = P.abspath(f"{P.meta.get('cutouts', 'cutouts')}/{slot}.png")
    if os.path.exists(cut):
        return decorate(load_rgba(cut, L.get("crop")), L), True
    mk = P.abspath(f"cutouts_auto/{slot}_mask.png")
    m = cv2.imread(mk, cv2.IMREAD_GRAYSCALE)
    if m is None:
        m = np.full((600, 400), 255, np.uint8)
    if L.get("crop"):
        c = L["crop"]
        H0, W0 = m.shape
        m = m[int(c[1] * H0):int((c[1] + c[3]) * H0), int(c[0] * W0):int((c[0] + c[2]) * W0)]
    a = (m.astype(np.float32) / 255.0)
    h, w = a.shape
    out = np.zeros((h, w, 4), np.float32)
    base = _rgb(L.get("proxy_color", "#3a4650"))
    yy, xx = np.mgrid[0:h, 0:w]
    hatch = (((xx + yy) // max(4, int(w / 60))) % 2).astype(np.float32)
    out[..., :3] = base * (0.85 + 0.15 * hatch[..., None])
    rim = cv2.morphologyEx((a > 0.5).astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(np.float32)
    yy2, xx2 = np.mgrid[0:h, 0:w]
    rim *= (((xx2 + yy2) // max(6, int(w / 70))) % 2).astype(np.float32)   # dashed
    out[..., :3] = out[..., :3] * (1 - rim[..., None]) + np.array([0.35, 0.95, 1.0], np.float32) * rim[..., None]
    out[..., 3] = a * float(L.get("proxy_alpha", 0.18))
    ov = np.zeros((h, w), np.uint8)
    cv2.putText(ov, f"CUTOUT {slot}", (int(w * 0.04), int(h * 0.05) + 12), cv2.FONT_HERSHEY_SIMPLEX, max(0.4, w / 900), 255,
                max(1, int(w / 500)), cv2.LINE_AA)
    o = ov.astype(np.float32)[..., None] / 255
    out[..., :3] = out[..., :3] * (1 - o) + np.array([0.35, 0.95, 1.0], np.float32) * o
    out[..., 3:4] = np.maximum(out[..., 3:4], np.maximum(o * 0.6, rim[..., None] * 0.45))
    return out, False


_CLOUDS = {}


def depth_cloud(R, L):
    """World-space point cloud from a clean plate + relative inverse depth (0 far .. 1 near)."""
    key = (L["src"], L.get("depth"), str(L.get("fov", 45)), L.get("feather", 0), L.get("near", 2.0), L.get("far", 30.0), tuple(L.get("pos", (0, 0, 0))),
           L.get("yaw", 0), L.get("pitch", 0), L.get("max_points", 900000), tuple(L.get("gmap") or ()), str(L.get("grade")))
    if key in _CLOUDS:
        return _CLOUDS[key]
    rgba = load_rgba(R.P.abspath(L["src"]))
    if L.get("gmap"):
        rgba = gradient_map(rgba, L["gmap"])
    if L.get("grade"):
        # colour grade a colourised plate: multiply tint, lift/gain, desaturate
        gd = L["grade"]
        rgb = rgba[..., :3]
        sat = float(gd.get("saturation", 1.0))
        lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
        rgb = lum[..., None] + (rgb - lum[..., None]) * sat
        rgb = rgb * _rgb(gd.get("tint", "#ffffff")) * float(gd.get("gain", 1.0)) + _rgb(gd.get("lift", "#000000"))
        rgba[..., :3] = np.clip(rgb, 0, 1)
    dpath = R.P.abspath(L.get("depth") or L["src"].rsplit(".", 1)[0] + "_depth.npy")
    d = np.load(dpath).astype(np.float32)
    h, w = rgba.shape[:2]
    d = cv2.resize(d, (w, h), interpolation=cv2.INTER_LINEAR)
    s = max(1.0, math.sqrt(h * w / float(L.get("max_points", 900000))))
    if s > 1.0:
        w2, h2 = int(w / s), int(h / s)
        rgba = cv2.resize(rgba, (w2, h2), interpolation=cv2.INTER_AREA)
        d = cv2.resize(d, (w2, h2), interpolation=cv2.INTER_AREA)
        h, w = h2, w2
    near, far = float(L.get("near", 2.0)), float(L.get("far", 30.0))
    inv = 1.0 / far + d * (1.0 / near - 1.0 / far)
    z = 1.0 / inv
    fov = L.get("fov", 45)
    if fov == "auto" or isinstance(fov, dict):
        # widen the reprojection so the plate covers the camera frame (plus margin) in both directions
        cfg = fov if isinstance(fov, dict) else {}
        cv = math.radians(float(cfg.get("camera_fov", 40)))
        margin = float(cfg.get("margin", 1.18))
        tv = math.tan(cv / 2) * margin
        th = math.tan(cv / 2) * (16 / 9) * margin / (w / h)
        fov = math.degrees(2 * math.atan(max(tv, th)))
        fov = min(fov, float(cfg.get("max", 100)))
    f = (h / 2) / math.tan(math.radians(float(fov)) / 2)
    vv, uu = np.mgrid[0:h, 0:w].astype(np.float32)
    X = (uu - w / 2) / f * z
    Y = -(vv - h / 2) / f * z
    P = np.stack([X, Y, z], -1).reshape(-1, 3).astype(np.float64)
    Rm = rot_matrix(float(L.get("pitch", 0)), float(L.get("yaw", 0)), 0)
    P = P @ Rm.T + np.array(L.get("pos", (0, 0, 0)), np.float64)
    fe = float(L.get("feather", 0))
    al = np.ones((h, w), np.float32)
    if fe > 0:
        def ramp(n):
            k = max(1, int(n * fe))
            r = np.ones(n, np.float32)
            x = np.linspace(0, 1, k)
            r[:k] = x * x * (3 - 2 * x)
            r[n - k:] = np.minimum(r[n - k:], r[:k][::-1])
            return r
        al = ramp(h)[:, None] * ramp(w)[None, :]
    col = np.concatenate([rgba[..., :3].reshape(-1, 3), al.reshape(-1, 1)], 1).astype(np.float32)
    # point footprint in world units (pixel size at its depth) for splat sizing
    foot = (z / f).reshape(-1).astype(np.float32)
    out = (P, col, foot, (w, h))
    _CLOUDS[key] = out
    return out


def splat(cloud, cam, opacity=1.0, fill=3):
    P, col, foot, _ = cloud
    W, H = cam.W, cam.H
    Pc = cam.to_cam(P)
    z = Pc[:, 2]
    ok = z > 0.05
    Pc, c, ft, z = Pc[ok], col[ok], foot[ok], z[ok]
    x = cam.W / 2 + cam.f * Pc[:, 0] / z
    y = cam.H / 2 - cam.f * Pc[:, 1] / z
    inb = (x > -2) & (x < W + 2) & (y > -2) & (y < H + 2)
    x, y, z, c, ft = x[inb], y[inb], z[inb], c[inb], ft[inb]
    if not len(z):
        return None
    order = np.argsort(-z)  # far first, near last (last write wins)
    x, y, z, c, ft = x[order], y[order], z[order], c[order], ft[order]
    img = np.zeros((H, W, 4), np.float32)
    zb = np.full((H, W), np.inf, np.float32)
    rad = np.clip(ft * cam.f / z, 0.5, 6.0)   # projected size of one source pixel
    xi, yi = x.astype(np.int32), y.astype(np.int32)
    for dx, dy, lim in ((0, 0, 0.0), (1, 0, 0.9), (0, 1, 0.9), (1, 1, 1.3), (-1, 0, 1.8), (0, -1, 1.8), (2, 0, 2.6), (0, 2, 2.6)):
        sel = rad > lim
        xs, ys = np.clip(xi[sel] + dx, 0, W - 1), np.clip(yi[sel] + dy, 0, H - 1)
        img[ys, xs] = c[sel]
        zb[ys, xs] = z[sel]
    m = np.isfinite(zb).astype(np.float32)
    # close small holes by propagating neighbours
    for _ in range(fill):
        hole = m < 0.5
        if not hole.any():
            break
        k = np.ones((3, 3), np.float32)
        sm = cv2.filter2D(m, -1, k, borderType=cv2.BORDER_CONSTANT)
        si = cv2.filter2D(img * m[..., None], -1, k, borderType=cv2.BORDER_CONSTANT)
        grow = hole & (sm > 2.5)
        img[grow] = si[grow] / sm[grow][:, None]
        m[grow] = 1
    a = m[..., None] * img[..., 3:4] * opacity
    out = np.zeros((H, W, 4), np.float32)
    out[..., :3] = img[..., :3] * a
    out[..., 3:4] = a
    zmed = float(np.median(z))
    return {"type": "raster", "depth": zmed, "img": out}


def build(L, S, cam, t, ctx, R):
    """Turn one layer spec into drawables."""
    kind = L.get("kind", "image")
    root = R.P.root
    if kind == "depth3d":
        d = splat(depth_cloud(R, L), cam, _v(L.get("opacity", 1.0), t, ctx, 1.0), int(L.get("fill", 3)))
        if d is None:
            return []
        d["dof"] = L.get("dof", False)
        d["fog"] = L.get("fog", True)
        if "sort_depth" in L:
            d["depth"] = float(L["sort_depth"])
        return [d]
    if kind == "image":
        key = ("img", L["src"], tuple(L.get("crop") or ()), L.get("frame"), L.get("feather"), L.get("key_white"), L.get("invert"),
               tuple(L.get("gmap") or ()))
        lv = S.texture(key, lambda: decorate(load_rgba(R.P.abspath(L["src"]), L.get("crop")), L))
        return [quad(lv, L, cam, t, ctx)]
    if kind == "slot":
        key = ("slot", L["slot"], tuple(L.get("crop") or ()), os.path.exists(R.P.abspath(f"cutouts/{L['slot']}.png")))
        lv = S.texture(key, lambda: slot_texture(R, L)[0])
        return [quad(lv, L, cam, t, ctx)]
    if kind == "text":
        key = ("text", L["text"], L.get("size", 160), L.get("color"), str(L.get("stroke")), L.get("vertical"))
        lv = S.texture(key, lambda: text_rgba(L["text"], L.get("size", 160), L.get("color", "#ffffff"), L.get("stroke"),
                                              L.get("vertical", False), L.get("font"), root))
        return [quad(lv, L, cam, t, ctx)]
    if kind == "words":
        words = L["words"]
        n = int(L.get("count", len(words)))
        out = []
        rng = np.random.default_rng(int(L.get("seed", 5)))
        c = _vec(L.get("center"), t, ctx, (0, 0, 8))
        rad = _v(L.get("radius", 3), t, ctx, 3)
        spd = float(L.get("speed", 0.25))
        spread = float(L.get("spread", 1.5))
        op = _v(L.get("opacity", 1.0), t, ctx, 1.0)
        for i in range(n):
            wd = words[i % len(words)]
            key = ("text", wd, L.get("size", 140), L.get("color", "#ffffff"), str(L.get("stroke")), L.get("vertical", True))
            lv = S.texture(key, lambda wd=wd: text_rgba(wd, L.get("size", 140), L.get("color", "#ffffff"), L.get("stroke"),
                                                         L.get("vertical", True), L.get("font"), root))
            if L.get("layout", "ring") == "ring":
                a = 2 * math.pi * i / n + spd * t
                p = c + np.array([math.cos(a) * rad, rng.uniform(-spread, spread) + 0.15 * math.sin(t + i), math.sin(a) * rad])
            else:
                vol = np.array(L.get("volume", [[-4, 4], [-2.5, 2.5], [3, 14]]), np.float64)
                b = rng.uniform(0, 1, 3)
                p = vol[:, 0] + b * (vol[:, 1] - vol[:, 0]) + np.array([0.2 * math.sin(t * 0.7 + i), 0.15 * math.cos(t * 0.5 + i * 2), 0])
            sub = dict(L)
            sub["pos"] = list(p)
            sub["billboard"] = True
            sub["rot"] = [0, 0, rng.uniform(-12, 12)]
            out.append(quad(lv, sub, cam, t, ctx, width=float(L.get("height", 1.2)) * lv[0].shape[1] / lv[0].shape[0], opacity=op))
        return out
    if kind == "glow":
        lv = S.texture(("glow", L.get("color", "#ffffff"), L.get("power", 2.0)), lambda: glow_rgba(256, L.get("color", "#ffffff"), L.get("power", 2.0)))
        sub = dict(L)
        sub["billboard"] = True
        d = quad(lv, sub, cam, t, ctx)
        d["light"] = False
        d["fog"] = False
        d["dof"] = False
        return [d]
    if kind == "particles":
        return particles(L, cam, t, ctx, R)
    if kind == "ribbon":
        top = _vec(L.get("pos"), t, ctx, (0, 3, 6))
        length = _v(L.get("length", 4), t, ctx, 4)
        sway = _v(L.get("sway", 0.15), t, ctx, 0.15)
        n = 40
        s = np.linspace(0, 1, n)
        ph = float(L.get("phase", 0))
        x = sway * np.sin(t * 1.2 + s * 3 + ph) * s ** 1.3
        z = sway * 0.6 * np.cos(t * 0.9 + s * 2 + ph) * s ** 1.5
        P = np.stack([top[0] + x, top[1] - s * length, top[2] + z], 1)
        twist = np.cos(s * float(L.get("twist", 9)) + t * 1.5)
        d = lines_raster([P], [_v(L.get("width", 0.08), t, ctx, 0.08)], L.get("color", "#b8202c"), cam,
                         _v(L.get("opacity", 1.0), t, ctx, 1.0), shade=[twist])
        return [d] if d else []
    if kind == "thread":
        # a cord strung through world points (sagging between them, gently swaying): links stations together
        pts = [np.array(p, np.float64) for p in L["points"]]
        sag = float(L.get("sag", 0.4))
        sway = float(L.get("sway", 0.05))
        poly = []
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            for k in range(16):
                q = k / 16
                p = a + (b - a) * q
                p[1] -= sag * 4 * q * (1 - q)
                p[0] += sway * math.sin(t * 1.1 + i + q * 3) * 4 * q * (1 - q)
                poly.append(p)
        poly.append(pts[-1])
        P = np.array(poly)
        # only the part grown so far
        g = float(np.clip(_v(L.get("grow", 1.0), t, ctx, 1.0), 0, 1))
        n = max(2, int(len(P) * g))
        d = lines_raster([P[:n]], [_v(L.get("width", 0.03), t, ctx, 0.03)], L.get("color", "#9a1c26"), cam,
                         _v(L.get("opacity", 1.0), t, ctx, 1.0))
        return [d] if d else []
    if kind == "strings":
        topy = float(L.get("top", 8))
        polys = []
        for i, tg in enumerate(L.get("targets", [])):
            T = _vec(tg, t, ctx, (0, 0, 6))
            sw = float(L.get("sway", 0.05)) * math.sin(t * 1.3 + i * 1.7)
            P = np.stack([np.linspace(T[0] + sw * 4, T[0], 12), np.linspace(topy, T[1], 12), np.full(12, T[2])], 1)
            polys.append(P)
        d = lines_raster(polys, [float(L.get("width", 0.012))] * len(polys), L.get("color", "#e8e4dc"), cam,
                         _v(L.get("opacity", 0.8), t, ctx, 0.8))
        return [d] if d else []
    if kind == "vines":
        g = float(np.clip(_v(L.get("grow", 1.0), t, ctx, 1.0), 0, 1))
        tw = int(L.get("tex", 1400))
        th = int(tw * float(L.get("aspect", 0.75)))
        vk = (L.get("seed", 1), tw, th, str(L.get("origins")), L.get("branches", 7))
        if vk not in _VINES:
            _VINES[vk] = Vines(int(L.get("seed", 1)), tw, th, L.get("origins", [[0.0, 1.0, -60], [1.0, 1.0, -120]]),
                               int(L.get("branches", 7)), L.get("thorns", True))
        gq = round(g * 240) / 240
        lv = S.texture(("vines", vk, gq, L.get("color")), lambda: _VINES[vk].render(gq, L.get("color", "#090506")))
        return [quad(lv, L, cam, t, ctx)]
    if kind == "shatter":
        key = (L["src"], int(L.get("pieces", 36)), int(L.get("seed", 3)), tuple(L.get("crop") or ()))
        if key not in _SHARDS:
            _SHARDS[key] = shatter_pieces(decorate(load_rgba(R.P.abspath(L["src"]), L.get("crop")), L), *key[1:3])
        pieces, asp = _SHARDS[key]
        e = float(np.clip(_v(L.get("explode", 0), t, ctx, 0), 0, 1.5))
        w = _v(L.get("width", 6), t, ctx, 6)
        spread = float(L.get("spread", 3.0))
        toward = float(L.get("toward", 4.0))
        spin = float(L.get("spin", 160))
        out = []
        base_R = rot_matrix(*_vec(L.get("rot"), t, ctx, (0, 0, 0)))
        for k, (tile, cx, cy, fw, rnd, spd) in enumerate(pieces):
            lv = [tile, cv2.pyrDown(tile)] if min(tile.shape[:2]) > 8 else [tile]
            off = base_R @ np.array([cx * w, cy * w * asp, 0])
            dirv = np.array([cx, cy, 0]) + 0.3 * rnd
            ex = e * spd
            disp = dirv * spread * ex + np.array([0, -0.6 * ex * ex, -toward * ex])
            Rk = rot_matrix(*(rnd * spin * ex))
            sub = dict(L)
            sub["rot"] = None
            out.append(quad(lv, {**sub, "anchor": "center"}, cam, t, ctx, aspect=tile.shape[0] / tile.shape[1],
                            extra_pos=off + disp, extra_R=base_R @ Rk, width=fw * w,
                            opacity=_v(L.get("opacity", 1.0), t, ctx, 1.0) * float(np.clip(1.6 - ex, 0, 1))))
        return out
    if kind == "cage":
        lv = S.texture(("cage", L.get("bars", 9), L.get("color"), L.get("thickness", 0.022), L.get("aspect", 1.33)),
                       lambda: cage_rgba(int(L.get("bars", 9)), 1200, int(1200 * L.get("aspect", 1.33)), L.get("color", "#1a1414"),
                                         float(L.get("thickness", 0.022))))
        return [quad(lv, L, cam, t, ctx)]
    if kind == "blood":
        lv = S.texture(("blood", L.get("seed", 1), L.get("color")), lambda: blood_rgba(int(L.get("seed", 1)), 1024, L.get("color", "#5e070b")))
        return [quad(lv, L, cam, t, ctx)]
    if kind == "clock":
        ang = 2 * math.pi * _v(L.get("speed", 1.0), t, ctx, 1.0) * t
        aq = round(ang / (2 * math.pi) * 360) % (360 * 12)
        lv = S.texture(("clock", aq, L.get("color")), lambda: clock_rgba(math.radians(aq), 700, L.get("color", "#f2ede2")))
        return [quad(lv, L, cam, t, ctx)]
    raise ValueError(f"unknown scene layer kind {kind!r}")
