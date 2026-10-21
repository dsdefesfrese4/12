"""Beat-reactive effects, image warping and transitions.

All pixel-size parameters are in 1080p units and get scaled by `u = H/1080`
so previews at lower resolution look the same.
Frames are float32 HxWx3 in 0..1.
"""
import math

import cv2
import numpy as np

GEOMETRIC = {"shake", "zoom_punch", "rot_punch", "drift_shake"}


def hex_rgb(c, default=(1.0, 1.0, 1.0)):
    if c is None:
        return default
    if isinstance(c, (list, tuple)):
        v = [float(x) for x in c]
        return tuple(x / 255.0 if max(v) > 1 else x for x in v)
    c = str(c).lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def envelope(spec, t, triggers):
    """0..1 strength of an effect at time t."""
    if triggers is None:
        v = 1.0
        if "fade_in" in spec or "fade_out" in spec:
            st, en = spec.get("_start", t), spec.get("_end", t)
            fi, fo = float(spec.get("fade_in", 0)), float(spec.get("fade_out", 0))
            if fi > 0:
                v = min(v, max(0.0, (t - st) / fi))
            if fo > 0:
                v = min(v, max(0.0, (en - t) / fo))
        return v
    decay = float(spec.get("decay", 0.25))
    attack = float(spec.get("attack", 0.0))
    curve = spec.get("curve", "exp")
    best = 0.0
    for tr in triggers:
        dt = t - tr
        if dt < -attack:
            continue
        if dt < 0:
            v = 1 + dt / attack
        elif curve == "linear":
            v = 1 - dt / decay
        elif curve == "hold":
            v = 1.0 if dt < decay else 0.0
        else:
            v = math.exp(-dt / max(1e-4, decay) * 2.3)  # ~10% after `decay`
        best = max(best, v)
    return best


def _rand(seed, t, rate):
    k = int(math.floor(t * rate))
    return np.random.default_rng((hash(seed) & 0xFFFF) * 100003 + k)


def geometry(effects, t, u):
    """Returns (dx, dy, extra_zoom, extra_rot) from geometric effects."""
    dx = dy = rot = 0.0
    zoom = 1.0
    for e in effects:
        typ, env = e["type"], e["_env"]
        if env <= 1e-3:
            continue
        if typ == "shake":
            amp = float(e.get("amount", 18)) * u
            trig = e.get("_trig")
            if trig:
                # damped spring: one directed kick per hit that rings out smoothly (no per-frame jitter)
                past = [x for x in trig if x <= t + 1e-6]
                if past:
                    tr = past[-1]
                    dt = t - tr
                    decay = float(e.get("decay", 0.3))
                    k = math.exp(-dt / max(1e-3, decay) * 2.3)
                    freq = float(e.get("freq", 3.5))
                    ang = (hash((round(tr, 3), str(e.get("seed", 1)))) % 360) * math.pi / 180
                    osc = math.sin(2 * math.pi * freq * dt + math.pi / 2) * k
                    dx += amp * osc * math.cos(ang)
                    dy += amp * osc * math.sin(ang)
                    rot += float(e.get("rot", 0.6)) * osc
            else:
                # continuous shake: smooth band-limited noise
                rate = float(e.get("rate", 6))
                ph = (hash(str(e.get("seed", 1))) % 100) / 7
                dx += amp * env * (math.sin(t * rate * 6.1 + ph) * 0.6 + math.sin(t * rate * 9.7 + ph * 2) * 0.4)
                dy += amp * env * (math.sin(t * rate * 7.3 + ph * 3) * 0.6 + math.sin(t * rate * 11.3 + ph) * 0.4)
        elif typ == "drift_shake":
            amp = float(e.get("amount", 6)) * u * env
            rate = float(e.get("rate", 3))
            ph = (hash(str(e.get("seed", 1))) % 100) / 10
            dx += amp * (math.sin(t * rate * 1.3 + ph) + 0.5 * math.sin(t * rate * 2.9 + ph * 2))
            dy += amp * (math.sin(t * rate * 1.1 + ph * 3) + 0.5 * math.sin(t * rate * 2.3))
        elif typ == "zoom_punch":
            zoom *= 1 + float(e.get("amount", 0.08)) * env
        elif typ == "rot_punch":
            rot += float(e.get("amount", 3)) * env * (1 if e.get("_flip", 0) % 2 == 0 else -1)
    return dx, dy, zoom, rot


