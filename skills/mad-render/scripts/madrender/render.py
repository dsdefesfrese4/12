"""Render a project.yaml to video.

  python3 -m madrender.render project.yaml                     # full quality -> out/<title>.mp4
  python3 -m madrender.render project.yaml --preview           # half res, fast
  python3 -m madrender.render project.yaml --from b16 --to b32 # only a range
  python3 -m madrender.render project.yaml --still 3.2 b20     # PNG stills for checking
  python3 -m madrender.render project.yaml --contact           # one frame per shot, labelled sheet
"""
import argparse
import copy
import math
import os
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool

import cv2
import numpy as np

from . import camera as cam_mod
from . import effects as fx
from . import puppet
from .kinetic import KineticText
from .mg import MGLayer
from .scene3d import SceneRenderer
from .text import TextItem
from .timeline import Project


class Renderer:
    def __init__(self, project_path, scale=1.0):
        self.P = Project(project_path)
        self.scale = scale
        self.W = int(round(self.P.W * scale / 2) * 2)
        self.H = int(round(self.P.H * scale / 2) * 2)
        self.u = self.H / 1080.0
        self.bg = np.array(fx.hex_rgb(self.P.meta.get("background")), np.float32)
        self._img_cache = {}
        self.show_slots = True
        self._prepare()

    # ------------------------------------------------------------- setup
    def _prepare(self):
        P = self.P
        glob_fx = P.style.get("effects", []) or []
        self.global_fx = [self._prep_fx(e, P.t0, P.t1) for e in glob_fx]
        for s in P.shots:
            s["_cam"] = cam_mod.resolve(s.get("camera"))
            s["_fx"] = [self._prep_fx(e, s["_start"], s["_end"]) for e in (s.get("effects") or [])]
            tr = s.get("transition") or P.style.get("transition") or {"type": "cut"}
            if isinstance(tr, str):
                tr = {"type": tr}
            if tr["type"] not in fx.TRANSITIONS:
                raise ValueError(f"shot {s['id']}: unknown transition {tr['type']!r}; options {sorted(fx.TRANSITIONS)}")
            s["_tr"] = tr
        self.texts = [KineticText(tx, P, self.u) if tx.get("kinetic") else TextItem(tx, P, self.u) for tx in P.texts]
        for s in P.shots:
            s["_mg"] = [MGLayer(m, self, s["_start"], s["_end"]) for m in (s.get("mg") or [])]
        self.global_mg = [MGLayer(m, self, P.t0, P.t1) for m in (P.style.get("mg") or [])]
        self.scene = SceneRenderer(self)

    def _prep_fx(self, e, start, end):
        e = dict(e)
        if "type" not in e:
            raise ValueError(f"effect without type: {e}")
        if "start" in e:
            start = self.P.T(e["start"])
        if "end" in e:
            end = self.P.T(e["end"])
        e["_start"], e["_end"] = start, end
        e["_trig"] = self.P.triggers(e, start, end)
        return e

    def _image(self, path, zmax, fit, crop=None):
        key = (path, round(zmax, 2), fit, tuple(crop) if crop else None)
        if key in self._img_cache:
            return self._img_cache[key]
        full = self.P.abspath(path)
        im = cv2.imread(full, cv2.IMREAD_UNCHANGED)
        if im is None:
            raise FileNotFoundError(f"cannot read image {full}")
        if im.ndim == 2:
            im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
        if im.dtype != np.uint8:
            im = (im / (65535.0 if im.dtype == np.uint16 else 1.0) * 255).astype(np.uint8)
        alpha = None
        if im.shape[2] == 4:
            alpha = im[..., 3:4].astype(np.float32) / 255.0
            im = im[..., :3]
        if crop:
            # crop: [x, y, w, h] normalised to the source image
            H0, W0 = im.shape[:2]
            x0, y0 = int(crop[0] * W0), int(crop[1] * H0)
            x1, y1 = int((crop[0] + crop[2]) * W0), int((crop[1] + crop[3]) * H0)
            im = im[max(0, y0):min(H0, y1), max(0, x0):min(W0, x1)]
            if alpha is not None:
                alpha = alpha[max(0, y0):min(H0, y1), max(0, x0):min(W0, x1)]
        rgb = cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        ih, iw = rgb.shape[:2]
        s0 = max(self.W / iw, self.H / ih) if fit == "cover" else min(self.W / iw, self.H / ih)
        r = min(1.0, s0 * zmax * 1.05)
        if r < 0.98:
            rgb = cv2.resize(rgb, (max(1, int(iw * r)), max(1, int(ih * r))), interpolation=cv2.INTER_AREA)
            if alpha is not None:
                alpha = cv2.resize(alpha, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_AREA)[..., None]
        out = (rgb, alpha)
        self._img_cache[key] = out
        return out

    # ------------------------------------------------------------- per frame
    def shot_frame(self, s, t, n):
        W, H, u = self.W, self.H, self.u
        P = self.P
        dur = max(1e-6, s["_end"] - s["_start"])
        p = (t - s["_start"]) / dur
        cam = s["_cam"]
        st = cam_mod.state(cam, p)
        for e in s["_fx"]:
            e["_env"] = fx.envelope(e, t, e["_trig"]) if e["_start"] - 0.5 <= t <= e["_end"] + 1 else 0.0
            if e["type"] == "rot_punch" and e["_trig"]:
                e["_flip"] = sum(1 for x in e["_trig"] if x <= t)
        dx, dy, zp, rp = fx.geometry(s["_fx"], t, u)
        if s.get("scene"):
            ctx = puppet.Ctx(P, s["_start"], s["_end"])
            frame = self.scene.render(s, t, n, ctx)
            if abs(dx) > 0.01 or abs(dy) > 0.01 or abs(zp - 1) > 1e-4 or abs(rp) > 0.01:
                frame = fx.warp(frame, W, H, zp, W / 2, H / 2, rp, dx, dy)
            for e in s["_fx"]:
                frame = fx.apply_pixel(frame, e, t, u, n)
            for m in s["_mg"]:
                frame = m.draw(frame, t, n)
            return frame
        fit = s.get("fit", "cover")
        zoom_vals = cam["zoom"] if not cam.get("keys") else [k.get("zoom", 1) for k in cam["keys"]]
        zmax = max(zoom_vals) * 1.15
        rot = st["rot"] + rp
        ctx = puppet.Ctx(P, s["_start"], s["_end"])
        z0 = cam["zoom"][0] if not cam.get("keys") else cam["keys"][0].get("zoom", 1)
        c0 = cam["center"][0] if not cam.get("keys") else cam["keys"][0].get("center", [0.5, 0.5])

        # character slot: real cutout if it exists, otherwise a placeholder box
        crop = s.get("crop")
        base_path = s["image"]
        layers = list(s.get("layers") or [])
        slot = s.get("char")
        placeholder = None
        if slot:
            cut = P.abspath(f"{P.meta.get('cutouts', 'cutouts')}/{slot['slot']}.png")
            cut_bg = cut[:-4] + "_bg.png"
            if os.path.exists(cut):
                if os.path.exists(cut_bg):
                    base_path = cut_bg
                layers.insert(0, {"image": cut, "parallax": slot.get("parallax", 1.12), "crop": crop,
                                  "puppet": slot.get("puppet")})
            else:
                placeholder = slot

        # base image -> frame
        rgb, alpha = self._image(base_path, zmax, fit, crop)
        bh, bw = rgb.shape[:2]
        base = max(W / bw, H / bh) if fit == "cover" else min(W / bw, H / bh)

        def cam_matrix(par):
            zoom = z0 * (st["zoom"] / z0) ** par * zp
            cx = (c0[0] + (st["cx"] - c0[0]) * par) * bw
            cy = (c0[1] + (st["cy"] - c0[1]) * par) * bh
            sc = base * zoom
            if fit == "cover":
                sc *= fx.cover_fix(W, H, rot) if abs(rot) > 0.01 else 1
                if cam.get("clamp", True) and par == 1.0:
                    cx, cy = fx.clamp_center(cx, cy, sc, bw, bh, W, H)
            return fx.affine(W, H, sc, cx, cy, rot, dx * par, dy * par), sc

        frame = None
        if fit == "contain" and s.get("bg_color"):
            frame = np.empty((H, W, 3), np.float32)
            frame[:] = np.array(fx.hex_rgb(s["bg_color"]), np.float32)
        elif fit == "contain":
            # blurred, darkened cover version behind a contained image
            crgb, _ = self._image(base_path, 1.0, "cover", crop)
            ih, iw = crgb.shape[:2]
            s_c = max(W / iw, H / ih) * 1.1
            back = fx.warp(crgb, W, H, s_c, iw / 2, ih / 2, 0, 0, 0)
            back = cv2.GaussianBlur(cv2.resize(back, (W // 8, H // 8)), (0, 0), 4)
            frame = cv2.resize(back, (W, H)) * float(s.get("bg_dim", 0.45))
        M, sc = cam_matrix(1.0)
        img = fx.warp_m(rgb, M, W, H, "reflect" if fit == "cover" else "black", sc)
        if frame is None:
            frame = img
            if alpha is not None:
                a = fx.warp_m(alpha, M, W, H, "black", sc)[..., None]
                frame = img * a + self.bg * (1 - a)
        else:
            a = fx.warp_m(np.ones((bh, bw), np.float32) if alpha is None else alpha, M, W, H, "black", sc)
            a = a[..., None] if a.ndim == 2 else a
            frame = frame * (1 - a) + img * a

        for L in layers:
            op = puppet.value(L.get("opacity"), t, ctx, 1.0)
            if op <= 0.002:
                continue
            par = float(L.get("parallax", 1.0))
            lzmax = zmax * max(1.0, par) * float(L.get("place", {}).get("height", 1.0)) * 1.2
            lrgb, lalpha = self._image(L["image"], lzmax, "cover", L.get("crop"))
            lh, lw = lrgb.shape[:2]
            if L.get("puppet"):
                tp = t
                step = int(L["puppet"].get("step", 1))
                if step > 1:
                    fn = int(round((t - s["_start"]) * P.fps))
                    tp = s["_start"] + (fn - fn % step) / P.fps
                lrgb, lalpha = puppet.deform(lrgb, lalpha, L["puppet"], tp, ctx)
            pl = L.get("place")
            if pl:
                k = float(pl.get("height", 1.0)) * bh / lh
                pc = pl.get("center", [0.5, 0.5])
                off = [puppet.value(v, t, ctx, 0.0) for v in pl.get("move", [0, 0])]
                Lm = np.array([[k, 0, (pc[0] + off[0]) * bw - k * lw / 2],
                               [0, k, (pc[1] + off[1]) * bh - k * lh / 2]], np.float32)
            else:
                Lm = np.array([[bw / lw, 0, 0], [0, bh / lh, 0]], np.float32)
            Mc, sc_l = cam_matrix(par)
            Mfull = fx.compose(Mc, Lm)
            limg = fx.warp_m(lrgb, Mfull, W, H, "black", sc_l * Lm[0, 0])
            la = fx.warp_m(np.ones((lh, lw), np.float32) if lalpha is None else lalpha, Mfull, W, H,
                           "black", sc_l * Lm[0, 0])
            la = (la[..., None] if la.ndim == 2 else la) * op
            frame = frame * (1 - la) + limg * la
        for e in s["_fx"]:
            frame = fx.apply_pixel(frame, e, t, u, n)
        for m in s["_mg"]:
            frame = m.draw(frame, t, n)
        if placeholder is not None and self.show_slots:
            frame = self._draw_slot(frame, placeholder, M, bw, bh, crop)
        if s.get("card"):
            frame = self._card(frame, s["card"], t, ctx, n)
        return frame

    def _draw_slot(self, frame, slot, M, bw, bh, crop):
        """Dashed box + tag where a character cutout will go (box is in source-image coords)."""
        bx, by, bwn, bhn = slot.get("box", [0.2, 0.1, 0.6, 0.85])
        if crop:  # source coords -> cropped coords
            bx, by = (bx - crop[0]) / crop[2], (by - crop[1]) / crop[3]
            bwn, bhn = bwn / crop[2], bhn / crop[3]
        pts = np.array([[bx, by], [bx + bwn, by], [bx + bwn, by + bhn], [bx, by + bhn]], np.float32)
        pts = pts * np.array([bw, bh], np.float32)
        pts = (pts @ M[:, :2].T) + M[:, 2]
        ov = np.zeros((self.H, self.W), np.uint8)
        th = max(1, int(2 * self.u))
        for i in range(4):
            a, b = pts[i], pts[(i + 1) % 4]
            L = float(np.hypot(*(b - a)))
            nseg = max(1, int(L / (18 * self.u)))
            for k in range(0, nseg, 2):
                p0 = a + (b - a) * (k / nseg)
                p1 = a + (b - a) * (min(nseg, k + 1) / nseg)
                cv2.line(ov, tuple(int(v) for v in p0), tuple(int(v) for v in p1), 255, th, cv2.LINE_AA)
        tag = f"CUTOUT {slot['slot']}"
        org = (int(max(4, min(pts[:, 0].min() + 6, self.W - 300 * self.u))), int(max(16 * self.u, pts[:, 1].min() + 18 * self.u)))
        cv2.putText(ov, tag, org, cv2.FONT_HERSHEY_SIMPLEX, 0.45 * self.u, 255, max(1, int(self.u)), cv2.LINE_AA)
        a = (ov.astype(np.float32) / 255.0)[..., None] * 0.85
        col = np.array([0.35, 0.95, 1.0], np.float32)
        return frame * (1 - a) + col * a

    def _card(self, frame, spec, t, ctx, n):
        """Floating 3D panel: the shot is projected on a tilted card over a blurred backdrop."""
        W, H = self.W, self.H
        scale = puppet.value(spec.get("scale", 0.82), t, ctx, 0.82)
        rx = math.radians(puppet.value(spec.get("rx", 0), t, ctx, 0.0))
        ry = math.radians(puppet.value(spec.get("ry", 0), t, ctx, 0.0))
        rz = math.radians(puppet.value(spec.get("rz", 0), t, ctx, 0.0))
        ox = puppet.value(spec.get("x", 0), t, ctx, 0.0) * W
        oy = puppet.value(spec.get("y", 0), t, ctx, 0.0) * H
        hw, hh = W / 2 * scale, H / 2 * scale
        P3 = np.array([[-hw, -hh, 0], [hw, -hh, 0], [hw, hh, 0], [-hw, hh, 0]], np.float64)
        cx_, sx_ = math.cos(rx), math.sin(rx)
        cy_, sy_ = math.cos(ry), math.sin(ry)
        cz_, sz_ = math.cos(rz), math.sin(rz)
        Rx = np.array([[1, 0, 0], [0, cx_, -sx_], [0, sx_, cx_]])
        Ry = np.array([[cy_, 0, sy_], [0, 1, 0], [-sy_, 0, cy_]])
        Rz = np.array([[cz_, -sz_, 0], [sz_, cz_, 0], [0, 0, 1]])
        P3 = P3 @ (Rz @ Ry @ Rx).T
        f = 1.6 * W
        dst = np.stack([P3[:, 0] * f / (f + P3[:, 2]) + W / 2 + ox, P3[:, 1] * f / (f + P3[:, 2]) + H / 2 + oy], 1)
        src = np.array([[0, 0], [W, 0], [W, H], [0, H]], np.float32)
        Hm = cv2.getPerspectiveTransform(src, dst.astype(np.float32))
        card = cv2.warpPerspective(frame, Hm, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        mask = cv2.warpPerspective(np.ones((H, W), np.float32), Hm, (W, H), flags=cv2.INTER_LINEAR)[..., None]
        bgmode = spec.get("bg", "blur")
        if bgmode == "blur":
            small = cv2.resize(frame, (W // 10, H // 10), interpolation=cv2.INTER_AREA)
            back = cv2.resize(cv2.GaussianBlur(small, (0, 0), 3), (W, H)) * float(spec.get("bg_dim", 0.35))
        else:
            back = np.empty_like(frame)
            back[:] = np.array(fx.hex_rgb(bgmode), np.float32)
        sh = cv2.GaussianBlur(mask, (0, 0), 25 * self.u)
        sh = np.roll(np.roll(sh, int(18 * self.u), 0), int(10 * self.u), 1)
        sh = sh[..., None] if sh.ndim == 2 else sh
        back = back * (1 - 0.6 * sh)
        out = back * (1 - mask) + card * mask
        if spec.get("border", True):
            edge = cv2.morphologyEx((mask[..., 0] > 0.5).astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
            out[edge > 0] = out[edge > 0] * 0.4 + 0.6
        return out

    def frame(self, n):
        P = self.P
        t = P.frame_time(n)
        s = P.shot_at(t)
        if s is None:
            f = np.empty((self.H, self.W, 3), np.float32)
            f[:] = self.bg
        else:
            f = self.shot_frame(s, t, n)
            # transitions are centred on cuts: check the cut at this shot's start and the next one
            idx = P.shots.index(s)
            for j in (idx, idx + 1):
                if j <= 0 or j >= len(P.shots):
                    continue
                a, b = P.shots[j - 1], P.shots[j]
                tr = b["_tr"]
                if tr["type"] == "cut":
                    continue
                d = _tr_dur(tr, P)
                cut = b["_start"]
                if cut - d / 2 <= t < cut + d / 2:
                    q = (t - (cut - d / 2)) / d
                    pf = f if j == idx + 1 else self.shot_frame(a, t, n)
                    nf = f if j == idx else self.shot_frame(b, t, n)
                    f = fx.transition(tr["type"], pf, nf, q, tr, self.u)
                    break
        for e in self.global_fx:
            e["_env"] = fx.envelope(e, t, e["_trig"]) if e["_start"] - 0.5 <= t <= e["_end"] + 1 else 0.0
            if e["type"] in fx.GEOMETRIC:
                continue
            f = fx.apply_pixel(f, e, t, self.u, n)
        for m in self.global_mg:
            f = m.draw(f, t, n)
        for tx in self.texts:
            f = tx.draw(f, t, P.T)
        return f

    def frame_u8(self, n):
        f = self.frame(n)
        return (np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8)


def _tr_dur(tr, P):
    d = tr.get("dur", 0.2)
    if isinstance(d, str) and d.endswith("b"):
        return float(d[:-1]) * P.T.beat_len
    return float(d)


# ----------------------------------------------------------------- workers

def _worker(args):
    project, scale, a, b, out, crf, preset = args
    R = Renderer(project, scale)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{R.W}x{R.H}", "-r", str(R.P.fps), "-i", "-",
           "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(a, b):
        proc.stdin.write(R.frame_u8(n).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    return b - a


def render_video(project, out, scale=1.0, t_from=None, t_to=None, jobs=None, crf=None, preset="medium"):
    R = Renderer(project, scale)
    P = R.P
    n0 = 0 if t_from is None else max(0, int(round((P.T(t_from) - P.t0) * P.fps)))
    n1 = P.nframes if t_to is None else min(P.nframes, int(round((P.T(t_to) - P.t0) * P.fps)))
    if n1 <= n0:
        raise SystemExit("empty range")
    jobs = jobs or min(os.cpu_count() or 2, 8)
    crf = crf or P.meta.get("crf", 18)
    tmp = tempfile.mkdtemp(prefix="madr_")
    chunk = math.ceil((n1 - n0) / jobs)
    tasks, parts = [], []
    for i in range(jobs):
        a, b = n0 + i * chunk, min(n1, n0 + (i + 1) * chunk)
        if a >= b:
            break
        part = os.path.join(tmp, f"part{i:03d}.mp4")
        parts.append(part)
        tasks.append((project, scale, a, b, part, crf, preset))
    t_start = time.time()
    if len(tasks) == 1:
        _worker(tasks[0])
    else:
        with Pool(len(tasks)) as pool:
            pool.map(_worker, tasks)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst]
    audio = P.abspath(P.meta.get("audio"))
    if audio and os.path.exists(audio):
        ss = P.t0 + n0 / P.fps
        dur = (n1 - n0) / P.fps
        cmd += ["-ss", f"{ss:.4f}", "-t", f"{dur:.4f}", "-i", audio]
        sfx = [x for x in (P.meta.get("sfx") or []) if ss - 10 <= P.T(x["at"]) <= ss + dur]
        if not sfx:
            cmd += ["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "256k", "-shortest"]
        else:
            # voice lines / sound effects over the song; the song ducks under each one
            fl, labels, duck = [], [], []
            for k, x in enumerate(sfx):
                cmd += ["-i", P.abspath(x["file"])]
                at = P.T(x["at"]) - ss
                a0, a1 = float(x.get("from", 0)), float(x.get("to", 0)) or None
                trim = f"atrim=start={a0}" + (f":end={a1}" if a1 else "") + ",asetpts=PTS-STARTPTS"
                fl.append(f"[{k + 2}:a]{trim},volume={float(x.get('gain', 1.0))},adelay={max(0, int(at * 1000))}:all=1[s{k}]")
                labels.append(f"[s{k}]")
                if a1:
                    L = a1 - a0
                else:
                    fd = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                                        P.abspath(x["file"])]).decode().strip())
                    L = fd - a0
                g = float(x.get("duck", 0.35))
                duck.append(f"volume=enable='between(t,{at - 0.05:.3f},{at + L + 0.1:.3f})':volume={g}")
            fl.append(f"[1:a]{','.join(duck)}[m]")
            fl.append(f"[m]{''.join(labels)}amix=inputs={len(labels) + 1}:normalize=0:duration=first[aout]")
            cmd += ["-filter_complex", ";".join(fl), "-map", "0:v", "-map", "[aout]", "-c:a", "aac", "-b:a", "256k"]
    cmd += ["-c:v", "copy", "-movflags", "+faststart", out]
    subprocess.check_call(cmd)
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    el = time.time() - t_start
    print(f"rendered {n1 - n0} frames ({(n1 - n0) / P.fps:.1f}s) at {R.W}x{R.H} in {el:.1f}s -> {out}")


def stills(project, times, outdir, scale=1.0):
    R = Renderer(project, scale)
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for tx in times:
        t = R.P.T(tx)
        n = int(round((t - R.P.t0) * R.P.fps))
        img = R.frame_u8(n)
        p = os.path.join(outdir, f"still_{str(tx).replace(':', '_')}.png")
        cv2.imwrite(p, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        paths.append(p)
    print("\n".join(paths))


def contact(project, out, cols=4, scale=0.25, where=0.5):
    R = Renderer(project, scale)
    P = R.P
    tiles = []
    for s in P.shots:
        t = s["_start"] + (s["_end"] - s["_start"]) * where
        n = int(round((t - P.t0) * P.fps))
        img = cv2.cvtColor(R.frame_u8(n), cv2.COLOR_RGB2BGR)
        label = f"{s['id']}  {s['_start']:.2f}-{s['_end']:.2f}s  {(s.get('camera') or {}).get('preset', 'static')}"
        bar = np.zeros((28, img.shape[1], 3), np.uint8)
        cv2.putText(bar, label, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(np.vstack([bar, img]))
    if not tiles:
        raise SystemExit("no shots")
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    sheet = np.vstack(rows)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    cv2.imwrite(out, sheet)
    print(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("-o", "--out")
    ap.add_argument("--preview", action="store_true", help="half resolution, faster encode")
    ap.add_argument("--scale", type=float)
    ap.add_argument("--from", dest="t_from")
    ap.add_argument("--to", dest="t_to")
    ap.add_argument("--still", nargs="+", help="times to export as PNG")
    ap.add_argument("--contact", action="store_true")
    ap.add_argument("--jobs", type=int)
    ap.add_argument("--crf", type=int)
    a = ap.parse_args(argv)
    root = os.path.dirname(os.path.abspath(a.project))
    P = Project(a.project)
    title = P.meta.get("title") or os.path.splitext(os.path.basename(a.project))[0]
    scale = a.scale or (0.5 if a.preview else 1.0)
    if a.still:
        return stills(a.project, a.still, a.out or os.path.join(root, "out", "stills"), scale)
    if a.contact:
        return contact(a.project, a.out or os.path.join(root, "out", "contact.png"))
    suffix = "_preview" if a.preview else ""
    out = a.out or os.path.join(root, "out", f"{title}{suffix}.mp4")
    render_video(a.project, out, scale, a.t_from, a.t_to, a.jobs, a.crf,
                 preset="veryfast" if a.preview else "medium")


if __name__ == "__main__":
    sys.exit(main())
