"""v2 — 章鱼噼的原罪 × 唯死以解脱  (style: oppressive, from style.json)

Three parts (user-defined):
  Part 1  0:00–1:47   Shizuka's world -> node: Marina's death. 谁言语淬毒 = "ありがとう タコピー" (voice),
                      封锁我歌喉 = second voice line + flash-cuts of Marina's death. 1:47.3 music stop = 原罪 title page.
  Part 2  1:49–2:59   Marina's first loop (2022).
  Part 3  2:59–3:51   Back to 2016 -> Shizuka's suicide on "唯 死以解脱".
No Chinese on-screen text. Japanese only, sparse, Mincho, faint.
"""
import json
import math
import os

import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
STYLE = json.load(open(os.path.join(ROOT, "style.json"), encoding="utf-8"))
LIM = STYLE["limits"]
EF = LIM["effects"]
FONT_Q = "assets/fonts/" + LIM["typography"]["fonts"]["quiet"]
FONT_H = "assets/fonts/" + LIM["typography"]["fonts"]["heavy"]
TXT_COL = LIM["typography"]["color"]

PALETTES = {  # per part, inside the oppressive palette
    1: {"shadow": "#060606", "mid": "#55524b", "highlight": "#e2dccf"},
    2: {"shadow": "#040608", "mid": "#47504f", "highlight": "#d9dfdc"},
    3: {"shadow": "#070504", "mid": "#5a4d3b", "highlight": "#e8dcc4"},
}
ACCENT = LIM["palette"]["accent"]
FLASHES = []

SHOTS = []
TEXTS = []


def part_of(t):
    return 1 if t < 108.9 else (2 if t < 179.0 else 3)


def img(pid):
    c = os.path.join(ROOT, "panels_clean", pid + ".png")
    if os.path.exists(c):
        return f"panels_clean/{pid}.png"
    p = os.path.join(ROOT, "panels", pid + ".png")
    return f"panels/{pid}.png" if os.path.exists(p) else f"pages/{pid}.jpg"


def aspect(pid, crop=None):
    import cv2
    im = cv2.imread(os.path.join(ROOT, img(pid)))
    h, w = im.shape[:2]
    if crop:
        w, h = w * crop[2], h * crop[3]
    return h / w


def fill_width(dist, fov=40, margin=1.12, asp=None):
    vis_w = 2 * dist * math.tan(math.radians(fov) / 2) * 16 / 9
    vis_h = 2 * dist * math.tan(math.radians(fov) / 2)
    w = vis_w * margin
    if asp is not None and w * asp < vis_h * margin:
        w = vis_h * margin / asp
    return w


def base_scene(bg="#020202", fog=0.05, focus=10, aperture=1.4, light_dir=(0.35, -0.55, 1.0), ambient=0.86, light="#ece6da"):
    return {"bg": bg, "fov": 40, "fog": {"color": "#030303", "density": fog * 0.45},
            "dof": {"focus": focus, "aperture": aperture},
            "light": {"dir": list(light_dir), "color": light, "ambient": ambient}, "layers": []}


def dust(vol=((-7, 7), (-4, 4), (1.5, 11)), preset="dust", count=None, opacity=None, speed=1.0):
    p = {"kind": "particles", "preset": preset if preset in EF["particles"] else "dust", "volume": [list(v) for v in vol],
         "opacity": opacity if opacity is not None else EF["particle_opacity"], "speed": speed}
    if count:
        p["count"] = count
    return p


def creep(pid, t, *, crop=None, slot=None, z=10.0, push=0.45, drift=(0.15, 0.0), dutch=(0.0, 0.0), look=(0, 0),
          rise=0.0, fog=0.05, extra=None, particles=True, aperture=1.4, light_dir=(0.35, -0.55, 1.0), note=""):
    """Default oppressive move: a slow creeping push toward a plate, parallax from dust in front."""
    asp = aspect(pid, crop)
    sc = base_scene(fog=fog, focus=z, aperture=aperture, light_dir=light_dir)
    w = fill_width(z, asp=asp)
    plate = {"kind": "image", "src": img(pid), "pos": [0, 0, z], "width": round(w, 3)}
    if crop:
        plate["crop"] = crop
    sc["layers"].append(plate)
    if slot:
        sw = w * (z - 0.6) / z
        sl = {"kind": "slot", "slot": slot, "pos": [0, 0, z - 0.6], "width": round(sw, 3)}
        if crop:
            sl["crop"] = crop
        sc["layers"].append(sl)
    if particles:
        sc["layers"].append(dust())
    for L in (extra or []):
        sc["layers"].append(L)
    sc["camera"] = {"keys": [
        {"at": 0, "pos": [-drift[0], -drift[1] + look[1] - rise / 2, 0.0], "look": [look[0], look[1], z], "roll": dutch[0]},
        {"at": 1, "pos": [drift[0], drift[1] + look[1] + rise / 2, push * z / 10 * 2], "look": [look[0] * 0.9, look[1] + rise * 0.3, z],
         "roll": dutch[1], "ease": "sine"}], "handheld": LIM["camera"]["handheld"]}
    return shot(t, sc, note=note)


