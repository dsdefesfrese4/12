"""Layered character rig: bones, pseudo-3D head turn, blink, gaze, mouth, breathing, hair physics.

A rig is a folder with rig.yaml + part PNGs (RGBA, full canvas size or cropped with `offset`).

rig.yaml
  canvas: [W, H]
  bones:                      # pivots in normalised canvas coords
    body: {pivot: [0.5, 1.0]}
    neck: {parent: body, pivot: [0.5, 0.80]}
    head: {parent: neck, pivot: [0.5, 0.74]}
  head_sphere: {center: [0.5, 0.45], radius: [0.32, 0.36]}   # face ellipse used for the turn warp
  parts:                      # back to front
    - {name: hair_back, image: hair_back.png, bone: head, depth: -0.5, hair: {root: 0.05, length: 0.6}}
    - {name: body, image: body.png, bone: body, depth: -0.3, breathe: 1}
    - {name: neck, image: neck.png, bone: neck, depth: -0.2}
    - {name: face, image: face.png, bone: head, depth: 0.0}
    - {name: eye_L, kind: eye, bone: head, depth: 0.15, side: L,
       white: eyeL_white.png, iris: eyeL_iris.png, lash: eyeL_lash.png, low: eyeL_low.png,
       hilite: eyeL_hi.png}
    - {name: mouth, kind: mouth, bone: head, depth: 0.12, inner: mouth_inner.png,
       upper: mouth_up.png, lower: mouth_low.png}
    - {name: bangs, image: bangs.png, bone: head, depth: 0.3, hair: {root: 0.0, length: 0.35}}

Parameters (all animatable with the same value syntax as puppet pins):
  head_x  -1..1  turn left/right (pseudo 3D, parts slide by depth + spherical bulge)
  head_y  -1..1  look up/down
  head_roll      degrees, rotates the head bone
  neck_roll      degrees
  body_roll      degrees
  body_y         fraction of canvas height (bob)
  breath  0..1   chest/shoulder rise
  eye_open, eye_open_L, eye_open_R   0 closed .. 1 open (1.1 = wide)
  eye_x, eye_y   -1..1 gaze
  hilite         0..1 extra shimmer strength on eye highlights
  mouth_open     0 closed .. 1 as drawn .. 1.4 wider
  hair_wind      extra sway (degrees)
Physics: hair parts lag behind head motion with a damped spring (`physics:` in rig.yaml
  {stiffness: 60, damping: 7, gain: 1.0}).
"""
import math
import os

import cv2
import numpy as np
import yaml

PARAMS = ["head_x", "head_y", "head_roll", "neck_roll", "body_roll", "body_y", "breath",
          "eye_open", "eye_open_L", "eye_open_R", "eye_x", "eye_y", "hilite", "mouth_open", "hair_wind"]
DEFAULTS = {"eye_open": 1.0, "mouth_open": 1.0}


def _load(path):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise FileNotFoundError(path)
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGRA)
    if im.shape[2] == 3:
        im = cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
    rgba = cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA).astype(np.float32) / 255.0
    return rgba


class Sprite:
    """A part image cropped to its alpha bbox, remembering where it sits on the canvas."""

    def __init__(self, rgba, offset=(0, 0)):
        a = rgba[..., 3]
        ys, xs = np.nonzero(a > 0.004)
        if len(xs) == 0:
            self.img = rgba[:1, :1] * 0
            self.x0 = self.y0 = 0
        else:
            pad = 24
            x0, x1 = max(0, xs.min() - pad), min(rgba.shape[1], xs.max() + 1 + pad)
            y0, y1 = max(0, ys.min() - pad), min(rgba.shape[0], ys.max() + 1 + pad)
            self.img = np.ascontiguousarray(rgba[y0:y1, x0:x1])
            self.x0, self.y0 = x0 + offset[0], y0 + offset[1]
        self.h, self.w = self.img.shape[:2]


