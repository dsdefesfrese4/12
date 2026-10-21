"""First-pass character cutouts for every character slot (rembg isnet-anime).

  python3 auto_cutout.py project_dir slot1 slot2 ...   (slot = panel id; image found in panels/ or pages/)

Writes cutouts_auto/<slot>.png (RGBA), cutouts_auto/<slot>_mask.png and cutouts_auto/boxes.json
(normalised bbox of the character, used to place placeholders). These are drafts: they are NOT
picked up by the renderer until copied/refined into cutouts/.
"""
import json, os, sys
import cv2, numpy as np
from rembg import new_session, remove

root = sys.argv[1]
slots = sys.argv[2:]
out = os.path.join(root, "cutouts_auto")
os.makedirs(out, exist_ok=True)
bp = os.path.join(out, "boxes.json")
boxes = json.load(open(bp)) if os.path.exists(bp) else {}
sess = new_session("isnet-anime")
for s in slots:
    if s in boxes and os.path.exists(os.path.join(out, s + ".png")):
        continue
    p = os.path.join(root, "panels", s + ".png")
    if not os.path.exists(p):
        p = os.path.join(root, "pages", s + ".jpg")
    im = cv2.imread(p, cv2.IMREAD_COLOR)
    rgba = np.asarray(remove(cv2.cvtColor(im, cv2.COLOR_BGR2RGB), session=sess, post_process_mask=True))
    a = rgba[..., 3]
    H, W = a.shape
    ys, xs = np.nonzero(a > 128)
    if len(xs) < 0.01 * H * W:
        box = [0.15, 0.08, 0.7, 0.9]
    else:
        box = [xs.min() / W, ys.min() / H, (xs.max() - xs.min()) / W, (ys.max() - ys.min()) / H]
    boxes[s] = [round(float(v), 4) for v in box]
    cv2.imwrite(os.path.join(out, s + "_mask.png"), a)
    cv2.imwrite(os.path.join(out, s + ".png"), np.dstack([im, a]))
    print(s, boxes[s], flush=True)
    json.dump(boxes, open(bp, "w"), indent=1)