def floor(pid, t, *, crop=None, slot=None, height=(7.5, 5.8), extra=None, note=""):
    """Plate lying on the ground; the camera looks straight down and cranes slowly lower."""
    asp = aspect(pid, crop)
    sc = base_scene(fog=0.03, focus=height[1], aperture=1.2, light_dir=(0.2, -1.0, 0.25), ambient=0.55)
    w = fill_width(height[0], asp=asp, margin=1.35)
    plate = {"kind": "image", "src": img(pid), "pos": [0, 0, 0], "width": round(w, 3), "rot": [-90, 0, 0]}
    if crop:
        plate["crop"] = crop
    sc["layers"].append(plate)
    if slot:
        sl = {"kind": "slot", "slot": slot, "pos": [0, 0.15, 0], "width": round(w, 3), "rot": [-90, 0, 0]}
        if crop:
            sl["crop"] = crop
        sc["layers"].append(sl)
    sc["layers"].append(dust(vol=((-5, 5), (0.3, 7), (-4, 4)), preset="ash", speed=0.6))
    for L in (extra or []):
        sc["layers"].append(L)
    sc["camera"] = {"keys": [{"at": 0, "pos": [0.0, height[0], -0.01], "look": [0, 0, 0], "roll": 4},
                             {"at": 1, "pos": [0.05, height[1], 0.0], "look": [0, 0, 0], "roll": 9, "ease": "sine"}],
                    "handheld": LIM["camera"]["handheld"]}
    return shot(t, sc, note=note)


def corridor(items, t, *, spacing=4.5, start_z=6, note="", frame="border", dolly=None):
    """Framed panels hanging in darkness at increasing depth; the camera drifts forward past them."""
    sc = base_scene(fog=0.06, focus=start_z + 2, aperture=1.8, ambient=0.5)
    for i, (pid, side) in enumerate(items):
        asp = aspect(pid)
        w = 3.4 if asp < 1 else 2.4
        sc["layers"].append({"kind": "image", "src": img(pid), "frame": frame, "pos": [side * 1.9, 0.15 * (-1) ** i, start_z + i * spacing],
                             "width": w, "rot": [0, -side * 22, side * 2]})
    sc["layers"].append(dust(vol=((-6, 6), (-3, 3), (0.5, start_z + len(items) * spacing))))
    dz = dolly or spacing * (len(items) - 0.8)
    sc["camera"] = {"keys": [{"at": 0, "pos": [0, 0, 0], "look": [0, 0, start_z + 4], "roll": -2},
                             {"at": 1, "pos": [0.1, 0.05, dz], "look": [0, 0, start_z + 4 + dz], "roll": 2, "ease": "sine"}],
                    "handheld": LIM["camera"]["handheld"]}
    sc["dof"]["focus"] = {"from": start_z, "to": start_z + dz * 0.7}
    return shot(t, sc, note=note)


def void(t, layers, cam, note="", fog=0.08):
    sc = base_scene(fog=fog, focus=8, aperture=1.6)
    sc["layers"] = layers
    sc["camera"] = cam
    return shot(t, sc, note=note)


def flat(pid, t, cam="push_in", note="", crop=None):
    sh = {"start": t, "image": img(pid), "camera": {"preset": cam} if isinstance(cam, str) else cam, "note": note}
    if crop:
        sh["crop"] = crop
    SHOTS.append(sh)
    return sh


def shot(t, scene, note=""):
    sh = {"start": t, "scene": scene, "note": note}
    SHOTS.append(sh)
    return sh


def text(t0, t1, s, *, pos=(0.82, 0.5), size=46, vertical=True, font=FONT_Q, kin_in="blur_in", kin_out="blur", stagger=0.08,
         opacity=None):
    TEXTS.append({"start": t0, "end": t1, "text": s, "pos": list(pos), "size": size, "vertical": vertical, "font": font,
                  "color": TXT_COL, "stroke": {"width": 0},
                  "kinetic": {"in": kin_in, "out": kin_out, "idle": "none", "stagger": stagger, "in_dur": 0.9, "out_dur": 0.7,
                              "tracking": 0.35, "shadow": {"color": "#000000", "offset": [0, 0], "blur": 10, "opacity": 0.8}}})