def affine(W, H, s, cx, cy, rot_deg, dx, dy):
    """2x3 matrix placing src pixel (cx,cy) at frame centre (+dx,dy), scaled by s, rotated."""
    a = math.radians(rot_deg)
    ca, sa = math.cos(a) * s, math.sin(a) * s
    return np.array([[ca, -sa, W / 2 + dx - (ca * cx - sa * cy)],
                     [sa, ca, H / 2 + dy - (sa * cx + ca * cy)]], dtype=np.float32)


def compose(A, B):
    """A after B, both 2x3."""
    A3 = np.vstack([A, [0, 0, 1]])
    B3 = np.vstack([B, [0, 0, 1]])
    return (A3 @ B3)[:2].astype(np.float32)


def warp_m(img, M, W, H, border="reflect", s=1.0):
    bm = cv2.BORDER_REFLECT_101 if border == "reflect" else cv2.BORDER_CONSTANT
    interp = cv2.INTER_LINEAR if s >= 0.75 else cv2.INTER_AREA
    return cv2.warpAffine(img, M, (W, H), flags=interp, borderMode=bm, borderValue=0)


def warp(img, W, H, s, cx, cy, rot_deg, dx, dy, border="reflect"):
    return warp_m(img, affine(W, H, s, cx, cy, rot_deg, dx, dy), W, H, border, s)


def cover_fix(W, H, rot_deg):
    """Extra zoom so a rotated frame never shows the image edge."""
    a = abs(math.radians(rot_deg))
    c, s = math.cos(a), math.sin(a)
    return max((W * c + H * s) / W, (W * s + H * c) / H)


def clamp_center(cx, cy, s, iw, ih, W, H):
    hw, hh = W / 2 / s, H / 2 / s
    cx = iw / 2 if iw <= 2 * hw else min(max(cx, hw), iw - hw)
    cy = ih / 2 if ih <= 2 * hh else min(max(cy, hh), ih - hh)
    return cx, cy


# ---------------------------------------------------------------- pixel effects

class FxCache:
    """Per-process cache for expensive overlays (speed lines, grain, vignette)."""

    def __init__(self):
        self.d = {}

    def get(self, key, fn):
        if key not in self.d:
            self.d[key] = fn()
        return self.d[key]


CACHE = FxCache()


def _speed_lines(W, H, count, inner, center, seed, thickness):
    rng = np.random.default_rng(seed)
    m = np.zeros((H, W), np.uint8)
    cx, cy = center[0] * W, center[1] * H
    R = math.hypot(W, H)
    for _ in range(count):
        ang = rng.uniform(0, 2 * math.pi)
        width = rng.uniform(0.15, 1.0) * thickness / R * 3
        r0 = R * inner * rng.uniform(0.8, 1.35) / 2
        pts = [(cx + math.cos(ang) * r0, cy + math.sin(ang) * r0),
               (cx + math.cos(ang - width) * R, cy + math.sin(ang - width) * R),
               (cx + math.cos(ang + width) * R, cy + math.sin(ang + width) * R)]
        cv2.fillPoly(m, [np.array(pts, np.int32)], 255, lineType=cv2.LINE_AA)
    return (m.astype(np.float32) / 255.0)[..., None]


def _vignette(W, H, amount, softness):
    y, x = np.ogrid[0:H, 0:W]
    d = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
    v = 1 - amount * np.clip((d - (1 - softness)) / softness, 0, 1) ** 2
    return v.astype(np.float32)[..., None]


def _grain_bank(W, H, n=6):
    rng = np.random.default_rng(7)
    return [rng.normal(0, 1, (H, W, 1)).astype(np.float32) for _ in range(n)]


def zoom_blur(f, amount, samples=6, center=(0.5, 0.5)):
    H, W = f.shape[:2]
    acc = f.copy()
    cx, cy = center[0] * W, center[1] * H
    for i in range(1, samples):
        s = 1 + amount * i / (samples - 1)
        M = np.array([[s, 0, cx - s * cx], [0, s, cy - s * cy]], np.float32)
        acc += cv2.warpAffine(f, M, (W, H), borderMode=cv2.BORDER_REFLECT_101)
    return acc / samples


