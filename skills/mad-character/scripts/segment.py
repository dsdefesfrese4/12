"""Split a manga character into flat-colour regions with SAM point prompts.

  python3 segment.py parts.yaml            # writes <out>/mask_<name>.png, flat.png, lines.png, preview.jpg

parts.yaml
  image: ../assets/layers/eyes_open/clean.png
  out: parts_open
  line_thresh: 0.45          # darker than this = ink line
  regions:                   # later entries win where masks overlap
    - {name: shirt, color: "#96a0ac", points: [[100, 1100]], neg: [[380, 950]]}
    - {name: skin,  color: "#efc4a0", points: [[330, 600], [420, 800]], neg: [[210, 500]]}
    - {name: hair,  color: "#1e1e26", points: [[100, 200]], box: [0, 0, 822, 600]}
    - {name: eye_L, color: "#4a4a50", points: [[210, 500]]}
  fill_unassigned: nearest   # pixels no region claimed (under lines) take the nearest region

Points are in source-image pixels (look at the image, pick a few clear points per region;
add `neg` points where SAM bleeds into a neighbour). Run, check preview.jpg, adjust, rerun.
Masks can also be painted/edited by hand: an existing mask_<name>_fix.png (white add, black
on alpha=0 ignored) is OR-ed in, mask_<name>_cut.png is subtracted.
"""
import os
import sys

import cv2
import numpy as np
import torch
import yaml

_SAM = None


def sam():
    global _SAM
    if _SAM is None:
        from transformers import SamModel, SamProcessor
        _SAM = (SamModel.from_pretrained("facebook/sam-vit-base").eval(),
                SamProcessor.from_pretrained("facebook/sam-vit-base"))
    return _SAM


def predict(img_rgb, points, neg=None, box=None, emb_cache={}):
    model, proc = sam()
    key = id(img_rgb)
    pts = [list(map(float, p)) for p in points] + [list(map(float, p)) for p in (neg or [])]
    labels = [1] * len(points) + [0] * len(neg or [])
    kw = {"input_points": [[pts]], "input_labels": [[labels]]}
    if box:
        kw["input_boxes"] = [[list(map(float, box))]]
    inputs = proc(img_rgb, return_tensors="pt", **kw)
    with torch.no_grad():
        if key not in emb_cache:
            emb_cache.clear()
            emb_cache[key] = model.get_image_embeddings(inputs["pixel_values"])
        emb = emb_cache[key]
        out = model(image_embeddings=emb, input_points=inputs["input_points"],
                    input_labels=inputs["input_labels"],
                    input_boxes=inputs.get("input_boxes"), multimask_output=True)
    masks = proc.image_processor.post_process_masks(out.pred_masks, inputs["original_sizes"],
                                                    inputs["reshaped_input_sizes"])[0][0]
    scores = out.iou_scores[0, 0]
    best = int(torch.argmax(scores))
    return masks[best].numpy().astype(np.uint8), float(scores[best])


def hex_bgr(c):
    c = c.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    return np.array([b, g, r], np.uint8)


def main():
    cfg_path = sys.argv[1]
    root = os.path.dirname(os.path.abspath(cfg_path))
    cfg = yaml.safe_load(open(cfg_path, encoding="utf-8"))
    src = cv2.imread(os.path.join(root, cfg["image"]), cv2.IMREAD_COLOR)
    out = os.path.join(root, cfg.get("out", "parts"))
    os.makedirs(out, exist_ok=True)
    H, W = src.shape[:2]
    rgb = cv2.cvtColor(src, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    label = np.full((H, W), -1, np.int32)
    regions = cfg["regions"]
    for i, r in enumerate(regions):
        m = np.zeros((H, W), np.uint8)
        if r.get("points"):
            m, score = predict(rgb, r["points"], r.get("neg"), r.get("box"))
            print(f"{r['name']:<12} score {score:.2f} area {m.mean() * 100:.1f}%")
        if r.get("poly"):
            for poly in r["poly"]:
                cv2.fillPoly(m, [np.int32(poly)], 1)
        if r.get("close"):
            k = int(r["close"])
            m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
        fix = os.path.join(out, f"mask_{r['name']}_fix.png")
        cut = os.path.join(out, f"mask_{r['name']}_cut.png")
        if os.path.exists(fix):
            m |= (cv2.imread(fix, cv2.IMREAD_GRAYSCALE) > 127).astype(np.uint8)
        if os.path.exists(cut):
            m &= (cv2.imread(cut, cv2.IMREAD_GRAYSCALE) <= 127).astype(np.uint8)
        if r.get("within"):
            j = [k for k, rr in enumerate(regions) if rr["name"] == r["within"]][0]
            m = (label == j).astype(np.uint8) if not m.any() else m & (label == j)
        if r.get("clip_poly"):
            cm = np.zeros((H, W), np.uint8)
            cv2.fillPoly(cm, [np.int32(r["clip_poly"])], 1)
            m &= cm
        if r.get("light_only"):
            m &= (gray > float(r["light_only"])).astype(np.uint8)
        if r.get("dark_only"):
            m &= (gray < float(r["dark_only"])).astype(np.uint8)
        label[m > 0] = i
    if cfg.get("fill_unassigned", "nearest") == "nearest":
        un = label < 0
        if un.any() and (~un).any():
            # nearest labelled pixel via distance transform on each label
            best_d = np.full((H, W), np.inf, np.float32)
            for i in range(len(regions)):
                mk = (label == i)
                if not mk.any():
                    continue
                d = cv2.distanceTransform((~mk).astype(np.uint8), cv2.DIST_L2, 5)
                upd = un & (d < best_d)
                label[upd] = i
                best_d[upd] = d[upd]
    flat = np.zeros((H, W, 3), np.uint8)
    for i, r in enumerate(regions):
        mk = label == i
        flat[mk] = hex_bgr(r["color"])
        cv2.imwrite(os.path.join(out, f"mask_{r['name']}.png"), mk.astype(np.uint8) * 255)
    th = float(cfg.get("line_thresh", 0.45))
    # line layer: ink darkness as alpha (keeps hatching and tone dots)
    ink = np.clip((th + 0.25 - gray) / 0.5, 0, 1)
    line_col = hex_bgr(cfg.get("line_color", "#1a1214"))
    lines = np.dstack([np.full((H, W, 3), line_col, np.uint8), (ink * 255).astype(np.uint8)])
    cv2.imwrite(os.path.join(out, "lines.png"), lines)
    cv2.imwrite(os.path.join(out, "flat.png"), flat)
    # per-region line tint (e.g. dirt / bruises on skin drawn in red-brown instead of black)
    line_map = np.zeros((H, W, 3), np.float32) + line_col
    for i, r in enumerate(regions):
        if r.get("line_color"):
            line_map[label == i] = hex_bgr(r["line_color"])
    lines = np.dstack([line_map.astype(np.uint8), (ink * 255).astype(np.uint8)])
    cv2.imwrite(os.path.join(out, "lines.png"), lines)
    a = ink[..., None]
    comp = (flat * (1 - a) + line_map * a).astype(np.uint8)
    cv2.imwrite(os.path.join(out, "colored.png"), comp)
    np.save(os.path.join(out, "labels.npy"), label)
    prev = np.hstack([src, (flat * 0.6 + src * 0.4).astype(np.uint8), comp])
    cv2.imwrite(os.path.join(out, "preview.jpg"), prev)
    print("->", out)


if __name__ == "__main__":
    sys.exit(main())