def ribbon(top=(0.4, 4.2, 6.0), length=(3.0, 3.0), sway=0.12, width=0.055):
    return {"kind": "ribbon", "pos": list(top), "length": {"from": length[0], "to": length[1]}, "width": width, "sway": sway,
            "color": "#8a1a22", "twist": 7}


def words_ja(center=(0, 0, 9), count=9, opacity=0.3):
    return {"kind": "words", "layout": "cloud", "words": ["しね", "どろぼう", "寄生虫", "ゴミ", "くさい", "きもい"], "count": count,
            "volume": [[-4.5, 4.5], [-2.4, 2.4], [center[2] - 2.5, center[2] - 0.5]], "size": 150, "color": "#bdb6aa",
            "height": 0.55, "opacity": opacity, "font": FONT_Q, "light": False}


# =========================================================================== PART 1
creep("c1_p03_p02", 0.0, z=14, push=0.25, fog=0.09, note="宇宙：飞船在黑暗深处，缓慢逼近（黑场渐显）",
      extra=[dust(vol=((-9, 9), (-5, 5), (2, 20)), preset="dust", count=420, opacity=0.25, speed=0.2)])
creep("c1_p26_p01", 6.80, slot="c1_p26_p01", z=10, push=0.35, rise=-2.4, look=(0, 0.9), dutch=(-1, 1),
      note="银河下的静香与查比：从星空缓慢下摇到人物")
corridor([("c1_p05_p02", -1), ("c1_p06_p02", 1), ("c1_p17_p01", -1)], 12.82, note="悬在黑暗里的三格回忆，镜头缓慢穿行（面包/闭眼/查比）")
creep("c1_p21_p04", 17.30, slot="c1_p21_p04", z=9, push=0.4, dutch=(0, -2), note="夜路“一起来玩”")
void(20.32, [dust(vol=((-7, 7), (-4, 4), (1, 14)), count=160, opacity=0.25, speed=0.3)],
     {"keys": [{"at": 0, "pos": [0, 0, 0], "look": [0, 0, 10]}, {"at": 1, "pos": [0, 0, 0.6], "look": [0, 0, 10]}]},
     note="标题：タコピーの原罪 / 2016年のきみへ")
text(20.9, 24.6, "タコピーの原罪", pos=(0.5, 0.47), size=74, font=FONT_H, stagger=0.14)
text(21.9, 24.6, "２０１６年のきみへ", pos=(0.58, 0.55), size=26, stagger=0.06)
creep("c2_p02_p01", 24.80, slot="c2_p02_p01", z=10, push=0.4, dutch=(2, 4), extra=[words_ja()],
      note="教室·被涂鸦的课桌；看不清的恶意字样（しね/どろぼう…）浮在空气里")
creep("c2_p03_p01", 30.81, slot="c2_p03_p01", z=9, push=0.55, dutch=(-3, -6), look=(0.5, 0.4), note="真理奈的笑，荷兰角越来越斜")
creep("c1_p27_p01", 36.78, slot="c1_p27_p01", z=10, push=0.2, rise=3.0, look=(0, -1.2), light_dir=(0.1, -1, 0.4),
      note="满身伤痕的静香：从脚缓慢升到脸，顶光")
creep("c1_p20_p01", 42.84, slot="c1_p20_p01", z=9, push=0.3, drift=(0.4, 0), note="深夜抱着查比——第一部分唯一的一点余温",
      extra=[{"kind": "glow", "pos": [-0.8, -0.3, 8.6], "width": 5, "color": "#3a2a1c"}])
# 谁笑着 / 似哭了 / 挣扎着 / 麻木了  — four faces surface one by one out of the dark
faces = [("c1_p17_p04", 47.32, (-2.2, 1.0, 9.5)), ("c3_p11_p01", 49.12, (2.0, 0.9, 10.5)),
         ("c3_p13_p04", 50.38, (-1.9, -1.2, 10.0)), ("c3_p20_p02", 52.42, (2.1, -1.1, 9.0))]
lay = []
for pid, ta, p in faces:
    lay.append({"kind": "image", "src": img(pid), "frame": "border", "pos": list(p), "width": 3.2, "rot": [0, -p[0] * 6, p[0] * 1.2],
                "opacity": {"keys": [[ta - 0.05, 0], [ta + 0.6, 1]], "ease": "ease_out"}})
