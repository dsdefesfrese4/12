"""2.5D/3D scene renderer: textured planes at real depths, perspective camera, DOF, fog, light, particles, lines.

World: x right, y up, z forward (into the screen). Units are arbitrary ("metres").

shot:
  scene:
    bg: "#050203" | ["#top", "#bottom"]
    fov: 45
    fog: {color: "#0a0204", density: 0.05}
    dof: {focus: <value>, aperture: 1.5}         # focus distance from camera; aperture scales blur
    light: {dir: [0.4, -0.3, 1], color: "#ffd8b0", ambient: 0.55}
    god_rays: {pos: [x, y, z], color: "#ffcc88", amount: 0.6, threshold: 0.6}
    camera:
      keys: [{at: 0, pos: [0, 0, -8], look: [0, 0, 0], fov: 45, roll: 0, ease: sine}, ...]   # at = shot progress 0..1
      handheld: 0.02                               # subtle noise on position/look
    layers:  (see elements.py for kinds)
      - {kind: image, src: panels/x.png, pos: [x, y, z], width: 6, rot: [rx, ry, rz], opacity: 1,
         frame: border|polaroid, feather: 0.06, light: true, billboard: false, crop: [...]}
      - {kind: slot, slot: c4_p28_p01, ...same placement as image...}
      - {kind: particles, preset: ash|dust|stars|rain|snow|petals|embers, volume: [[x0,x1],[y0,y1],[z0,z1]], count, vel: [x,y,z]}
      - {kind: ribbon | strings | vines | words | text | shatter | cage | glow | blood | clock, ...}
Every numeric field can be an animated <value> (see puppet.py); pos/rot accept a list of <value>.
"""
import math
import os

import cv2
import numpy as np

from . import camera as cam_mod
from . import effects as fx
from . import elements as el
from . import puppet


def _v(x, t, ctx, d=0.0):
    return puppet.value(x, t, ctx, d)


def _vec(x, t, ctx, d=(0, 0, 0)):
    if x is None:
        return np.array(d, np.float64)
    return np.array([_v(c, t, ctx, dd) for c, dd in zip(x, d)], np.float64)


def rot_matrix(rx, ry, rz):
    rx, ry, rz = (math.radians(a) for a in (rx, ry, rz))
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


class Cam:
    def __init__(self, pos, look, fov, roll, W, H):
        self.C = np.array(pos, np.float64)
        fw = np.array(look, np.float64) - self.C
        n = np.linalg.norm(fw)
        fw = fw / n if n > 1e-9 else np.array([0, 0, 1.0])
        up = np.array([0, 1.0, 0])
        if abs(np.dot(fw, up)) > 0.999:
            up = np.array([0, 0, -1.0])
        right = np.cross(up, fw)
        right /= np.linalg.norm(right)
        upc = np.cross(fw, right)
        r = math.radians(roll)
        right, upc = right * math.cos(r) + upc * math.sin(r), upc * math.cos(r) - right * math.sin(r)
        self.fw, self.right, self.up = fw, right, upc
        self.W, self.H = W, H
        self.f = (H / 2) / math.tan(math.radians(fov) / 2)

    def to_cam(self, P):
        d = np.asarray(P, np.float64) - self.C
        return np.stack([d @ self.right, d @ self.up, d @ self.fw], -1)

    def project(self, Pc):
        z = np.maximum(Pc[..., 2], 1e-4)
        return np.stack([self.W / 2 + self.f * Pc[..., 0] / z, self.H / 2 - self.f * Pc[..., 1] / z], -1)


