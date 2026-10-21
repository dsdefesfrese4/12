"""Animated lyric / caption text."""
import glob
import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .effects import hex_rgb, _rand

FONT_FALLBACKS = [
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
]


def find_font(path=None, project_root=None):
    cands = []
    if path:
        cands.append(path if os.path.isabs(path) or not project_root else os.path.join(project_root, path))
    if project_root:
        cands += sorted(glob.glob(os.path.join(project_root, "assets", "fonts", "*.[ot]t[fc]")))
    cands += FONT_FALLBACKS
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


class TextItem:
    def __init__(self, spec, project, u):
        self.s = spec
        self.u = u
        self.start, self.end = spec["_start"], spec["_end"]
        font = find_font(spec.get("font") or project.meta.get("font"), project.root)
        size = int(float(spec.get("size", 84)) * u)
        self.font = ImageFont.truetype(font, size) if font else ImageFont.load_default()
        self.color = tuple(int(c * 255) for c in hex_rgb(spec.get("color", "#ffffff")))
        st = spec.get("stroke", {"width": 5, "color": "#000000"})
        self.stroke_w = int(float(st.get("width", 0)) * u) if st else 0
        self.stroke_c = tuple(int(c * 255) for c in hex_rgb(st.get("color", "#000000"))) if st else (0, 0, 0)
        self.vertical = bool(spec.get("vertical", False))
        self.spacing = float(spec.get("spacing", 0.05)) * size
        self.glyphs = []
        lines = str(spec["text"]).split("\n")
        self._layout(lines, size)

    def _glyph(self, ch):
        pad = self.stroke_w + 4
        bbox = self.font.getbbox(ch, stroke_width=self.stroke_w)
        w = max(1, bbox[2] - bbox[0]) + pad * 2
        h = max(1, bbox[3] - bbox[1]) + pad * 2
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.text((pad - bbox[0], pad - bbox[1]), ch, font=self.font, fill=self.color + (255,),
               stroke_width=self.stroke_w, stroke_fill=self.stroke_c + (255,))
        a = np.asarray(im).astype(np.float32) / 255.0
        return a, bbox, pad

    def _layout(self, lines, size):
        # each glyph: (rgba, x, y) with x,y = top-left in pixels relative to block origin
        items = []
        asc, desc = self.font.getmetrics()
        line_h = (asc + desc) * float(self.s.get("line_height", 1.15))
        for li, line in enumerate(lines):
            pen = 0.0
            for ch in line:
                adv = self.font.getlength(ch) if not self.vertical else size
                if ch.strip():
                    rgba, bbox, pad = self._glyph(ch)
                    if self.vertical:
                        x = -li * line_h - (bbox[2] - bbox[0]) / 2 - pad
                        y = pen + bbox[1] - pad
                        adv = (asc + desc) * 0.95
                    else:
                        x = pen + bbox[0] - pad
                        y = li * line_h + bbox[1] - pad
                    items.append([rgba, x, y])
                pen += adv + self.spacing
        if not items:
            self.glyphs = []
            return
        x0 = min(i[1] for i in items)
        y0 = min(i[2] for i in items)
        x1 = max(i[1] + i[0].shape[1] for i in items)
        y1 = max(i[2] + i[0].shape[0] for i in items)
        self.bw, self.bh = x1 - x0, y1 - y0
        for i in items:
            i[1] -= x0
            i[2] -= y0
        self.glyphs = items

    def active(self, t):
        return self.start - 0.001 <= t < self.end

    def draw(self, f, t, T=None):
        if not self.glyphs or not self.active(t):
            return f
        H, W = f.shape[:2]
        anim = self.s.get("anim", "pop")
        pos = self.s.get("pos", [0.5, 0.82])
        anchor_x = pos[0] * W - self.bw / 2
        anchor_y = pos[1] * H - self.bh / 2
        lt = t - self.start
        dur = self.end - self.start
        n = len(self.glyphs)
        stagger = float(self.s.get("stagger", 0.04 if anim != "typewriter" else min(0.08, dur * 0.6 / n)))
        out_d = float(self.s.get("out", 0.15))
        fade_out = 1.0 if out_d <= 0 else min(1.0, max(0.0, (self.end - t) / out_d))
        # per-beat reveal: one glyph per beat
        beat_times = None
        if self.s.get("per") == "beat" and T is not None and T.beats:
            beat_times = [b for b in T.beats if b >= self.start - 1e-3][:n]
        gx_shake = gy_shake = 0.0
        if anim == "slam":
            k = min(1.0, lt / 0.12)
            if k >= 1 and lt < 0.4:
                r = _rand(self.s.get("id", "t"), t, 30)
                amp = 10 * self.u * (1 - (lt - 0.12) / 0.28)
                gx_shake, gy_shake = r.uniform(-amp, amp), r.uniform(-amp, amp)
        for i, (rgba, gx, gy) in enumerate(self.glyphs):
            ti = beat_times[i] - self.start if beat_times and i < len(beat_times) else i * stagger
            if anim == "slam":
                ti = 0
            local = lt - ti
            if local < 0:
                continue
            scale, alpha, ox, oy = 1.0, 1.0, 0.0, 0.0
            if anim == "pop":
                k = min(1.0, local / 0.14)
                scale = 1 + 0.9 * (1 - k) ** 2 - 0.12 * math.sin(math.pi * k)
                alpha = min(1.0, local / 0.06)
            elif anim == "typewriter":
                alpha = 1.0
            elif anim == "fade":
                alpha = min(1.0, local / float(self.s.get("fade", 0.3)))
            elif anim == "slide_up":
                k = min(1.0, local / 0.25)
                e = 1 - (1 - k) ** 3
                oy = (1 - e) * 40 * self.u
                alpha = e
            elif anim == "slam":
                k = min(1.0, local / 0.12)
                scale = 1 + 2.0 * (1 - k) ** 2
                alpha = min(1.0, k * 1.5)
            elif anim == "glitch":
                alpha = 1.0
                if local < 0.35:
                    r = _rand((self.s.get("id"), i), t, 30)
                    ox = r.uniform(-1, 1) * 25 * self.u * (1 - local / 0.35)
                    alpha = 1.0 if r.uniform() > 0.3 else 0.3
            alpha *= fade_out
            if alpha <= 0.01:
                continue
            g = rgba
            if abs(scale - 1) > 0.01:
                g = cv2.resize(rgba, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
            gh, gw = g.shape[:2]
            cx = anchor_x + gx + rgba.shape[1] / 2 + ox + gx_shake
            cy = anchor_y + gy + rgba.shape[0] / 2 + oy + gy_shake
            _blit(f, g, int(round(cx - gw / 2)), int(round(cy - gh / 2)), alpha)
        return f


def _blit(f, rgba, x, y, alpha):
    H, W = f.shape[:2]
    h, w = rgba.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x0 >= x1 or y0 >= y1:
        return
    src = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = src[..., 3:4] * alpha
    f[y0:y1, x0:x1] = f[y0:y1, x0:x1] * (1 - a) + src[..., :3] * a