lay.append(dust())
void(47.32, lay, {"keys": [{"at": 0, "pos": [0, 0, 2.5], "look": [0, 0, 10]}, {"at": 1, "pos": [0, 0, -1.0], "look": [0, 0, 10], "ease": "sine"}],
                  "handheld": 0.015}, note="谁笑着/似哭了/挣扎着/麻木了：四张脸逐个从黑暗里浮现，镜头缓慢后退")
creep("c4_p13_p01", 53.88, slot="c4_p13_p01", z=8.5, push=0.5, dutch=(4, 6), note="真理奈的嘶喊；暗红血迹在前景缓慢扩散",
      extra=[{"kind": "blood", "seed": 4, "pos": [1.6, -1.6, 5.5], "width": {"from": 1.5, "to": 2.6}, "opacity": 0.55, "light": False}])
creep("c3_p33_p01", 59.52, slot="c3_p33_p01", z=11, push=0.25, rise=-2.0, look=(0, 0.8), fog=0.07,
      extra=[{"kind": "strings", "top": 9, "targets": [[-0.35, 0.6, 10.3], [0.25, 0.5, 10.3], [-0.6, -0.8, 10.3], [0.55, -0.9, 10.3]],
              "color": "#cfc8bc", "opacity": 0.45, "width": 0.008, "sway": 0.04}],
      note="麻木地行走着不如木偶：走进森林的两人，头顶垂下细细的提线，镜头沿线缓慢下降")
creep("c4_p02_p01", 64.34, z=9, push=0.4, dutch=(-2, -5), fog=0.07, note="不予借口辩驳：黑暗森林里的真理奈")
creep("c4_p06_p02", 69.80, z=8, push=0.35, fog=0.05, note="绝望的藤蔓生于指尖交错：黑色荆棘从画面边缘缓慢长进来（1:11 副歌）",
      extra=[{"kind": "vines", "pos": [0, -0.2, 5.6], "width": 10, "aspect": 0.62, "grow": {"from": 0.0, "to": 0.75, "ease": "ease_in_out"},
              "seed": 3, "branches": 6, "origins": [[0.0, 1.0, -50], [1.0, 1.0, -130], [0.0, 0.2, 10], [1.0, 0.3, 170]], "light": False},
             {"kind": "vines", "pos": [-1.6, 0.4, 2.6], "width": 4.5, "aspect": 1.1, "grow": {"from": 0.2, "to": 0.9},
              "seed": 11, "branches": 3, "origins": [[0.0, 1.0, -40], [0.0, 0.6, -15]], "light": False}])
floor("c4_p11_p02", 74.30, height=(7.2, 5.4), note="逐渐吞噬不堪重负的躯壳：倒地的静香平躺在地面，俯拍缓慢下压，荆棘爬过",
      extra=[{"kind": "vines", "pos": [0, 0.05, 0], "rot": [-90, 0, 0], "width": 9, "aspect": 0.7, "grow": {"from": 0.3, "to": 1.0},
              "seed": 21, "branches": 7, "origins": [[0.0, 0.5, 0], [1.0, 0.5, 180], [0.5, 1.0, -90]], "light": False}])
creep("c4_p13_p02", 80.32, z=8.5, push=0.45, note="章鱼噼“鼓起勇气啊”")
creep("c4_p14_p01", 83.48, z=9, push=0.4, dutch=(0, 3), note="嘶吼着试图驱逐心里的魔：章鱼噼举起照相机",
      extra=[{"kind": "glow", "pos": [0.9, 0.7, 8.4], "width": 3, "color": "#3c3428"}])
void(86.31, [{"kind": "image", "src": img("c1_p42_p04"), "frame": "border", "pos": [0, 0, 9], "width": 4.2, "rot": [4, -10, 1]},
             dust(), {"kind": "glow", "pos": [0.4, 0.3, 9.5], "width": 6, "color": "#2a2620"}],
     {"keys": [{"at": 0, "pos": [-0.6, 0.2, 0], "look": [0, 0, 9]}, {"at": 1, "pos": [0.3, 0.0, 3.2], "look": [0, 0, 9], "roll": 3, "ease": "sine"}],
      "handheld": 0.015}, note="殊不知灵魂早已被妖魔胁迫：黑暗中漂浮的快乐照相机，镜头缓慢逼近")
