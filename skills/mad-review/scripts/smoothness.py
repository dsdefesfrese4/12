"""Frame-by-frame motion analysis: find stutters in a MAD / static-MAD render.

  python3 smoothness.py video.mp4 [--from 0 --to 10] [--plot out.png] [--json out.json]

For every pair of consecutive frames it estimates the global camera motion
(translation, zoom, rotation) with ORB features + RANSAC, then flags:
  POP     one-frame spike: speed jumps up and straight back down (keyframe pop / time-remap glitch)
  JERK    speed changes by a large factor between two frames (velocity discontinuity,
          usually linear keyframes or mismatched ease handles)
  REVERSE direction flips within one frame without slowing down
  HOLD    motion stops dead for a frame inside a move (duplicate frame / dropped frame)
Cuts (scene changes) are detected and excluded.
"""
import argparse
import json
import sys

import cv2
import numpy as np


def analyze(path, t_from=0.0, t_to=None, width=960):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    orb = cv2.ORB_create(3000)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    rows, prev, prev_g, i = [], None, None, -1
    scale = None
    while True:
        ok, f = cap.read()
        if not ok:
            break
        i += 1
        t = i / fps
        if t < t_from or (t_to is not None and t > t_to):
            continue
        if scale is None:
            scale = f.shape[1] / width
        g = cv2.cvtColor(cv2.resize(f, (width, int(f.shape[0] / scale))), cv2.COLOR_BGR2GRAY)
        kp, des = orb.detectAndCompute(g, None)
        row = {"frame": i, "t": round(t, 3), "dx": 0.0, "dy": 0.0, "zoom": 0.0, "rot": 0.0,
               "speed": 0.0, "cut": False, "diff": 0.0}
        if prev is not None:
            row["diff"] = float(np.abs(g.astype(np.float32) - prev_g).mean())
            if des is None or prev[1] is None or len(kp) < 30:
                row["cut"] = row["diff"] > 25
            else:
                m = bf.match(prev[1], des)
                if len(m) < 25:
                    row["cut"] = True
                else:
                    a = np.float32([prev[0][x.queryIdx].pt for x in m])
                    b = np.float32([kp[x.trainIdx].pt for x in m])
                    M, inl = cv2.estimateAffinePartial2D(a, b, ransacReprojThreshold=2.0)
                    if M is None or inl.sum() < 20:
                        row["cut"] = True
                    else:
                        s = float(np.hypot(M[0, 0], M[1, 0]))
                        row.update(dx=float(M[0, 2] * scale), dy=float(M[1, 2] * scale),
                                   zoom=100 * (s - 1), rot=float(np.degrees(np.arctan2(M[1, 0], M[0, 0]))))
                        # zoom/rotation expressed as pixel motion at the frame corner
                        half = np.hypot(f.shape[1], f.shape[0]) / 2
                        row["speed"] = float(np.hypot(row["dx"], row["dy"]) + abs(s - 1) * half
                                             + abs(np.radians(row["rot"])) * half)
                        if row["speed"] > 0.25 * half or abs(s - 1) > 0.3:
                            row["cut"] = True  # hard cut that still matched some features
                            row["speed"] = 0.0
        rows.append(row)
        prev, prev_g = (kp, des), g.astype(np.float32)
    return fps, rows


def flag(rows, min_speed=2.0, jerk_ratio=2.2, pop_ratio=2.0):
    issues = []
    sp = [r["speed"] for r in rows]
    for k in range(1, len(rows) - 1):
        r, a, b = rows[k], rows[k - 1], rows[k + 1]
        if r["cut"] or a["cut"] or b["cut"]:
            continue
        s, sa, sb = sp[k], sp[k - 1], sp[k + 1]
        if s > min_speed * 2 and s > pop_ratio * max(sa, 0.5) and s > pop_ratio * max(sb, 0.5):
            issues.append(("POP", r, f"speed {sa:.1f} -> {s:.1f} -> {sb:.1f} px/frame"))
            continue
        if max(s, sa) > min_speed * 2 and max(s, sa) / max(min(s, sa), 0.5) > jerk_ratio:
            issues.append(("JERK", r, f"speed {sa:.1f} -> {s:.1f} px/frame"))
            continue
        va, vb = np.array([a["dx"], a["dy"]]), np.array([r["dx"], r["dy"]])
        if np.linalg.norm(va) > min_speed * 1.5 and np.linalg.norm(vb) > min_speed * 1.5 and \
                np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)) < -0.3:
            issues.append(("REVERSE", r, f"({a['dx']:.1f},{a['dy']:.1f}) -> ({r['dx']:.1f},{r['dy']:.1f})"))
            continue
        if s < 0.3 and sa > min_speed * 1.5 and sb > min_speed * 1.5:
            issues.append(("HOLD", r, f"speed {sa:.1f} -> {s:.1f} -> {sb:.1f}"))
    return issues