def camera_state(spec, p, t, ctx):
    keys = spec.get("keys")
    if not keys:
        return (_vec(spec.get("pos"), t, ctx, (0, 0, -8)), _vec(spec.get("look"), t, ctx, (0, 0, 0)),
                _v(spec.get("fov"), t, ctx, 45), _v(spec.get("roll"), t, ctx, 0))
    keys = sorted(keys, key=lambda k: k["at"])

    def kv(k, name, d):
        return np.array(k.get(name, d), np.float64)

    def get(name, d):
        if p <= keys[0]["at"]:
            return kv(keys[0], name, d)
        for a, b in zip(keys, keys[1:]):
            if p <= b["at"]:
                q = cam_mod.ease(b.get("ease", spec.get("ease", "ease_in_out")), (p - a["at"]) / max(1e-6, b["at"] - a["at"]))
                return kv(a, name, d) + (kv(b, name, d) - kv(a, name, d)) * q
        return kv(keys[-1], name, d)
    pos, look = get("pos", (0, 0, -8)), get("look", (0, 0, 0))
    fov, roll = float(get("fov", spec.get("fov", 45))), float(get("roll", 0))
    hh = float(spec.get("handheld", 0))
    if hh:
        ph = t * 1.7
        pos = pos + hh * np.array([math.sin(ph * 1.3) + 0.5 * math.sin(ph * 3.1), math.sin(ph * 1.1 + 1) + 0.4 * math.sin(ph * 2.7), 0])
        look = look + hh * 0.6 * np.array([math.sin(ph * 0.9 + 2), math.sin(ph * 1.4 + 3), 0])
    return pos, look, fov, roll