text(87.4, 91.6, "ハッピーカメラ", pos=(0.16, 0.5), size=34, stagger=0.07)
creep("c4_p14_p01", 92.31, crop=[0.45, 0.0, 0.55, 0.7], z=8, push=0.55, dutch=(3, 6), note="照相机举起（裁到章鱼噼）——闪烁加重")
creep("c4_p15_p02", 95.60, z=8, push=0.1, particles=False, note="★“咚”——全片第一次闪白")
FLASHES.append(95.60)
floor("c4_p17_p01", 97.40, slot="c4_p17_p01", height=(6.8, 5.6), note="不得的自由：倒地的真理奈，俯拍；血迹在身下慢慢扩散",
      extra=[{"kind": "blood", "seed": 8, "pos": [0.3, 0.02, -0.4], "rot": [-90, 0, 0], "width": {"from": 1.0, "to": 3.6}, "opacity": 0.7, "light": False}])
creep("c4_p25_p01", 99.82, slot="c4_p25_p01", z=9, push=0.3, look=(0, 0.6), note="谁言语淬毒：闭眼笑——原片语音「ありがとう タコピー」")
text(100.30, 102.75, "ありがとう　タコピー", pos=(0.84, 0.5), size=44, stagger=0.06)
creep("c4_p26_p01", 102.82, slot="c4_p26_p01", z=9, push=0.5, look=(0, 0.6), note="封锁我歌喉：睁眼——第二句原片语音")
# flash-cut montage of Marina's death, one beat each, hard cuts
for k, (pid, crop) in enumerate([("c4_p23_p01", None), ("c4_p19_p01", None), ("c4_p17_p02", None), ("c4_p21_p01", [0, 0, 1, 0.6]),
                                 ("c4_p23_p01", [0.2, 0.4, 0.6, 0.6]), ("c4_p26_p01", [0.1, 0.25, 0.8, 0.5]), ("c4_p17_p01", None),
                                 ("c4_p19_p01", [0.2, 0.2, 0.6, 0.6])]):
    sh = flat(pid, round(104.30 + k * 0.372, 3), cam={"zoom": [1.08, 1.12], "ease": "linear"}, crop=crop,
              note="真理奈之死 闪切" if k == 0 else "")
    sh["montage"] = True
flat("c4_p29_p01", 107.30, cam={"zoom": [1.0, 1.0]}, note="■音乐骤停：原罪 标题页，完全静止")

# =========================================================================== PART 2  (Marina, first loop, 2022)
creep("c11_p18_p01", 108.96, crop=[0.0, 0.0, 0.62, 1.0], slot="c11_p18_p01", z=9, push=0.35, look=(0, 0.3), note="第二部分：2022年 真理奈")
text(109.6, 114.3, "２０２２年のきみへ", pos=(0.16, 0.42), size=30, stagger=0.06)
text(110.6, 114.3, "雲母坂まりな", pos=(0.12, 0.5), size=40)
creep("c12_p02_p01", 115.12, slot="c12_p02_p01", z=10, push=0.35, rise=-1.8, look=(0, 0.6), dutch=(-2, -4), note="于人前故作淡漠：带着伤疤走进学校")
creep("c12_p04_p01", 120.62, crop=[0, 0, 1, 0.56], z=9, push=0.25, fog=0.06, note="狂奔着捂住耳朵：家里酗酒的母亲（静止般的压迫）")
creep("c12_p12_p01", 124.08, crop=[0, 0, 1, 0.62], slot="c12_p12_p01", z=9, push=0.3, note="奢求就此逃脱：直树——隔着笼栅的一点光",
      extra=[{"kind": "cage", "pos": [0, 0, 3.2], "width": 6.5, "bars": 7, "aspect": 0.7, "color": "#0c0c0c", "light": False}])
shot(127.10, {**base_scene(fog=0.04, focus=8.5), "layers": [
    {"kind": "shatter", "src": img("c12_p08_p01"), "crop": [0, 0.36, 1, 0.64], "pos": [0, 0, 9], "width": 10.5, "pieces": 46, "seed": 5,
     "explode": {"keys": [[128.5, 0], [131.6, 0.55]], "ease": "ease_in"}, "spread": 2.2, "toward": 2.5, "spin": 70}, dust()],
    "camera": {"keys": [{"at": 0, "pos": [0, 0, 0], "look": [0, 0, 9]}, {"at": 1, "pos": [0.2, 0, 1.2], "look": [0, 0, 9], "ease": "sine"}],
               "handheld": 0.015}}, note="如蛆附骨的折磨：杯子碎片划伤的回忆——画面像玻璃一样缓慢碎开")