def apply_pixel(f, e, t, u, frame_idx):
    typ, env = e["type"], e["_env"]
    if env <= 1e-3 or typ in GEOMETRIC:
        return f
    H, W = f.shape[:2]
    if typ == "flash":
        col = np.array(hex_rgb(e.get("color", "#ffffff")), np.float32)
        a = float(e.get("amount", 0.85)) * env
        if e.get("mode", "normal") == "add":
            return np.minimum(1, f + col * a)
        return f * (1 - a) + col * a
    if typ == "rgb_split":
        o = max(1, int(round(float(e.get("amount", 10)) * u * env)))
        out = f.copy()
        out[..., 0] = np.roll(f[..., 0], -o, axis=1)
        out[..., 2] = np.roll(f[..., 2], o, axis=1)
        if e.get("vertical"):
            out[..., 0] = np.roll(out[..., 0], o // 2, axis=0)
        return out
    if typ == "zoom_blur":
        return zoom_blur(f, float(e.get("amount", 0.12)) * env, int(e.get("samples", 6)),
                         e.get("center", (0.5, 0.5)))
    if typ == "motion_blur":
        k = int(float(e.get("amount", 40)) * u * env) | 1
        if k < 3:
            return f
        return cv2.blur(f, (k, 1) if e.get("dir", "h") == "h" else (1, k))
    if typ == "blur":
        r = float(e.get("amount", 8)) * u * env
        if r < 0.5:
            return f
        return cv2.GaussianBlur(f, (0, 0), r)
    if typ == "invert":
        if env >= float(e.get("threshold", 0.5)):
            return 1 - f
        return f
    if typ == "grade":
        out = f
        b = float(e.get("brightness", 0)) * env
        c = 1 + (float(e.get("contrast", 1)) - 1) * env
        sat = 1 + (float(e.get("saturation", 1)) - 1) * env
        out = (out - 0.5) * c + 0.5 + b
        if sat != 1:
            g = out.mean(axis=2, keepdims=True)
            out = g + (out - g) * sat
        if "tint" in e:
            tint = np.array(hex_rgb(e["tint"]), np.float32)
            out = out * (1 - 0.5 * env * float(e.get("tint_amount", 0.4))) + \
                tint * 0.5 * env * float(e.get("tint_amount", 0.4))
        if "gamma" in e:
            out = np.clip(out, 0, 1) ** (1 / (1 + (float(e["gamma"]) - 1) * env))
        return np.clip(out, 0, 1)
    if typ == "mono":
        g = (f @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
        a = float(e.get("amount", 1)) * env
        return f * (1 - a) + g * a
    if typ == "threshold":
        g = (f @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
        th = float(e.get("level", 0.5))
        bw = np.clip((g - th) * 12 + 0.5, 0, 1)
        a = env * float(e.get("amount", 1))
        return f * (1 - a) + np.repeat(bw, 3, axis=2) * a
    if typ == "glow":
        small = cv2.resize(f, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
        th = float(e.get("threshold", 0.6))
        bright = np.clip((small - th) / (1 - th), 0, 1)
        bright = cv2.GaussianBlur(bright, (0, 0), float(e.get("radius", 12)) * u / 4 * 4)
        bright = cv2.resize(bright, (W, H), interpolation=cv2.INTER_LINEAR)
        if "color" in e:
            bright = bright.mean(axis=2, keepdims=True) * np.array(hex_rgb(e["color"]), np.float32)
        return np.minimum(1, f + bright * float(e.get("amount", 0.6)) * env)
    if typ == "speed_lines":
        variants = int(e.get("variants", 4))
        rate = float(e.get("rate", 15))
        k = int(t * rate) % variants
        center = tuple(e.get("center", (0.5, 0.5)))
        m = CACHE.get(("sl", W, H, int(e.get("count", 140)), float(e.get("inner", 0.45)),
                       center, k, float(e.get("thickness", 6))),
                      lambda: _speed_lines(W, H, int(e.get("count", 140)), float(e.get("inner", 0.45)),
                                           center, 100 + k, float(e.get("thickness", 6)) * u))
        col = np.array(hex_rgb(e.get("color", "#ffffff")), np.float32)
        a = m * float(e.get("opacity", 0.9)) * env
        return f * (1 - a) + col * a
    if typ == "vignette":
        v = CACHE.get(("vig", W, H, float(e.get("amount", 0.5)), float(e.get("softness", 0.6))),
                      lambda: _vignette(W, H, float(e.get("amount", 0.5)), float(e.get("softness", 0.6))))
        return f * (1 - (1 - v) * env)
    if typ == "grain":
        bank = CACHE.get(("grain", W, H), lambda: _grain_bank(W, H))
        n = bank[frame_idx % len(bank)]
        return np.clip(f + n * float(e.get("amount", 0.04)) * env, 0, 1)
    if typ == "letterbox":
        ratio = float(e.get("ratio", 2.39))
        bar = int(round((H - W / ratio) / 2 * env))
        if bar > 0:
            f = f.copy()
            col = np.array(hex_rgb(e.get("color", "#000000")), np.float32)
            f[:bar] = col
            f[H - bar:] = col
        return f
    if typ == "glitch":
        r = _rand(e.get("seed", 3), t, float(e.get("rate", 20)))
        out = f.copy()
        n = int(e.get("slices", 8))
        amt = float(e.get("amount", 60)) * u * env
        for _ in range(n):
            y0 = int(r.uniform(0, H))
            h = int(r.uniform(4, 60) * u)
            out[y0:y0 + h] = np.roll(out[y0:y0 + h], int(r.uniform(-amt, amt)), axis=1)
        o = int(amt / 4)
        if o:
            out[..., 0] = np.roll(out[..., 0], o, axis=1)
            out[..., 2] = np.roll(out[..., 2], -o, axis=1)
        return out
    if typ == "strobe":
        rate = float(e.get("rate", 12))
        if int(t * rate) % 2 == 1:
            col = np.array(hex_rgb(e.get("color", "#000000")), np.float32)
            return f * (1 - env) + col * env
        return f
    if typ == "duotone":
        # luminance -> shadow colour .. highlight colour (manga pages tinted per section)
        g = (f @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
        g = np.clip((g - 0.5) * float(e.get("contrast", 1.0)) + 0.5, 0, 1)
        lo = np.array(hex_rgb(e.get("shadow", "#0d0a14")), np.float32)
        hi = np.array(hex_rgb(e.get("highlight", "#f2ece0")), np.float32)
        mid = e.get("mid")
        if mid:
            m = np.array(hex_rgb(mid), np.float32)
            d = np.where(g < 0.5, lo + (m - lo) * (g * 2), m + (hi - m) * (g * 2 - 1))
        else:
            d = lo + (hi - lo) * g
        a = float(e.get("amount", 1.0)) * env
        return f * (1 - a) + d * a
    if typ == "particles":
        return _particles(f, e, t, u, env)
    if typ == "flicker":
        # projector-style luminance flicker + occasional dust/scratch specks
        r = _rand(e.get("seed", 9), t, float(e.get("rate", 12)))
        amt = float(e.get("amount", 0.04)) * env
        out = f * (1 - amt * r.uniform(0, 1))
        if e.get("specks", True) and r.uniform() < 0.35:
            m = np.zeros((H, W), np.float32)
            for _ in range(int(r.integers(1, 5))):
                x, y = int(r.uniform(0, W)), int(r.uniform(0, H))
                if r.uniform() < 0.3:
                    cv2.line(m, (x, 0), (x + int(r.uniform(-8, 8) * u), H), float(r.uniform(0.2, 0.5)), max(1, int(u)), cv2.LINE_AA)
                else:
                    cv2.circle(m, (x, y), max(1, int(r.uniform(1, 3) * u)), float(r.uniform(0.3, 0.8)), -1, cv2.LINE_AA)
            dark = r.uniform() < 0.6
            out = out * (1 - m[..., None]) + (0.0 if dark else 0.9) * m[..., None]
        return out
    if typ == "light_sweep":
        # a soft diagonal band of light crossing the frame once per trigger / per `period`
        period = float(e.get("period", 2.5))
        ph = ((t - e.get("_start", 0)) / period) % 1.0 if e.get("_trig") is None else 1 - env
        ang = math.radians(float(e.get("angle", 25)))
        yy, xx = np.mgrid[0:H:4, 0:W:4].astype(np.float32)
        d = (xx * math.cos(ang) + yy * math.sin(ang)) / (W * math.cos(ang) + H * math.sin(ang))
        width = float(e.get("width", 0.12))
        band = np.exp(-((d - (ph * 1.6 - 0.3)) / width) ** 2)
        band = cv2.resize(band, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
        col = np.array(hex_rgb(e.get("color", "#fff6e0")), np.float32)
        strength = float(e.get("amount", 0.35)) * (env if e.get("_trig") is not None else 1.0)
        return np.minimum(1, f + band * col * strength)
    if typ == "leak":
        # warm light leak blob drifting from a corner
        cx = float(e.get("x", 0.85)) + 0.05 * math.sin(t * 0.7)
        cy = float(e.get("y", 0.15)) + 0.05 * math.cos(t * 0.5)
        yy, xx = np.mgrid[0:H:4, 0:W:4].astype(np.float32)
        r = float(e.get("radius", 0.45)) * max(W, H)
        m = np.exp(-(((xx - cx * W) ** 2 + (yy - cy * H) ** 2) / (r * r)))
        m = cv2.resize(m, (W, H))[..., None]
        col = np.array(hex_rgb(e.get("color", "#ff9a4a")), np.float32)
        a = float(e.get("amount", 0.35)) * env
        return 1 - (1 - f) * (1 - m * col * a)  # screen
    if typ == "scanlines":
        f = f.copy()
        step = max(2, int(4 * u))
        f[::step] *= 1 - 0.35 * float(e.get("amount", 1)) * env
        return f
    raise ValueError(f"unknown effect type {typ!r}")


def _particles(f, e, t, u, env):
    """Procedural particles: dust (bokeh drifting up), stars (twinkle), rain, snow, ash, petals."""
    H, W = f.shape[:2]
    kind = e.get("kind", "dust")
    n = int(e.get("count", {"dust": 70, "stars": 160, "rain": 220, "snow": 120, "ash": 90}.get(kind, 80)))
    rng = np.random.default_rng(int(e.get("seed", 11)))
    x0 = rng.uniform(0, 1, n)
    y0 = rng.uniform(0, 1, n)
    sz = rng.uniform(0.4, 1.0, n)
    ph = rng.uniform(0, 2 * math.pi, n)
    sp = float(e.get("speed", 1.0))
    col = np.array(hex_rgb(e.get("color", {"rain": "#c8d4e8", "ash": "#2a2a2a"}.get(kind, "#fff8e8"))), np.float32)
    layer = np.zeros((H, W), np.float32)
    tt = t * sp
    if kind == "rain":
        L = 60 * u
        ang = math.radians(float(e.get("angle", 12)))
        xs = ((x0 + tt * 0.25 * math.sin(ang) * sz) % 1.0) * W
        ys = ((y0 + tt * 2.2 * sz) % 1.0) * H
        for x, y, s_ in zip(xs, ys, sz):
            cv2.line(layer, (int(x), int(y)), (int(x - L * s_ * math.sin(ang)), int(y - L * s_)), float(0.5 + 0.5 * s_),
                     max(1, int(1.5 * u)), cv2.LINE_AA)
        a = cv2.GaussianBlur(layer, (0, 0), 0.8 * u)
    else:
        if kind == "stars":
            xs, ys = x0 * W, y0 * H
            br = 0.5 + 0.5 * np.sin(tt * 3 * sz + ph)
            rad = 1.2 * u * (0.5 + sz)
        elif kind in ("snow", "ash"):
            xs = ((x0 + 0.03 * np.sin(tt * 0.8 + ph)) % 1.0) * W
            ys = ((y0 + tt * 0.08 * (0.5 + sz)) % 1.0) * H
            br = np.ones(n)
            rad = (2.5 if kind == "snow" else 1.8) * u * (0.5 + sz)
        else:  # dust: slow upward drift with bokeh size variety
            xs = ((x0 + 0.02 * np.sin(tt * 0.5 + ph)) % 1.0) * W
            ys = ((y0 - tt * 0.03 * (0.4 + sz)) % 1.0) * H
            br = 0.4 + 0.6 * (0.5 + 0.5 * np.sin(tt * 1.3 + ph))
            rad = 3.0 * u * (0.3 + sz * 1.6)
        rad = np.broadcast_to(rad, (n,))
        for x, y, r, b in zip(xs, ys, rad, br):
            cv2.circle(layer, (int(x), int(y)), max(1, int(r)), float(b), -1, cv2.LINE_AA)
        a = cv2.GaussianBlur(layer, (0, 0), float(e.get("blur", 1.2 if kind != "dust" else 2.5)) * u)
        if kind == "stars":
            a = np.maximum(a, cv2.GaussianBlur(layer, (0, 0), 4 * u) * 0.6)
    a = np.clip(a * float(e.get("opacity", 0.8)) * env, 0, 1)[..., None]
    if kind == "ash":
        return f * (1 - a) + col * a
    return np.minimum(1, f + a * col)


# ---------------------------------------------------------------- transitions

TRANSITIONS = {"cut", "fade", "flash", "black", "whip_left", "whip_right", "whip_up", "whip_down",
               "slide_left", "slide_right", "zoom", "glitch", "wipe_left", "wipe_right", "circle"}


def transition(kind, prev, nxt, q, spec, u):
    """Blend prev->next at transition progress q (0..1, cut at 0.5)."""
    H, W = prev.shape[:2]
    if kind == "fade":
        a = _smooth(q)
        return prev * (1 - a) + nxt * a
    if kind in ("flash", "black"):
        col = np.array(hex_rgb(spec.get("color", "#ffffff" if kind == "flash" else "#000000")), np.float32)
        base = prev if q < 0.5 else nxt
        a = 1 - abs(q - 0.5) * 2
        a = a ** (0.6 if kind == "flash" else 1.0)
        return base * (1 - a) + col * a
    if kind.startswith("whip_") or kind.startswith("slide_"):
        d = kind.split("_")[1]
        e = _smooth(q)
        horiz = d in ("left", "right")
        size = W if horiz else H
        sign = -1 if d in ("left", "up") else 1
        off = int(round(e * size)) * sign
        both = np.concatenate([prev, nxt], axis=1 if horiz else 0)
        # prev occupies [0,size), next [size, 2size) along the axis; move window
        start = int(round(e * size))
        if sign < 0:
            win = both[:, start:start + W] if horiz else both[start:start + H]
        else:
            both = np.concatenate([nxt, prev], axis=1 if horiz else 0)
            st = size - start
            win = both[:, st:st + W] if horiz else both[st:st + H]
        del off
        if kind.startswith("whip_"):
            k = int(math.sin(math.pi * q) * float(spec.get("blur", 120)) * u) | 1
            if k >= 3:
                win = cv2.blur(win, (k, 1) if horiz else (1, k))
        return win
    if kind == "zoom":
        if q < 0.5:
            p = q * 2
            s = 1 + p * p * 1.5
            M = np.array([[s, 0, W / 2 - s * W / 2], [0, s, H / 2 - s * H / 2]], np.float32)
            img = cv2.warpAffine(prev, M, (W, H), borderMode=cv2.BORDER_REFLECT_101)
            img = zoom_blur(img, 0.25 * p)
        else:
            p = (1 - q) * 2
            s = 1 + p * p * 1.5
            M = np.array([[s, 0, W / 2 - s * W / 2], [0, s, H / 2 - s * H / 2]], np.float32)
            img = cv2.warpAffine(nxt, M, (W, H), borderMode=cv2.BORDER_REFLECT_101)
            img = zoom_blur(img, 0.25 * p)
        a = max(0.0, 1 - abs(q - 0.5) * 5) * 0.8
        return img * (1 - a) + a
    if kind == "glitch":
        base = prev if q < 0.5 else nxt
        e = {"type": "glitch", "_env": 1 - abs(q - 0.5) * 2, "amount": 120, "slices": 14,
             "seed": int(q * 1000)}
        return apply_pixel(base, e, q * 10, u, 0)
    if kind in ("wipe_left", "wipe_right"):
        e = _smooth(q)
        x = int(e * W)
        out = prev.copy()
        if kind == "wipe_left":
            out[:, W - x:] = nxt[:, W - x:]
        else:
            out[:, :x] = nxt[:, :x]
        return out
    if kind == "circle":
        e = _smooth(q)
        y, x = np.ogrid[0:H, 0:W]
        r = e * math.hypot(W, H) / 2
        m = (((x - W / 2) ** 2 + (y - H / 2) ** 2) <= r * r).astype(np.float32)[..., None]
        m = cv2.GaussianBlur(m, (0, 0), 3 * u)[..., None] if m.ndim == 3 else m
        return prev * (1 - m) + nxt * m
    return nxt if q >= 0.5 else prev


def _smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)