def plot(rows, issues, out):
    W, H, pad = 1400, 420, 50
    img = np.full((H, W, 3), 255, np.uint8)
    sp = np.array([r["speed"] for r in rows])
    if len(sp) < 2:
        return
    mx = max(5.0, sp.max() * 1.1)
    xs = pad + (np.arange(len(sp)) / (len(sp) - 1)) * (W - 2 * pad)
    ys = H - pad - sp / mx * (H - 2 * pad)
    for v in range(0, int(mx) + 1, max(1, int(mx / 6))):
        y = int(H - pad - v / mx * (H - 2 * pad))
        cv2.line(img, (pad, y), (W - pad, y), (230, 230, 230), 1)
        cv2.putText(img, str(v), (5, y + 4), 0, 0.4, (120, 120, 120), 1)
    pts = np.int32(np.stack([xs, ys], 1))
    cv2.polylines(img, [pts], False, (180, 90, 20), 2, cv2.LINE_AA)
    idx = {r["frame"]: k for k, r in enumerate(rows)}
    colors = {"POP": (0, 0, 220), "JERK": (0, 140, 255), "REVERSE": (180, 0, 180), "HOLD": (0, 160, 0)}
    for kind, r, _ in issues:
        k = idx[r["frame"]]
        cv2.circle(img, tuple(pts[k]), 7, colors[kind], 2)
        cv2.putText(img, f"{kind} {r['t']:.2f}s", (int(pts[k][0]) + 8, int(pts[k][1]) - 8), 0, 0.45, colors[kind], 1)
    for k, r in enumerate(rows):
        if r["cut"]:
            cv2.line(img, (int(xs[k]), pad), (int(xs[k]), H - pad), (200, 200, 200), 1)
    cv2.putText(img, "camera speed (px/frame); grey lines = cuts", (pad, 25), 0, 0.55, (60, 60, 60), 1)
    cv2.imwrite(out, img)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--from", dest="t_from", type=float, default=0.0)
    ap.add_argument("--to", dest="t_to", type=float)
    ap.add_argument("--plot")
    ap.add_argument("--json")
    ap.add_argument("--beats", help="beats.json: flags within 1 frame of a beat are marked as intended hits")
    ap.add_argument("--offset", type=float, default=0.0, help="song time of the video's first frame")
    ap.add_argument("--project", help="project.yaml: flags within a shot's transition / first 0.3s are marked as cuts")
    a = ap.parse_args()
    fps, rows = analyze(a.video, a.t_from, a.t_to)
    issues = flag(rows)
    moving = [r["speed"] for r in rows if not r["cut"] and r["speed"] > 0.5]
    print(f"{a.video}: {len(rows)} frames @ {fps:.3f} fps, cuts {sum(r['cut'] for r in rows)}, "
          f"median speed {np.median(moving) if moving else 0:.1f} px/frame")
    beat_t = []
    if a.beats:
        with open(a.beats) as f:
            bj = json.load(f)
        beat_t = [b - a.offset for b in bj.get("beats", [])]
    def on_beat(t):
        return any(-1.5 / fps <= t - b <= 1.5 / fps for b in beat_t)
    cut_t = []
    if a.project:
        import yaml
        pj = yaml.safe_load(open(a.project, encoding="utf-8"))
        st0 = float((pj.get("meta") or {}).get("start", 0) or 0)
        for sh in pj.get("shots", []):
            if isinstance(sh.get("start"), (int, float)):
                cut_t.append(float(sh["start"]) - (a.offset if a.offset else st0))
    def near_cut(t):
        return any(-0.15 <= t - c <= 0.35 for c in cut_t)
    real = [(k, r, m) for k, r, m in issues if not on_beat(r["t"]) and not near_cut(r["t"])]
    hits = [(k, r, m) for k, r, m in issues if on_beat(r["t"]) or near_cut(r["t"])]
    print(f"SUMMARY: {len(real)} unexplained stutters, {len(hits)} on beats/cuts (intended)")
    for kind, r, msg in issues:
        tag = "  (beat hit / cut)" if (kind, r, msg) in hits else ""
        print(f"  {kind:<8} frame {r['frame']:4d}  {r['t']:6.2f}s  {msg}{tag}")
    if a.plot:
        plot(rows, issues, a.plot)
        print("plot ->", a.plot)
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"fps": fps, "rows": rows, "issues": [(k, r["frame"], m) for k, r, m in issues]}, f, indent=1)


if __name__ == "__main__":
    sys.exit(main())