creep("c13_p06_p01", 131.80, z=10, push=0.3, drift=(0.6, 0), dutch=(0, -4), fog=0.05, note="肆意地 发泄着 咆哮着 毁灭了：母亲倒在地上的房间")
FLASHES.append(136.46)
creep("c13_p08_p01", 137.58, slot="c13_p08_p01", z=8.5, push=0.45, look=(0, 0.8), note="与这深渊拼个鱼死网破：血泪的真理奈")
void(143.42, [{"kind": "image", "src": img("c13_p09_p01"), "frame": "border", "pos": [0, 0, 8], "width": 4.6, "rot": [0, 8, -2]},
              dust(vol=((-9, 9), (-5, 5), (2, 20)), count=420, opacity=0.25, speed=0.15)],
     {"keys": [{"at": 0, "pos": [0, 0, 2.2], "look": [0, 0, 8]}, {"at": 1, "pos": [0, 0, -3.5], "look": [0, 0, 8], "ease": "sine"}], "handheld": 0.01},
     note="像地底蝼蚁在自我撕扯：“把她杀掉就好了吧”——画面退入黑暗")
# the time vortex: framed pages along a spiral, the camera drifts down the tunnel; year counter 2022 -> 2016
vort = []
for i, pid in enumerate(["c13_p08_p01", "c12_p02_p01", "c4_p25_p01", "c3_p32_p01", "c2_p03_p01", "c1_p26_p01", "c4_p17_p01", "c1_p27_p01"]):
    a = i * 0.9
    vort.append({"kind": "image", "src": img(pid), "frame": "border", "pos": [round(math.cos(a) * 2.4, 2), round(math.sin(a) * 1.5, 2), 5 + i * 3.2],
                 "width": 2.6, "rot": [0, round(-math.cos(a) * 25), round(math.degrees(a) * 0.1)]})
vort.append(dust(vol=((-6, 6), (-4, 4), (1, 30))))
void(148.26, vort, {"keys": [{"at": 0, "pos": [0, 0, 0], "look": [0, 0, 10], "roll": 0},
                             {"at": 1, "pos": [0, 0, 18], "look": [0, 0, 28], "roll": -18, "ease": "sine"}], "handheld": 0.01},
     note="深陷绝望漩涡：时间回溯——沿螺旋排列的记忆画格，镜头缓慢旋入")
creep("c13_p18_p01" if os.path.exists(os.path.join(ROOT, "panels/c13_p18_p01.png")) else "c13_p18_p02", 151.00, z=9, push=0.3,
      note="谁能说破孰对孰错：章鱼噼在森林里")
corridor([("c12_p07_p01", -1), ("c8_p19_p01", 1), ("c3_p22_p03", -1)], 155.32, spacing=5,
         note="只窥得世人心中纲常丑恶：三个母亲（真理奈母/东君母/静香母）悬在黑暗走廊两侧")
void(161.66, [{"kind": "image", "src": img("c13_p16_p01"), "pos": [0, 0.6, 22], "width": 15}, dust(vol=((-8, 8), (-5, 5), (2, 20)))],
     {"keys": [{"at": 0, "pos": [0, -0.6, 0], "look": [0, 0.2, 22]}, {"at": 1, "pos": [0, -0.2, 7.5], "look": [0, 0.6, 22], "ease": "ease_in"}],
      "handheld": 0.01}, fog=0.05, note="彻底沦为腐化败坏的偏颇：巨大的章鱼噼脸“必须去杀掉久世静香”，镜头从远处一点点靠近")
void(169.42, [{"kind": "image", "src": img("c13_p14_p01"), "frame": "border", "pos": [0, -1.0, 9], "width": 4.4, "rot": [-20, 0, 6]},
              dust(vol=((-9, 9), (-6, 12), (1, 20)), count=500, opacity=0.3, speed=1.0)],
     {"keys": [{"at": 0, "pos": [0, 2.5, 0], "look": [0, 0, 9]}, {"at": 1, "pos": [0, -0.5, 1.5], "look": [0, -2.5, 9], "roll": 8, "ease": "ease_in"}],
      "handheld": 0.01}, note="高空坠落当作赌注以搏：坠向 2016")
creep("c13_p12_p01", 175.60, crop=[0, 0, 1, 0.55], z=9, push=0.3, note="挣扎叛逆却不能得：“我将消除你的所有记忆”")
TEXTS.append({"start": 149.0, "end": 154.8, "text": "", "mg_counter": True})