class SceneRenderer:
    def __init__(self, renderer):
        self.R = renderer
        self.tex_cache = {}

    # -------------------------------------------------------------- textures
    def texture(self, key, make):
        if key not in self.tex_cache:
            rgba = make()
            levels = [el.premul(rgba)]
            while max(levels[-1].shape[:2]) > 96:
                levels.append(cv2.pyrDown(levels[-1]))
            self.tex_cache[key] = levels
        return self.tex_cache[key]

    @staticmethod
    def pick_level(levels, proj_w):
        for lv in levels[::-1]:
            if lv.shape[1] >= proj_w * 0.9:
                return lv
        return levels[0]

    # -------------------------------------------------------------- drawing
    def draw_quad(self, canvas, levels, corners_w, cam, ctx_draw, opacity=1.0, shade=None, blur_sigma=0.0, fog=None,
                  tint=None):
        Pc = cam.to_cam(corners_w)
        zmin = Pc[:, 2].min()
        near = 0.08
        if zmin <= near:
            return
        opacity *= float(np.clip((zmin - near) / 0.6, 0, 1))
        if opacity <= 0.003:
            return
        dst = cam.project(Pc).astype(np.float32)
        W, H = cam.W, cam.H
        pad = int(3 * blur_sigma) + 2
        x0, y0 = int(math.floor(dst[:, 0].min())) - pad, int(math.floor(dst[:, 1].min())) - pad
        x1, y1 = int(math.ceil(dst[:, 0].max())) + pad, int(math.ceil(dst[:, 1].max())) + pad
        X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        if X1 <= X0 or Y1 <= Y0:
            return
        proj_w = max(np.linalg.norm(dst[1] - dst[0]), np.linalg.norm(dst[2] - dst[3]))
        tex = self.pick_level(levels, proj_w)
        th, tw = tex.shape[:2]
        src = np.array([[0, 0], [tw, 0], [tw, th], [0, th]], np.float32)
        Hm = cv2.getPerspectiveTransform(src, dst - np.array([X0, Y0], np.float32))
        roi = cv2.warpPerspective(tex, Hm, (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR,
                                  borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        if blur_sigma > 0.6:
            roi = cv2.GaussianBlur(roi, (0, 0), blur_sigma)
        a = roi[..., 3:4] * opacity
        rgb = roi[..., :3] * opacity
        if shade is not None:
            rgb = rgb * shade
        if tint is not None:
            rgb = rgb * tint
        if fog is not None:
            fcol, ff = fog
            if ff > 0.001:
                rgb = rgb * (1 - ff) + fcol * a * ff
        dstv = canvas[Y0:Y1, X0:X1]
        canvas[Y0:Y1, X0:X1] = rgb + dstv * (1 - a)

    # -------------------------------------------------------------- main
    def render(self, s, t, n, ctx):
        R = self.R
        W, H, u = R.W, R.H, R.u
        sc = s["scene"]
        p = (t - s["_start"]) / max(1e-6, s["_end"] - s["_start"])
        canvas = np.zeros((H, W, 3), np.float32)
        bg = sc.get("bg", "#000000")
        if isinstance(bg, list):
            top, bot = (np.array(fx.hex_rgb(c), np.float32) for c in bg)
            g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
            canvas[:] = top * (1 - g) + bot * g
        else:
            canvas[:] = np.array(fx.hex_rgb(bg), np.float32)
        pos, look, fov, roll = camera_state(sc.get("camera", {}), p, t, ctx)
        cam = Cam(pos, look, fov, roll, W, H)
        fog = sc.get("fog")
        fogc = np.array(fx.hex_rgb(fog.get("color", "#000000")), np.float32) if fog else None
        dens = float(fog.get("density", 0.05)) if fog else 0.0
        dof = sc.get("dof")
        focus = _v(dof.get("focus", 6), t, ctx, 6) if dof else None
        aperture = float(dof.get("aperture", 1.0)) if dof else 0.0
        light = sc.get("light")
        if light:
            Ld = np.array(light.get("dir", [0.3, -0.3, 1.0]), np.float64)
            Ld /= np.linalg.norm(Ld)
            lcol = np.array(fx.hex_rgb(light.get("color", "#ffffff")), np.float32)
            amb = float(light.get("ambient", 0.6))

        drawables = []
        for L in sc.get("layers", []):
            drawables += el.build(L, self, cam, t, ctx, R)
        # each drawable: dict(depth, kind, ...)
        drawables.sort(key=lambda d: -d["depth"])
        for d in drawables:
            z = d["depth"]
            blur = 0.0
            if dof and d.get("dof", True):
                blur = aperture * abs(1.0 / max(focus, 0.1) - 1.0 / max(z, 0.1)) * cam.f * 0.02 * u
            ff = (1 - math.exp(-dens * max(0.0, z))) if fog and d.get("fog", True) else 0.0
            fogp = (fogc, ff) if fog else None
            if d["type"] == "quad":
                shade = None
                if light and d.get("light", True):
                    nrm = d["R"] @ np.array([0, 0, -1.0])
                    lam = max(0.0, float(np.dot(nrm, -Ld)))
                    shade = (amb + (1 - amb) * lam) * lcol
                self.draw_quad(canvas, d["levels"], d["corners"], cam, ctx, d.get("opacity", 1.0), shade, blur, fogp,
                               d.get("tint"))
            elif d["type"] == "raster":
                # full-frame premultiplied RGBA produced in screen space (particles, lines)
                img = d["img"]
                if blur > 0.6:
                    img = cv2.GaussianBlur(img, (0, 0), blur)
                a = img[..., 3:4]
                rgb = img[..., :3]
                if fogp and ff > 0.001:
                    rgb = rgb * (1 - ff) + fogc * a * ff
                canvas[:] = rgb + canvas * (1 - a)
        gr = sc.get("god_rays")
        if gr:
            canvas = self.god_rays(canvas, gr, cam, t, ctx)
        return canvas

    def god_rays(self, f, gr, cam, t, ctx):
        H, W = f.shape[:2]
        P = _vec(gr.get("pos"), t, ctx, (0, 2, 20))
        Pc = cam.to_cam(P[None])[0]
        if Pc[2] <= 0.1:
            return f
        lx, ly = cam.project(Pc[None])[0]
        sw, sh = W // 4, H // 4
        small = cv2.resize(f, (sw, sh), interpolation=cv2.INTER_AREA)
        th = float(gr.get("threshold", 0.6))
        m = np.clip((small.mean(axis=2, keepdims=True) - th) / (1 - th), 0, 1) * small
        # light source glow seeds the rays even if nothing bright is there
        yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
        seed = np.exp(-(((xx - lx / 4) ** 2 + (yy - ly / 4) ** 2) / (2 * (sw * 0.04) ** 2)))[..., None]
        m = m + seed * 0.8
        acc = m.copy()
        cx, cy = lx / 4, ly / 4
        for i in range(1, 12):
            s = 1 - 0.06 * i
            M = np.array([[s, 0, cx - s * cx], [0, s, cy - s * cy]], np.float32)
            acc += cv2.warpAffine(m, M, (sw, sh), borderMode=cv2.BORDER_CONSTANT) * (1 - i / 12)
        acc = cv2.GaussianBlur(acc / 6, (0, 0), 2)
        rays = cv2.resize(acc, (W, H), interpolation=cv2.INTER_LINEAR)
        col = np.array(fx.hex_rgb(gr.get("color", "#ffd9a0")), np.float32)
        amt = _v(gr.get("amount", 0.6), t, ctx, 0.6)
        return 1 - (1 - f) * (1 - np.clip(rays * col * amt, 0, 1))