def _rot(deg, px, py):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, px - c * px + s * py], [s, c, py - s * px - c * py], [0, 0, 1]], np.float64)


def _tr(dx, dy):
    return np.array([[1, 0, dx], [0, 1, dy], [0, 0, 1]], np.float64)


def _sc(sx, sy, px, py):
    return np.array([[sx, 0, px - sx * px], [0, sy, py - sy * py], [0, 0, 1]], np.float64)


class Rig:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.root = os.path.dirname(self.path)
        with open(self.path, encoding="utf-8") as f:
            self.spec = yaml.safe_load(f)
        self.W, self.H = self.spec["canvas"]
        self.bones = self.spec.get("bones", {})
        hs = self.spec.get("head_sphere", {"center": [0.5, 0.45], "radius": [0.3, 0.35]})
        self.sph_c = (hs["center"][0] * self.W, hs["center"][1] * self.H)
        self.sph_r = (hs["radius"][0] * self.W, hs["radius"][1] * self.H)
        self.turn_px = float(self.spec.get("turn", 0.045)) * self.H
        self.parts = []
        for p in self.spec["parts"]:
            p = dict(p)
            kind = p.get("kind", "image")
            if kind == "image":
                p["_spr"] = Sprite(self._img(p["image"]), p.get("offset", (0, 0)))
            elif kind == "eye":
                for k in ("white", "iris", "lash", "low", "hilite", "skin"):
                    if p.get(k):
                        p["_" + k] = Sprite(self._img(p[k]))
                p["_geom"] = self._eye_geom(p)
            elif kind == "mouth":
                for k in ("inner", "upper", "lower"):
                    if p.get(k):
                        p["_" + k] = Sprite(self._img(p[k]))
            self.parts.append(p)
        self.phys = self.spec.get("physics", {"stiffness": 55.0, "damping": 6.0, "gain": 1.0})
        self._phys_cache = None

    def _img(self, rel):
        full = rel if os.path.isabs(rel) else os.path.join(self.root, rel)
        im = _load(full)
        if im.shape[1] != self.W or im.shape[0] != self.H:
            raise ValueError(f"{rel}: part images must be canvas size {self.W}x{self.H}, got {im.shape[1]}x{im.shape[0]}")
        return im

    # ---------------------------------------------------------------- geometry helpers
    def _eye_geom(self, p):
        """Per-column y of the upper lash's lower edge and the lower lash's upper edge."""
        lash = p["_lash"]
        a = lash.img[..., 3] > 0.3
        cols = {}
        for x in range(lash.w):
            ys = np.nonzero(a[:, x])[0]
            if len(ys):
                cols[x + lash.x0] = ys.max() + lash.y0
        low_y = None
        if p.get("_low"):
            lw = p["_low"]
            ys, xs = np.nonzero(lw.img[..., 3] > 0.3)
            if len(ys):
                low_y = float(np.median(ys)) + lw.y0
        if low_y is None:
            wh = p["_white"]
            ys, _ = np.nonzero(wh.img[..., 3] > 0.3)
            low_y = ys.max() + wh.y0
        up_y = float(np.median(list(cols.values()))) if cols else low_y - 40
        return {"cols": cols, "low_y": low_y, "up_y": up_y, "h": max(8.0, low_y - up_y)}

    def bone_matrix(self, name, P):
        """Canvas-space 3x3 matrix of a bone, including parents."""
        if name is None or name not in self.bones:
            return np.eye(3)
        b = self.bones[name]
        px, py = b["pivot"][0] * self.W, b["pivot"][1] * self.H
        local = np.eye(3)
        if name == "body":
            local = _tr(0, P["body_y"] * self.H) @ _rot(P["body_roll"], px, py)
        elif name == "neck":
            local = _rot(P["neck_roll"], px, py) @ _tr(0, -P["breath"] * 0.006 * self.H)
        elif name == "head":
            # nodding (head_y) also tips the head slightly around the pivot
            local = _rot(P["head_roll"] + P["head_x"] * 1.5, px, py)
        else:
            local = _rot(P.get(name + "_roll", 0.0), px, py)
        parent = b.get("parent")
        return self.bone_matrix(parent, P) @ local if parent else local

    def _turn_field(self, spr, depth, P, extra_dx=None, extra_dy=None):
        """Displacement (dx, dy) on a sprite grid for the pseudo-3D head turn."""
        hx, hy = P["head_x"], P["head_y"]
        if abs(hx) < 1e-4 and abs(hy) < 1e-4 and extra_dx is None:
            return None
        g = 6
        gh, gw = max(2, spr.h // g + 1), max(2, spr.w // g + 1)
        ys, xs = np.mgrid[0:gh, 0:gw].astype(np.float32)
        X = spr.x0 + xs * (spr.w - 1) / (gw - 1)
        Y = spr.y0 + ys * (spr.h - 1) / (gh - 1)
        cx, cy = self.sph_c
        rx, ry = self.sph_r
        nx, ny = (X - cx) / rx, (Y - cy) / ry
        bulge = np.clip(1 - nx * nx - ny * ny, 0, 1)
        bulge = np.sqrt(bulge)  # sphere surface height
        # parts in front (depth>0) ride on the sphere; back parts move opposite
        k = self.turn_px
        dx = hx * k * (depth + 0.6 * bulge * (1 if depth >= 0 else 0.3))
        dy = hy * k * (depth + 0.6 * bulge * (1 if depth >= 0 else 0.3))
        # foreshortening: compress the side turning away
        dx += -hx * 0.08 * (X - cx) * np.abs(nx).clip(0, 1) * np.sign(nx) * np.sign(hx) * (nx * hx > 0)
        dy += -hy * 0.06 * (Y - cy) * np.abs(ny).clip(0, 1) * np.sign(ny) * np.sign(hy) * (ny * hy > 0)
        if extra_dx is not None:
            dx = dx + extra_dx(X, Y)
        if extra_dy is not None:
            dy = dy + extra_dy(X, Y)
        return X, Y, dx.astype(np.float32), dy.astype(np.float32)

    def _deform_sprite(self, spr, field):
        """Forward displacement field -> backward remap (first-order inverse)."""
        if field is None:
            return spr.img
        X, Y, dx, dy = field
        mapx = cv2.resize((X - dx - spr.x0).astype(np.float32), (spr.w, spr.h), interpolation=cv2.INTER_LINEAR)
        mapy = cv2.resize((Y - dy - spr.y0).astype(np.float32), (spr.w, spr.h), interpolation=cv2.INTER_LINEAR)
        return cv2.remap(spr.img, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    # ---------------------------------------------------------------- physics
    def precompute_physics(self, param_fn, t0, t1, fps):
        """Damped spring driven by head motion; returns callable angle(t) per hair part."""
        n = int(math.ceil((t1 - t0) * fps)) + 3
        dt = 1.0 / fps
        k, c, gain = float(self.phys.get("stiffness", 55)), float(self.phys.get("damping", 6)), \
            float(self.phys.get("gain", 1.0))
        th, om = 0.0, 0.0
        prev_drive = None
        out = np.zeros(n)
        sub = 4
        for i in range(n):
            t = t0 + i * dt
            P = param_fn(t)
            drive = P["head_roll"] + P["neck_roll"] + P["body_roll"] + P["head_x"] * 12
            pos_y = P["body_y"] * 400 + P["head_y"] * 6
            if prev_drive is None:
                prev_drive = (drive, pos_y)
            acc = ((drive - prev_drive[0]) + (pos_y - prev_drive[1]) * 0.5) / dt
            prev_drive = (drive, pos_y)
            for _ in range(sub):
                h = dt / sub
                a = -k * th - c * om - gain * acc * 0.35
                om += a * h
                th += om * h
            out[i] = th
        self._phys = (t0, fps, out)

    def hair_angle(self, t):
        if not hasattr(self, "_phys"):
            return 0.0
        t0, fps, arr = self._phys
        i = (t - t0) * fps
        i0 = int(np.clip(math.floor(i), 0, len(arr) - 2))
        f = min(1.0, max(0.0, i - i0))
        return float(arr[i0] * (1 - f) + arr[i0 + 1] * f)

    # ---------------------------------------------------------------- render
    def render(self, P, t=0.0, frame=0):
        """P: dict of params. Returns RGBA float32 canvas."""
        for k in PARAMS:
            if k not in ("eye_open_L", "eye_open_R"):
                P.setdefault(k, DEFAULTS.get(k, 0.0))
        canvas = np.zeros((self.H, self.W, 4), np.float32)
        hair_th = self.hair_angle(t) + P["hair_wind"]
        for p in self.parts:
            M = self.bone_matrix(p.get("bone"), P)
            depth = float(p.get("depth", 0.0))
            kind = p.get("kind", "image")
            if kind == "image":
                spr = p["_spr"]
                extra = None
                if p.get("hair"):
                    extra = self._hair_dx(p, spr, hair_th)
                if p.get("breathe"):
                    by = self.bones.get("body", {"pivot": [0.5, 1]})["pivot"][1] * self.H
                    s = 1 + P["breath"] * 0.012 * float(p["breathe"])
                    M = M @ _sc(1 + (s - 1) * 0.4, s, self.W / 2, by)
                field = self._turn_field(spr, depth, P, extra) if p.get("bone") == "head" or extra else \
                    (self._turn_field(spr, depth * 0.3, P) if depth else None)
                img = self._deform_sprite(spr, field)
                self._blit(canvas, img, spr, M, float(p.get("opacity", 1.0)))
            elif kind == "eye":
                self._eye(canvas, p, P, M, depth, frame)
            elif kind == "mouth":
                self._mouth(canvas, p, P, M, depth)
        return canvas

    def _hair_dx(self, p, spr, th):
        hp = p["hair"]
        root = float(hp.get("root", 0.0)) * self.H
        length = float(hp.get("length", 0.4)) * self.H
        amp = math.radians(th) * float(hp.get("gain", 1.0))

        def fx(X, Y):
            s = np.clip((Y - root) / length, 0, 1.5)
            return amp * length * s ** 1.6
        return fx

    def _blit(self, canvas, img, spr, M, opacity=1.0):
        A = M @ _tr(spr.x0, spr.y0)
        out = cv2.warpAffine(img, A[:2].astype(np.float32), (self.W, self.H), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        a = out[..., 3:4] * opacity
        canvas[..., :3] = canvas[..., :3] * (1 - a) + out[..., :3] * a
        canvas[..., 3:4] = canvas[..., 3:4] * (1 - a) + a

    def _eye(self, canvas, p, P, M, depth, frame):
        side = p.get("side", "L")
        o = P.get("eye_open_" + side, P["eye_open"])
        o = float(np.clip(o, 0.0, 1.25))
        g = p["_geom"]
        layer = np.zeros((self.H, self.W, 4), np.float32)

        def put(spr, dx=0.0, dy=0.0, sy=1.0, alpha=1.0):
            if spr is None:
                return
            A = _tr(dx, dy) @ _sc(1, sy, 0, g["low_y"]) @ _tr(spr.x0, spr.y0)
            out = cv2.warpAffine(spr.img, A[:2].astype(np.float32), (self.W, self.H), flags=cv2.INTER_LINEAR)
            a = out[..., 3:4] * alpha
            layer[..., :3] = layer[..., :3] * (1 - a) + out[..., :3] * a
            layer[..., 3:4] = layer[..., 3:4] * (1 - a) + a

        close = (1 - min(o, 1.0)) * g["h"]
        wide = max(0.0, o - 1.0) * g["h"]
        # eyeball: white + iris (gaze) + highlights, clipped under the moving upper lid
        ball = np.zeros((self.H, self.W, 4), np.float32)
        lay_save = layer
        layer = ball
        put(p.get("_white"))
        gx = P["eye_x"] * float(p.get("gaze_x", 0.12)) * g["h"] * 2
        gy = P["eye_y"] * float(p.get("gaze_y", 0.08)) * g["h"] * 2
        put(p.get("_iris"), gx, gy)
        if p.get("_hilite"):
            shimmer = 0.85 + 0.15 * math.sin(frame * 1.7) * (0.5 + P["hilite"])
            jx = math.sin(frame * 0.9) * 1.2 * P["hilite"]
            put(p["_hilite"], gx * 1.05 + jx, gy * 1.05, alpha=shimmer)
        layer = lay_save
        # clip: visible below the lid edge (per column), above the lower lash
        lid_off = close - wide
        clip = np.zeros((self.H, 1), np.float32)
        yy = np.arange(self.H, dtype=np.float32)[:, None]
        cols = g["cols"]
        if cols:
            xs = np.array(sorted(cols))
            edge = np.array([cols[x] for x in xs], np.float32)
            full_edge = np.full(self.W, -1e6, np.float32)
            full_edge[xs] = edge
            edge_row = full_edge[None, :] + lid_off - 2
            clip = np.clip((yy - edge_row) / 2.0, 0, 1)
            ball[..., 3:4] *= clip[..., None]
        a = ball[..., 3:4]
        layer[..., :3] = layer[..., :3] * (1 - a) + ball[..., :3] * a
        layer[..., 3:4] = layer[..., 3:4] * (1 - a) + a
        put(p.get("_low"))
        # upper lash slides down with the lid, flattens a bit when closed
        flat = 1 - 0.35 * (1 - min(o, 1.0))
        put(p.get("_lash"), 0, lid_off, sy=flat)
        field_spr = _FullSprite(self.W, self.H)
        fld = self._turn_field(field_spr, depth, P)
        if fld is not None:
            layer = self._deform_sprite(_ImgSprite(layer), fld)
        self._blit(canvas, layer, _ImgSprite(layer), M)

    def _mouth(self, canvas, p, P, M, depth):
        m = float(np.clip(P["mouth_open"], 0.0, 1.6))
        layer = np.zeros((self.H, self.W, 4), np.float32)
        up, low, inner = p.get("_upper"), p.get("_lower"), p.get("_inner")
        top_y = up.y0 + up.h * 0.6 if up else (inner.y0 if inner else 0)
        bot_y = low.y0 + low.h * 0.4 if low else (inner.y0 + inner.h if inner else 0)
        gap = max(4.0, bot_y - top_y)

        def put(spr, dy=0.0, sy=1.0, py=0.0, alpha=1.0):
            if spr is None:
                return
            A = _tr(0, dy) @ _sc(1, sy, 0, py) @ _tr(spr.x0, spr.y0)
            out = cv2.warpAffine(spr.img, A[:2].astype(np.float32), (self.W, self.H), flags=cv2.INTER_LINEAR)
            a = out[..., 3:4] * alpha
            layer[..., :3] = layer[..., :3] * (1 - a) + out[..., :3] * a
            layer[..., 3:4] = layer[..., 3:4] * (1 - a) + a

        put(inner, sy=max(0.02, m), py=top_y, alpha=min(1.0, m * 3))
        put(up)
        put(low, dy=(m - 1) * gap)
        fld = self._turn_field(_FullSprite(self.W, self.H), depth, P)
        if fld is not None:
            layer = self._deform_sprite(_ImgSprite(layer), fld)
        self._blit(canvas, layer, _ImgSprite(layer), M)


class _FullSprite:
    def __init__(self, W, H):
        self.x0 = self.y0 = 0
        self.w, self.h = W, H


class _ImgSprite:
    def __init__(self, img):
        self.img = img
        self.x0 = self.y0 = 0
        self.h, self.w = img.shape[:2]