# =========================================================================== PART 3  (2016, Shizuka's end)
creep("c13_p19_p01", 179.04, slot="c13_p19_p01", z=9, push=0.25, fog=0.06, note="第三部分：回到 2016——渺茫的洒脱")
text(179.8, 183.9, "久世しずか", pos=(0.84, 0.5), size=40)
creep("c1_p31_p05", 184.30, slot="c1_p31_p05", z=8.5, push=0.4, extra=[ribbon(top=(1.3, 3.6, 6.0), length=(2.6, 2.9))],
      note="仲直りリボン：借走丝带——前景里那根丝带第一次出现，轻轻摆动")
creep("c1_p32_p01", 189.80, slot="c1_p32_p01", z=9, push=0.2, note="★DROP：“拜拜”——第三次（最后一次）闪白，然后长长的停留")
FLASHES.append(189.80)
creep("c1_p27_p01", 194.72, slot="c1_p27_p01", z=10, push=0.3, rise=-2.0, look=(0, 0.6),
      extra=[{"kind": "cage", "pos": [0.2, 0, 3.4], "width": 7, "bars": 9, "aspect": 0.7, "color": "#090909", "light": False}],
      note="如困兽在夹缝中辗转流落：栅栏后的静香")
creep("c1_p36_p04", 200.10, z=9, push=0.35, fog=0.06, extra=[ribbon(top=(-1.2, 4.0, 7.0), length=(3.2, 3.2), sway=0.05)],
      note="倘若选择死亡是否能解脱：章鱼噼走进那个房间")
void(203.44, [{"kind": "image", "src": img("c1_p36_p03"), "pos": [0, 4.2, 9], "width": 5.5, "rot": [-25, 0, 0]},
              ribbon(top=(0.0, 3.4, 8.0), length=(5.2, 5.2), sway=0.05, width=0.07), dust()],
     {"keys": [{"at": 0, "pos": [0, -2.0, 0], "look": [0, -1.5, 8]}, {"at": 1, "pos": [0, -0.5, 1.0], "look": [0, 3.5, 8.5], "ease": "sine"}],
      "handheld": 0.012}, note="跃下后形同小丑躺在血泊：镜头沿着丝带缓慢向上，直到横梁")
creep("c1_p36_p01", 209.46, z=8, push=0.35, note="微弱呼救却被笑声所淹没：章鱼噼“静香香？”")
text(210.2, 214.9, "しずかちゃん", pos=(0.82, 0.48), size=42, stagger=0.12)
for k, pid in enumerate(["c1_p37_p01", "c1_p37_p02", "c1_p37_p03"]):
    creep(pid, [215.54, 217.03, 218.52][k], z=9, push=0.15, particles=True, note="放弃吧 认清这结果：悬空的鞋，一格一格" if k == 0 else "")
creep("c1_p36_p02", 220.28, z=8, push=0.3, note="但 伏诛俗世：仰望")
void(223.40, [ribbon(top=(0.0, 3.0, 6.5), length=(3.6, 3.6), sway=0.03, width=0.07), dust(count=120, opacity=0.2, speed=0.05)],
     {"keys": [{"at": 0, "pos": [0, 0, 0], "look": [0, 1.2, 6.5]}, {"at": 1, "pos": [0, 0, 0.3], "look": [0, 1.2, 6.5]}]},
     note="唯——黑暗里只剩那根丝带")
creep("c1_p35_p01", 224.40, slot="c1_p35_p01", z=10, push=-0.25, fog=0.05, particles=True, light_dir=(-0.6, -0.3, 1),
      note="死以解脱：上吊的房间。缓慢后拉，窗外的光，结束于黑")

# =========================================================================== assemble


