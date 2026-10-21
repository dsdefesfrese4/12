"""Motion-graphics overlay layer (drawn in screen space over a shot, or globally via style.mg).

shot:
  mg:
    - {type: ring, on: beat|downbeat|[times], center: [0.5,0.5], color, width: 6, r0: 0.02, r1: 0.6, dur: 0.6, blend: add}
    - {type: burst, on: ..., center, count: 24, r0: 0.05, r1: 0.7, width: 3, dur: 0.4}
    - {type: bars, at: 64.3, dir: h|v|diag, count: 5, color, dur: 0.5, thickness: 0.2}      # wipe accent
    - {type: frame, start, end, inset: 0.06, width: 3, color, draw: 0.6, corners: true}       # draws itself on
    - {type: line, a: [x,y], b: [x,y], start, draw: 0.4, width, color}
    - {type: crosshair, center: <xy value>, radius: 0.12, color, spin: 30}
    - {type: grid, spacing: 0.05, dot: 2, color, opacity: 0.25, drift: [0.01, 0]}
    - {type: stripes, angle: 35, spacing: 0.04, width: 0.015, color, opacity: 0.2, speed: 0.1, band: [y0, y1]}
    - {type: ticker, text: "去死 小偷 寄生虫 ", y: 0.12, size: 46, speed: -300, color, opacity: 0.9, angle: -6, band: "#000000"}
    - {type: counter, from: 1, to: 101, start, end, pos: [x,y], size: 160, prefix: "LOOP ", color}
    - {type: glitch_blocks, on: beat, count: 12, color, dur: 0.15}
    - {type: invert_rect, on: ..., rect: [x,y,w,h], dur: 0.12}                                # difference flash
    - {type: halftone, opacity: 0.25, cell: 10}
    - {type: label, text: "ORIGINAL SIN", pos: [x,y], size: 28, color, start, end, typewriter: true}
Time fields accept time expressions; `on` follows effect trigger syntax (beat/downbeat/hit/start/list, every, phase).
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import camera as cam_mod
from . import effects as fx
from . import puppet
from .text import find_font

_TXT = {}


def _col(c, d="#ffffff"):
    return np.array(fx.hex_rgb(c or d), np.float32)


def _text_mask(text, size, root, font=None):
    key = (text, size, font)
    if key in _TXT:
        return _TXT[key]
    fp = find_font(font, root)
    f = ImageFont.truetype(fp, int(size)) if fp else ImageFont.load_default()
    b = f.getbbox(text)
    im = Image.new("L", (max(2, b[2] - b[0] + 8), max(2, b[3] - b[1] + 8)), 0)
    ImageDraw.Draw(im).text((4 - b[0], 4 - b[1]), text, font=f, fill=255)
    m = np.asarray(im).astype(np.float32) / 255
    _TXT[key] = m
    return m


def _comp(f, m, col, alpha, blend="normal"):
    a = np.clip(m * alpha, 0, 1)[..., None]
    if blend == "add":
        return np.minimum(1, f + col * a)
    if blend == "screen":
        return 1 - (1 - f) * (1 - col * a)
    if blend == "difference":
        return f * (1 - a) + np.abs(col - f) * a
    if blend == "multiply":
        return f * (1 - a) + f * col * a
    return f * (1 - a) + col * a


class MGLayer:
    def __init__(self, spec, renderer, start, end):
        self.s = dict(spec)
        self.R = renderer
        P = renderer.P
        self.start = P.T(spec["start"]) if "start" in spec else start
        self.end = P.T(spec["end"]) if "end" in spec else end
        self.trig = None
        if "on" in spec or "at" in spec:
            sp = dict(spec)
            if "at" in spec:
                sp["on"] = [spec["at"]] if not isinstance(spec["at"], list) else spec["at"]
            self.trig = P.triggers(sp, self.start, self.end)
        self.ctx = puppet.Ctx(P, self.start, self.end)

    def _active_trig(self, t, dur):
        if not self.trig:
            return []
        return [(tr, (t - tr) / dur) for tr in self.trig if 0 <= t - tr < dur]

    def draw(self, f, t, n):
        s = self.s
        if not (self.start - 1e-3 <= t <= self.end + float(s.get("dur", 0.6))):
            return f
        typ = s["type"]
        H, W = f.shape[:2]
        u = self.R.u
        col = _col(s.get("color"))
        blend = s.get("blend", "normal")
        op = puppet.value(s.get("opacity", 1.0), t, self.ctx, 1.0)
        if typ in ("ring", "burst", "bars", "glitch_blocks", "invert_rect"):
            dur = float(s.get("dur", 0.6))
            for tr, q in self._active_trig(t, dur):
                f = getattr(self, "_" + typ)(f, q, tr, col, op, blend, W, H, u)
            return f
        if not (self.start <= t <= self.end):
            return f
        return getattr(self, "_" + typ)(f, t, col, op, blend, W, H, u)

    # ---------------- triggered
    def _ring(self, f, q, tr, col, op, blend, W, H, u):
        s = self.s
        c = s.get("center", [0.5, 0.5])
        e = cam_mod.ease("expo_out", q)
        r = (float(s.get("r0", 0.02)) + (float(s.get("r1", 0.6)) - float(s.get("r0", 0.02))) * e) * max(W, H)
        th = max(1, int(float(s.get("width", 6)) * u * (1 - q) + 1))
        m = np.zeros((H, W), np.float32)
        cv2.circle(m, (int(c[0] * W), int(c[1] * H)), int(r), 1.0, th, cv2.LINE_AA)
        return _comp(f, m, col, op * (1 - q), blend if blend != "normal" else "add")

    def _burst(self, f, q, tr, col, op, blend, W, H, u):
        s = self.s
        c = np.array(s.get("center", [0.5, 0.5])) * [W, H]
        n = int(s.get("count", 24))
        rng = np.random.default_rng(int(tr * 1000))
        m = np.zeros((H, W), np.float32)
        e = cam_mod.ease("expo_out", q)
        R = max(W, H)
        for i in range(n):
            a = 2 * math.pi * i / n + rng.uniform(-0.1, 0.1)
            r0 = (float(s.get("r0", 0.05)) + 0.5 * e) * R * rng.uniform(0.8, 1.2)
            r1 = (float(s.get("r0", 0.05)) + float(s.get("r1", 0.7)) * e) * R * rng.uniform(0.8, 1.2)
            p0 = c + np.array([math.cos(a), math.sin(a)]) * r0
            p1 = c + np.array([math.cos(a), math.sin(a)]) * r1
            cv2.line(m, tuple(p0.astype(int)), tuple(p1.astype(int)), 1.0, max(1, int(float(s.get("width", 3)) * u)), cv2.LINE_AA)
        return _comp(f, m, col, op * (1 - q), blend)

    def _bars(self, f, q, tr, col, op, blend, W, H, u):
        s = self.s
        n = int(s.get("count", 5))
        d = s.get("dir", "h")
        thick = float(s.get("thickness", 0.2))
        m = np.zeros((H, W), np.float32)
        for i in range(n):
            qi = min(1, max(0, q * 1.6 - i * 0.12))
            e_in = cam_mod.ease("expo_out", min(1, qi * 2))
            e_out = cam_mod.ease("expo_in", max(0, qi * 2 - 1))
            if d == "h":
                y0 = int(i / n * H)
                y1 = int(y0 + H / n * thick * 5)
                xa, xb = int(W * e_out), int(W * e_in)
                m[y0:y1, xa:xb] = 1
            else:
                x0 = int(i / n * W)
                x1 = int(x0 + W / n * thick * 5)
                ya, yb = int(H * e_out), int(H * e_in)
                m[ya:yb, x0:x1] = 1
        if d == "diag":
            M = cv2.getRotationMatrix2D((W / 2, H / 2), -25, 1.4)
            m = cv2.warpAffine(m, M, (W, H))
        return _comp(f, m, col, op, blend)

    def _glitch_blocks(self, f, q, tr, col, op, blend, W, H, u):
        rng = np.random.default_rng(int(tr * 1000) + int(q * 4))
        m = np.zeros((H, W), np.float32)
        for _ in range(int(self.s.get("count", 12))):
            x, y = rng.uniform(0, W), rng.uniform(0, H)
            w, h = rng.uniform(0.03, 0.25) * W, rng.uniform(0.005, 0.04) * H
            m[int(y):int(y + h), int(x):int(x + w)] = 1
        return _comp(f, m, col, op * (1 - q * 0.5), self.s.get("blend", "difference"))

    def _invert_rect(self, f, q, tr, col, op, blend, W, H, u):
        x, y, w, h = self.s.get("rect", [0, 0, 1, 1])
        out = f.copy()
        sl = (slice(int(y * H), int((y + h) * H)), slice(int(x * W), int((x + w) * W)))
        out[sl] = 1 - out[sl]
        return out

    # ---------------- continuous
    def _frame(self, f, t, col, op, blend, W, H, u):
        s = self.s
        p = min(1, (t - self.start) / float(s.get("draw", 0.6)))
        e = cam_mod.ease("expo_out", p)
        ins = float(s.get("inset", 0.06))
        x0, y0, x1, y1 = ins * W, ins * H, (1 - ins) * W, (1 - ins) * H
        m = np.zeros((H, W), np.float32)
        th = max(1, int(float(s.get("width", 3)) * u))
        if s.get("corners", True):
            L = min(W, H) * 0.08 * e
            for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x1, y1, -1, -1), (x0, y1, 1, -1)):
                cv2.line(m, (int(cx), int(cy)), (int(cx + sx * L), int(cy)), 1, th, cv2.LINE_AA)
                cv2.line(m, (int(cx), int(cy)), (int(cx), int(cy + sy * L)), 1, th, cv2.LINE_AA)
        else:
            pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
            per = 2 * ((x1 - x0) + (y1 - y0))
            left = per * e
            for a, b in zip(pts, pts[1:]):
                seg = math.hypot(b[0] - a[0], b[1] - a[1])
                if left <= 0:
                    break
                qq = min(1, left / seg)
                cv2.line(m, (int(a[0]), int(a[1])), (int(a[0] + (b[0] - a[0]) * qq), int(a[1] + (b[1] - a[1]) * qq)), 1, th, cv2.LINE_AA)
                left -= seg
        return _comp(f, m, col, op, blend)

    def _line(self, f, t, col, op, blend, W, H, u):
        s = self.s
        p = min(1, (t - self.start) / float(s.get("draw", 0.4)))
        e = cam_mod.ease("expo_out", p)
        a, b = np.array(s["a"]) * [W, H], np.array(s["b"]) * [W, H]
        m = np.zeros((H, W), np.float32)
        cv2.line(m, tuple(a.astype(int)), tuple((a + (b - a) * e).astype(int)), 1, max(1, int(float(s.get("width", 3)) * u)), cv2.LINE_AA)
        return _comp(f, m, col, op, blend)

    def _crosshair(self, f, t, col, op, blend, W, H, u):
        s = self.s
        c = s.get("center", [0.5, 0.5])
        cx = puppet.value(c[0], t, self.ctx, 0.5) * W
        cy = puppet.value(c[1], t, self.ctx, 0.5) * H
        p = min(1, (t - self.start) / 0.35)
        r = float(s.get("radius", 0.12)) * H * (1.6 - 0.6 * cam_mod.ease("expo_out", p))
        m = np.zeros((H, W), np.float32)
        th = max(1, int(2 * u))
        cv2.circle(m, (int(cx), int(cy)), int(r), 1, th, cv2.LINE_AA)
        cv2.circle(m, (int(cx), int(cy)), int(r * 0.35), 1, th, cv2.LINE_AA)
        a0 = math.radians(float(s.get("spin", 30)) * (t - self.start))
        for k in range(4):
            a = a0 + k * math.pi / 2
            p0 = (int(cx + math.cos(a) * r * 0.55), int(cy + math.sin(a) * r * 0.55))
            p1 = (int(cx + math.cos(a) * r * 1.35), int(cy + math.sin(a) * r * 1.35))
            cv2.line(m, p0, p1, 1, th, cv2.LINE_AA)
        return _comp(f, m, col, op, blend)

    def _grid(self, f, t, col, op, blend, W, H, u):
        s = self.s
        sp = float(s.get("spacing", 0.05)) * W
        dr = s.get("drift", [0.01, 0])
        ox = (dr[0] * W * (t - self.start)) % sp
        oy = (dr[1] * H * (t - self.start)) % sp
        m = np.zeros((H, W), np.float32)
        d = max(1, int(float(s.get("dot", 2)) * u))
        for y in np.arange(oy, H, sp):
            for x in np.arange(ox, W, sp):
                cv2.circle(m, (int(x), int(y)), d, 1, -1, cv2.LINE_AA)
        return _comp(f, m, col, op, blend)

    def _stripes(self, f, t, col, op, blend, W, H, u):
        s = self.s
        ang = math.radians(float(s.get("angle", 35)))
        sp = float(s.get("spacing", 0.04)) * W
        wd = float(s.get("width", 0.015)) * W
        yy, xx = np.mgrid[0:H:2, 0:W:2].astype(np.float32)
        d = xx * math.cos(ang) + yy * math.sin(ang) + float(s.get("speed", 0.1)) * W * (t - self.start)
        m = ((d % sp) < wd).astype(np.float32)
        m = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)
        band = s.get("band")
        if band:
            mask = np.zeros_like(m)
            mask[int(band[0] * H):int(band[1] * H)] = 1
            m *= mask
        return _comp(f, m, col, op, blend)

    def _ticker(self, f, t, col, op, blend, W, H, u):
        s = self.s
        tm = _text_mask(s.get("text", "TAKOPI "), int(float(s.get("size", 46)) * u), self.R.P.root, s.get("font"))
        th, tw = tm.shape
        reps = int(W * 1.6 / tw) + 3
        strip = np.tile(tm, (1, reps))
        off = int((float(s.get("speed", -300)) * u * (t - self.start)) % tw)
        strip = np.roll(strip, off, axis=1)
        bandh = int(th * 1.5)
        layer = np.zeros((bandh, strip.shape[1]), np.float32)
        layer[(bandh - th) // 2:(bandh - th) // 2 + th] = strip
        bg = s.get("band")
        canvas_m = np.zeros((H, W), np.float32)
        canvas_b = np.zeros((H, W), np.float32)
        ang = float(s.get("angle", 0))
        y = float(s.get("y", 0.12)) * H
        M = cv2.getRotationMatrix2D((strip.shape[1] / 2, bandh / 2), ang, 1.0)
        M[0, 2] += W / 2 - strip.shape[1] / 2
        M[1, 2] += y - bandh / 2
        canvas_m = cv2.warpAffine(layer, M, (W, H))
        if bg:
            canvas_b = cv2.warpAffine(np.ones_like(layer), M, (W, H))
            f = _comp(f, canvas_b, _col(bg), op * 0.85)
        return _comp(f, canvas_m, col, op, blend)

    def _counter(self, f, t, col, op, blend, W, H, u):
        s = self.s
        q = (t - self.start) / max(1e-6, self.end - self.start)
        q = cam_mod.ease(s.get("ease", "expo_in"), min(1, q))
        v = int(round(float(s.get("from", 1)) + (float(s.get("to", 101)) - float(s.get("from", 1))) * q))
        txt = f"{s.get('prefix', '')}{v}{s.get('suffix', '')}"
        m = _text_mask(txt, int(float(s.get("size", 160)) * u), self.R.P.root, s.get("font"))
        pos = s.get("pos", [0.5, 0.5])
        canvas = np.zeros((H, W), np.float32)
        x, y = int(pos[0] * W - m.shape[1] / 2), int(pos[1] * H - m.shape[0] / 2)
        x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + m.shape[1]), min(H, y + m.shape[0])
        if x1 > x0 and y1 > y0:
            canvas[y0:y1, x0:x1] = m[y0 - y:y1 - y, x0 - x:x1 - x]
        return _comp(f, canvas, col, op, blend)

    def _label(self, f, t, col, op, blend, W, H, u):
        s = self.s
        txt = s["text"]
        if s.get("typewriter", True):
            k = int((t - self.start) / float(s.get("char_dur", 0.04)))
            txt = txt[:max(0, k)] + ("_" if int(t * 4) % 2 == 0 and k < len(s["text"]) + 6 else "")
        if not txt:
            return f
        m = _text_mask(txt, int(float(s.get("size", 28)) * u), self.R.P.root, s.get("font"))
        pos = s.get("pos", [0.08, 0.9])
        canvas = np.zeros((H, W), np.float32)
        x, y = int(pos[0] * W), int(pos[1] * H)
        x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + m.shape[1]), min(H, y + m.shape[0])
        if x1 > x0 and y1 > y0:
            canvas[y0:y1, x0:x1] = m[y0 - y:y1 - y, x0 - x:x1 - x]
        return _comp(f, canvas, col, op, blend)

    def _halftone(self, f, t, col, op, blend, W, H, u):
        cell = max(4, int(float(self.s.get("cell", 10)) * u))
        g = cv2.resize(f.mean(axis=2), (W // cell, H // cell), interpolation=cv2.INTER_AREA)
        m = np.zeros((H, W), np.float32)
        for j in range(g.shape[0]):
            for i in range(g.shape[1]):
                r = int((1 - g[j, i]) * cell * 0.7)
                if r > 0:
                    cv2.circle(m, (i * cell + cell // 2, j * cell + cell // 2), r, 1, -1, cv2.LINE_AA)
        return _comp(f, m, _col(self.s.get("color", "#000000")), op, blend)
