"""Kinetic typography: per-character designed text animation.

texts:
  - start: 100.28
    end: 103.8
    text: "谁言语淬毒"
    kinetic:
      in: slam|drop|flip|scatter|blur_in|type|glitch|wipe|stamp|rise     (per-char, staggered)
      out: fade|scatter|blur|glitch|wipe|drop|cut
      idle: none|float|jitter|beat_pulse|flicker
      stagger: 0.05          # s between chars ("beat" = one char per beat)
      in_dur: 0.35
      out_dur: 0.25
      accent: "#d0141c"      # colour for keywords
      keywords: ["毒"]
      ghost: {text: "淬毒", size: 520, color: "#ffffff", opacity: 0.08, drift: [-40, 0]}   # huge outline text behind
      underline: {color: "#d0141c", width: 6, delay: 0.2, dur: 0.4}
      box: {color: "#ffffff", width: 3, pad: 24, delay: 0.1, dur: 0.5}
      rgb: 6                 # chromatic split px on idle/in
      tracking: 0.08         # letter spacing (fraction of size)
      shadow: {color: "#000000", offset: [6, 6], blur: 6, opacity: 0.6}
    pos: [0.5, 0.5]  size: 120  color: "#ffffff"  stroke: {width: 0}  vertical: false  font: ...
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import camera as cam_mod
from . import effects as fx
from .text import find_font


def _rand(seed):
    return np.random.default_rng(abs(hash(seed)) % (2 ** 31))


class KineticText:
    def __init__(self, spec, project, u):
        self.s = spec
        self.k = spec.get("kinetic") or {}
        self.P = project
        self.u = u
        self.start, self.end = spec["_start"], spec["_end"]
        size = int(float(spec.get("size", 110)) * u)
        self.size = size
        fp = find_font(spec.get("font") or project.meta.get("font"), project.root)
        self.font = ImageFont.truetype(fp, size) if fp else ImageFont.load_default()
        self.fp = fp
        self.color = fx.hex_rgb(spec.get("color", "#ffffff"))
        self.accent = fx.hex_rgb(self.k.get("accent", "#d0141c"))
        kw = self.k.get("keywords") or []
        st = spec.get("stroke") or {"width": 0}
        self.sw = int(float(st.get("width", 0)) * u)
        self.sc = fx.hex_rgb(st.get("color", "#000000"))
        self.vertical = bool(spec.get("vertical", False))
        text = str(spec["text"])
        self.chars = []
        hot = set()
        for w in kw:
            i = text.find(w)
            while i >= 0:
                hot.update(range(i, i + len(w)))
                i = text.find(w, i + 1)
        track = float(self.k.get("tracking", 0.06)) * size
        pen = 0.0
        asc, desc = self.font.getmetrics()
        for i, ch in enumerate(text):
            adv = (self.font.getlength(ch) if not self.vertical else (asc + desc) * 0.98) + track
            if ch.strip():
                col = self.accent if i in hot else self.color
                g = self._glyph(ch, col)
                if self.vertical:
                    self.chars.append([g, 0.0, pen + g.shape[0] / 2, i])
                else:
                    self.chars.append([g, pen + g.shape[1] / 2, 0.0, i])
            pen += adv
        n = max(1, len(self.chars))
        if self.vertical:
            self.bw, self.bh = size * 1.2, pen - track
            for c in self.chars:
                c[2] -= self.bh / 2
        else:
            self.bw, self.bh = pen - track, (asc + desc)
            for c in self.chars:
                c[1] -= self.bw / 2
        self.n = n
        st_ = self.k.get("stagger", 0.045)
        if st_ == "beat" and project.T.beats:
            bts = [b for b in project.T.beats if b >= self.start - 1e-3]
            self.delays = [(bts[i] - self.start) if i < len(bts) else i * 0.3 for i in range(n)]
        else:
            self.delays = [i * float(st_) for i in range(n)]
        self.ghost = None
        if self.k.get("ghost"):
            gs = self.k["ghost"]
            f2 = ImageFont.truetype(fp, int(gs.get("size", 500) * u)) if fp else self.font
            self.ghost = self._outline_text(gs.get("text", text), f2, max(2, int(3 * u)))

    def _glyph(self, ch, col):
        pad = self.sw + 6
        b = self.font.getbbox(ch, stroke_width=self.sw)
        w, h = b[2] - b[0] + pad * 2, b[3] - b[1] + pad * 2
        asc, desc = self.font.getmetrics()
        hh = asc + desc + pad * 2
        im = Image.new("RGBA", (max(2, w), max(2, hh)), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.text((pad - b[0], pad), ch, font=self.font, fill=tuple(int(c * 255) for c in col) + (255,),
               stroke_width=self.sw, stroke_fill=tuple(int(c * 255) for c in self.sc) + (255,))
        return np.asarray(im).astype(np.float32) / 255.0

    def _outline_text(self, text, font, width):
        b = font.getbbox(text)
        w, h = b[2] - b[0] + 20, b[3] - b[1] + 20
        im = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(im)
        d.text((10 - b[0], 10 - b[1]), text, font=font, fill=255, stroke_width=width, stroke_fill=255)
        full = np.asarray(im).astype(np.float32) / 255
        im2 = Image.new("L", (w, h), 0)
        ImageDraw.Draw(im2).text((10 - b[0], 10 - b[1]), text, font=font, fill=255)
        inner = np.asarray(im2).astype(np.float32) / 255
        return np.clip(full - inner * 0.0, 0, 1) - np.clip(inner - cv2.erode(inner, np.ones((width * 2 + 1,) * 2)), 0, 0)

    def active(self, t):
        return self.start - 0.001 <= t < self.end + float(self.k.get("out_dur", 0.25)) * 0

    # ------------------------------------------------------------------ draw
    def draw(self, f, t, T=None):
        if not (self.start - 1e-3 <= t < self.end):
            return f
        H, W = f.shape[:2]
        k = self.k
        u = self.u
        lt = t - self.start
        rt = self.end - t
        pos = self.s.get("pos", [0.5, 0.5])
        ax, ay = pos[0] * W, pos[1] * H
        in_d = float(k.get("in_dur", 0.35))
        out_d = float(k.get("out_dur", 0.25))
        kin, kout, idle = k.get("in", "rise"), k.get("out", "fade"), k.get("idle", "none")
        # ghost text behind
        if self.ghost is not None:
            gs = k["ghost"]
            drift = gs.get("drift", [-40, 0])
            gx = ax + drift[0] * u * lt - self.ghost.shape[1] / 2
            gy = ay + drift[1] * u * lt - self.ghost.shape[0] / 2
            op = float(gs.get("opacity", 0.08)) * min(1, lt / 0.3) * min(1, max(0, rt) / 0.3)
            col = np.array(fx.hex_rgb(gs.get("color", "#ffffff")), np.float32)
            _blit_mask(f, self.ghost, int(gx), int(gy), col, op)
        # decorations
        self._decor(f, t, ax, ay, lt, rt)
        beat_pulse = 0.0
        if idle == "beat_pulse" and T is not None and T.beats:
            past = [b for b in T.beats if b <= t]
            if past:
                beat_pulse = math.exp(-(t - past[-1]) / 0.12)
        for gi, (g, cx, cy, ci) in enumerate(self.chars):
            d = self.delays[gi]
            p_in = (lt - d) / in_d
            if p_in < 0:
                continue
            p_in = min(1.0, p_in)
            p_out = 0.0
            if kout != "cut" and rt < out_d + (self.n - 1 - gi) * 0.02 * (kout in ("scatter", "drop")):
                p_out = 1 - max(0.0, rt - (self.n - 1 - gi) * 0.02 * (kout in ("scatter", "drop"))) / out_d
                p_out = min(1.0, max(0.0, p_out))
            r = _rand((self.s.get("_id", self.s.get("text")), gi))
            rv = r.uniform(-1, 1, 6)
            sc, rot, ox, oy, op, blur, flipx, rgb = 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0
            e = cam_mod.ease("expo_out", p_in)
            if kin == "slam":
                sc = 1 + 2.2 * (1 - e)
                op = min(1, p_in * 3)
                blur = 6 * (1 - e) * u
            elif kin == "drop":
                eb = cam_mod.ease("back_out", p_in)
                oy = -(1 - eb) * self.size * 1.2
                op = min(1, p_in * 4)
            elif kin == "rise":
                oy = (1 - e) * self.size * 0.6
                op = e
                blur = 3 * (1 - e) * u
            elif kin == "flip":
                flipx = abs(math.cos((1 - e) * math.pi / 2))
                op = min(1, p_in * 2)
            elif kin == "scatter":
                ox, oy = rv[0] * 420 * u * (1 - e), rv[1] * 260 * u * (1 - e)
                rot = rv[2] * 90 * (1 - e)
                sc = 1 + rv[3] * 0.8 * (1 - e)
                op = e
            elif kin == "blur_in":
                blur = 14 * (1 - e) * u
                op = e
                sc = 1.15 - 0.15 * e
            elif kin == "type":
                op = 1.0 if p_in > 0 else 0
            elif kin == "glitch":
                if p_in < 1:
                    jj = _rand((gi, int(t * 30)))
                    ox = jj.uniform(-1, 1) * 30 * u * (1 - p_in)
                    op = 1.0 if jj.uniform() > 0.35 * (1 - p_in) else 0.2
                    rgb = 10 * u * (1 - p_in)
            elif kin == "stamp":
                sc = 1 + 0.6 * (1 - cam_mod.ease("expo_out", p_in))
                rot = rv[2] * 6
                op = min(1, p_in * 5)
            elif kin == "wipe":
                op = 1.0
            # idle
            if idle == "float":
                oy += math.sin(t * 2.1 + gi * 0.7) * 4 * u
            elif idle == "jitter":
                jj = _rand((gi, int(t * 12)))
                ox += jj.uniform(-1, 1) * 2.5 * u
                oy += jj.uniform(-1, 1) * 2.5 * u
            elif idle == "flicker":
                jj = _rand((gi, int(t * 15)))
                op *= 0.55 if jj.uniform() < 0.12 else 1
            sc *= 1 + 0.12 * beat_pulse
            if k.get("rgb"):
                rgb = max(rgb, float(k["rgb"]) * u * (0.4 + 0.6 * beat_pulse))
            # out
            if p_out > 0:
                eo = cam_mod.ease("expo_in", p_out)
                if kout == "fade":
                    op *= 1 - p_out
                elif kout == "scatter":
                    ox += rv[4] * 500 * u * eo
                    oy += rv[5] * 300 * u * eo - 120 * u * eo
                    rot += rv[2] * 120 * eo
                    op *= 1 - eo
                elif kout == "blur":
                    blur += 16 * eo * u
                    op *= 1 - eo
                    sc *= 1 + 0.2 * eo
                elif kout == "glitch":
                    jj = _rand((gi, int(t * 30), "o"))
                    ox += jj.uniform(-1, 1) * 40 * u * p_out
                    op *= 0 if jj.uniform() < p_out else 1
                    rgb = max(rgb, 12 * u * p_out)
                elif kout == "drop":
                    oy += eo * self.size * 2
                    op *= 1 - eo
                elif kout == "wipe":
                    pass
            if op <= 0.01:
                continue
            gimg = g
            if blur > 0.5:
                gimg = cv2.GaussianBlur(np.pad(g, ((int(blur * 3),) * 2, (int(blur * 3),) * 2, (0, 0))), (0, 0), blur)
            gh, gw = gimg.shape[:2]
            ow, oh = int(gw * max(sc, 1) + 4), int(gh * max(sc, 1) + 4)
            ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
            sx, sy = sc * max(flipx, 0.02), sc
            A = np.array([[ca * sx, -sa * sy], [sa * sx, ca * sy]], np.float32)
            c_in = np.array([gw / 2, gh / 2], np.float32)
            c_out = np.array([ow / 2, oh / 2], np.float32)
            M = np.hstack([A, (c_out - A @ c_in)[:, None]]).astype(np.float32)
            warped = cv2.warpAffine(gimg, M, (ow, oh), flags=cv2.INTER_LINEAR, borderValue=0)
            x = int(ax + cx + ox - ow / 2)
            y = int(ay + cy + oy - oh / 2)
            if kin == "wipe" and p_in < 1:
                cut = int(ow * cam_mod.ease("ease_out", p_in))
                warped = warped.copy()
                warped[:, cut:, 3] = 0
            sh = k.get("shadow")
            if sh:
                so = sh.get("offset", [6, 6])
                scol = np.array(fx.hex_rgb(sh.get("color", "#000000")), np.float32)
                sa = cv2.GaussianBlur(warped[..., 3], (0, 0), max(0.5, float(sh.get("blur", 6)) * u))
                _blit_mask(f, sa, x + int(so[0] * u), y + int(so[1] * u), scol, op * float(sh.get("opacity", 0.6)))
            if rgb > 0.5:
                o = int(rgb)
                _blit_rgba(f, warped * np.array([1, 0, 0, 0.5], np.float32), x - o, y, op, additive=True)
                _blit_rgba(f, warped * np.array([0, 0, 1, 0.5], np.float32), x + o, y, op, additive=True)
            _blit_rgba(f, warped, x, y, op)
        return f

    def _decor(self, f, t, ax, ay, lt, rt):
        k, u = self.k, self.u
        out_d = float(k.get("out_dur", 0.25))
        fade = min(1.0, max(0.0, rt / out_d)) if rt < out_d else 1.0
        ul = k.get("underline")
        if ul:
            p = min(1, max(0, (lt - float(ul.get("delay", 0.2))) / float(ul.get("dur", 0.4))))
            if p > 0:
                e = cam_mod.ease("expo_out", p)
                col = tuple(float(c) for c in fx.hex_rgb(ul.get("color", "#d0141c")))
                if self.vertical:
                    x = int(ax + self.bw * 0.62)
                    y0 = int(ay - self.bh / 2)
                    cv2.line(f, (x, y0), (x, int(y0 + self.bh * e)), col, max(1, int(ul.get("width", 6) * u)), cv2.LINE_AA)
                else:
                    y = int(ay + self.bh * 0.62)
                    x0 = int(ax - self.bw / 2)
                    cv2.line(f, (x0, y), (int(x0 + self.bw * e), y), col, max(1, int(ul.get("width", 6) * u)), cv2.LINE_AA)
        bx = k.get("box")
        if bx:
            p = min(1, max(0, (lt - float(bx.get("delay", 0.1))) / float(bx.get("dur", 0.5))))
            if p > 0:
                pad = float(bx.get("pad", 24)) * u
                x0, y0 = ax - self.bw / 2 - pad, ay - self.bh / 2 - pad
                x1, y1 = ax + self.bw / 2 + pad, ay + self.bh / 2 + pad
                pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
                per = 2 * ((x1 - x0) + (y1 - y0))
                left = per * cam_mod.ease("expo_out", p)
                col = tuple(float(c) * fade for c in fx.hex_rgb(bx.get("color", "#ffffff")))
                for a, b in zip(pts, pts[1:]):
                    seg = math.hypot(b[0] - a[0], b[1] - a[1])
                    if left <= 0:
                        break
                    q = min(1, left / seg)
                    cv2.line(f, (int(a[0]), int(a[1])), (int(a[0] + (b[0] - a[0]) * q), int(a[1] + (b[1] - a[1]) * q)), col,
                             max(1, int(bx.get("width", 3) * u)), cv2.LINE_AA)
                    left -= seg


def _blit_rgba(f, rgba, x, y, alpha=1.0, additive=False):
    H, W = f.shape[:2]
    h, w = rgba.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x0 >= x1 or y0 >= y1:
        return
    src = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = src[..., 3:4] * alpha
    if additive:
        f[y0:y1, x0:x1] = np.minimum(1, f[y0:y1, x0:x1] + src[..., :3] * a)
    else:
        f[y0:y1, x0:x1] = f[y0:y1, x0:x1] * (1 - a) + src[..., :3] * a


def _blit_mask(f, m, x, y, col, alpha):
    H, W = f.shape[:2]
    h, w = m.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x0 >= x1 or y0 >= y1:
        return
    a = m[y0 - y:y1 - y, x0 - x:x1 - x][..., None] * alpha
    f[y0:y1, x0:x1] = f[y0:y1, x0:x1] * (1 - a) + col * a