def build():
    pal_fx = lambda part: {"type": "duotone", **PALETTES[part], "amount": 0.86, "contrast": 1.12}
    shots = []
    S = sorted(SHOTS, key=lambda s: s["start"])
    for i, s in enumerate(S):
        part = part_of(s["start"])
        sh = {k: v for k, v in s.items() if k not in ("note", "montage")}
        sh["id"] = f"v{i + 1:03d}"
        efx = [pal_fx(part),
               {"type": "flicker", "amount": EF.get("flicker", 0.04)},
               {"type": "drift_shake", "amount": 2}]
        if s["start"] in FLASHES:
            efx += [{"type": "flash", "on": "start", "amount": 0.85, "decay": 0.6},
                    {"type": "shake", "on": "start", "amount": EF["shake_max"], "freq": EF["shake_freq"], "decay": 0.6},
                    {"type": "zoom_punch", "on": "start", "amount": EF["zoom_punch_max"], "attack": 0.08, "decay": 0.8}]
        if s.get("montage"):
            efx += [{"type": "rgb_split", "amount": EF["rgb_split_max"]}, {"type": "flash", "on": "start", "amount": 0.25, "decay": 0.12}]
        sh["effects"] = efx
        prev = S[i - 1] if i else None
        if i == 0:
            tr = {"type": "fade", "dur": 1.6}
        elif s.get("montage") or (prev and prev.get("montage")):
            tr = {"type": "cut"}
        elif prev and part_of(prev["start"]) != part:
            tr = {"type": "black", "dur": 1.2}
        elif s["start"] in (107.30, 223.40, 224.40, 95.60):
            tr = {"type": "cut"}
        else:
            tr = {"type": "fade", "dur": 0.7} if i % 3 else {"type": "black", "dur": 0.6}
        sh["transition"] = tr
        shots.append(sh)
    texts = [t for t in TEXTS if t.get("text")]
    mg = [  # global MG: thin, faint, sparse — oppressive vocabulary only
        {"type": "frame", "start": 20.32, "end": 24.8, "inset": 0.08, "width": LIM["mg"]["stroke"], "color": TXT_COL, "corners": True,
         "opacity": LIM["mg"]["opacity_max"]},
        {"type": "line", "start": 21.0, "end": 24.6, "a": [0.36, 0.62], "b": [0.64, 0.62], "draw": 1.6, "width": 1, "color": TXT_COL,
         "opacity": 0.3},
        {"type": "counter", "start": 148.6, "end": 154.8, "from": 2022, "to": 2016, "pos": [0.5, 0.88], "size": 34, "color": TXT_COL,
         "opacity": 0.4, "ease": "ease_in_out", "font": FONT_Q},
        {"type": "grid", "start": 148.26, "end": 151.0, "spacing": 0.06, "dot": 1, "color": TXT_COL, "opacity": 0.08, "drift": [0.0, 0.01]},
        {"type": "glitch_blocks", "on": [104.30, 104.67, 105.04, 105.42, 105.79, 106.16], "count": 6, "color": "#ffffff", "dur": 0.08,
         "blend": "difference", "opacity": 0.5},
    ]
    project = {
        "meta": {"title": "takopi_mad_v2", "width": 1920, "height": 1080, "fps": 24, "audio": "song.mp3", "beats": "beats.json",
                 "start": 0, "end": 231.3, "crf": 20, "cutouts": "cutouts", "font": FONT_Q,
                 "sfx": [{"file": "assets/voice_1.wav", "at": 100.28, "gain": 1.6, "duck": 0.3},
                         {"file": "assets/voice_2.wav", "at": 103.86, "gain": 1.6, "duck": 0.3}]},
        "style": {"effects": [{"type": "grain", "amount": EF["grain"]}, {"type": "vignette", "amount": EF["vignette"]},
                              {"type": "flash", "on": [229.6], "attack": 1.6, "decay": 3, "color": "#000000", "amount": 1.0}],
                  "mg": mg},
        "shots": shots,
        "texts": texts,
    }
    with open(os.path.join(ROOT, "project_v2.yaml"), "w", encoding="utf-8") as f:
        f.write("# generated by build_v2.py\n")
        yaml.safe_dump(project, f, allow_unicode=True, sort_keys=False, width=200)
    lines = ["# 分镜 v2 — 章鱼噼的原罪 × 唯死以解脱（风格：压抑）", "",
             "| 镜头 | 时间 | 部分 | 类型 | 设计 |", "|---|---|---|---|---|"]
    for i, s in enumerate(S):
        typ = "3D场景" if s.get("scene") else "平面"
        t = s["start"]
        lines.append(f"| v{i + 1:03d} | {int(t // 60)}:{t % 60:05.2f} | {part_of(t)} | {typ} | {s.get('note', '')} |")
    lines += ["", "文字（仅日文）：" + "、".join(f"{x['text']}（{x['start']:.1f}s）" for x in texts),
              "", f"闪白（上限 {LIM['transitions']['flash_max_total']}）：" + "、".join(f"{x:.2f}s" for x in FLASHES)]
    open(os.path.join(ROOT, "storyboard_v2.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    assert len(FLASHES) <= LIM["transitions"]["flash_max_total"], "flash budget exceeded"
    print(f"{len(shots)} shots ({sum(1 for s in S if s.get('scene'))} 3D scenes), {len(texts)} texts, flashes {FLASHES}")


if __name__ == "__main__":
    build()
