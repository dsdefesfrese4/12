"""Puppet-pin deformation (like AE Puppet / Live2D-lite) and generic animatable values.

A layer can carry:
  puppet:
    step: 3            # hold each pose N frames (anime "on threes"); 1 = every frame
    pins:
      - center: [0.5, 0.42]   # normalised layer coords of the part (e.g. head)
        radius: 0.45          # influence radius, fraction of layer height
        hard: 0.55            # inner fraction that moves rigidly
        pivot: [0.5, 0.9]     # rotation/scale pivot (e.g. neck)
        rotate: <value>       # degrees
        move: [<value>, <value>]   # fraction of layer height
        scale: <value>        # 1 = unchanged
        lag: 0.06             # seconds of delay (secondary motion, hair)

<value> is any of
  3.0                                   constant
  {from: -4, to: 2, ease: ease_out, start: b10, end: b14}   tween (defaults to the shot span)
  {keys: [[b10, 0], [b12, -3], [b14, 1]], ease: ease_in_out}  keyframes at song times
  {wave: 1.5, period: 4b, phase: 0.25}  sine (period in s or beats "4b")
  {pulse: 2, on: beat, decay: 0.2, every: 1}  impulse on beats
  [<value>, <value>, ...]               sum
"""
import math

import cv2
import numpy as np

from . import camera as cam_mod
from . import effects as fx


class Ctx:
    def __init__(self, project, start, end):
        self.P, self.start, self.end = project, start, end

    def T(self, x):
        return self.P.T(x)

    def period(self, p):
        if isinstance(p, str) and p.endswith("b"):
            return float(p[:-1]) * self.P.T.beat_len
        return float(p)


def value(v, t, ctx, default=0.0):
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, list):
        return sum(value(x, t, ctx, 0.0) for x in v)
    if "keys" in v:
        keys = [(ctx.T(k[0]), float(k[1])) for k in v["keys"]]
        keys.sort()
        if t <= keys[0][0]:
            return keys[0][1]
        for (ta, va), (tb, vb) in zip(keys, keys[1:]):
            if t <= tb:
                q = cam_mod.ease(v.get("ease", "ease_in_out"), (t - ta) / max(1e-6, tb - ta))
                return va + (vb - va) * q
        return keys[-1][1]
    if "from" in v or "to" in v:
        a, b = float(v.get("from", 0)), float(v.get("to", 0))
        st = ctx.T(v["start"]) if "start" in v else ctx.start
        en = ctx.T(v["end"]) if "end" in v else ctx.end
        q = cam_mod.ease(v.get("ease", "ease_in_out"), (t - st) / max(1e-6, en - st))
        return a + (b - a) * q
    if "wave" in v:
        per = ctx.period(v.get("period", 2.0))
        ph = float(v.get("phase", 0))
        amp = float(v["wave"])
        return amp * math.sin(2 * math.pi * ((t - ctx.start) / per + ph))
    if "pulse" in v:
        spec = dict(v)
        trig = ctx.P.triggers(spec, ctx.start, ctx.end)
        return float(v["pulse"]) * fx.envelope(spec, t, trig or [])
    raise ValueError(f"cannot evaluate value {v!r}")


def deform(img, alpha, spec, t, ctx):
    """Apply puppet pins to a layer image (float32 HxWxC) and its alpha (HxW or None)."""
    pins = spec.get("pins") or []
    if not pins:
        return img, alpha
    H, W = img.shape[:2]
    g = int(spec.get("grid", 8))
    gh, gw = max(2, H // g), max(2, W // g)
    ys, xs = np.mgrid[0:gh, 0:gw].astype(np.float32)
    px = xs * (W - 1) / (gw - 1)
    py = ys * (H - 1) / (gh - 1)
    dxs = np.zeros_like(px)
    dys = np.zeros_like(py)
    any_motion = False
    for pin in pins:
        tt = t - float(pin.get("lag", 0))
        rot = value(pin.get("rotate"), tt, ctx, 0.0)
        mv = pin.get("move") or [0, 0]
        mx = value(mv[0], tt, ctx, 0.0) * H
        my = value(mv[1], tt, ctx, 0.0) * H
        sc = value(pin.get("scale"), tt, ctx, 1.0)
        if abs(rot) < 1e-3 and abs(mx) < 1e-2 and abs(my) < 1e-2 and abs(sc - 1) < 1e-4:
            continue
        any_motion = True
        cx, cy = pin["center"][0] * W, pin["center"][1] * H
        pv = pin.get("pivot", pin["center"])
        pvx, pvy = pv[0] * W, pv[1] * H
        R = float(pin.get("radius", 0.3)) * H
        hard = float(pin.get("hard", 0.5))
        d = np.sqrt((px - cx) ** 2 + (py - cy) ** 2) / R
        w = np.clip((1 - d) / max(1e-3, 1 - hard), 0, 1)
        w = w * w * (3 - 2 * w)
        # inverse transform: where does output pixel p come from?
        a = math.radians(-rot)
        ca, sa = math.cos(a) / sc, math.sin(a) / sc
        qx, qy = px - mx - pvx, py - my - pvy
        sx = pvx + ca * qx - sa * qy
        sy = pvy + sa * qx + ca * qy
        dxs += w * (sx - px)
        dys += w * (sy - py)
    if not any_motion:
        return img, alpha
    mapx = cv2.resize(px + dxs, (W, H), interpolation=cv2.INTER_LINEAR)
    mapy = cv2.resize(py + dys, (W, H), interpolation=cv2.INTER_LINEAR)
    out = cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    if alpha is not None:
        a2 = alpha[..., 0] if alpha.ndim == 3 else alpha
        alpha = cv2.remap(a2, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                          borderValue=0)[..., None]
    return out, alpha
