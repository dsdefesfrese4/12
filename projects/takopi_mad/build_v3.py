"""v3 — 章鱼噼的原罪 × 唯死以解脱   (style gate: oppressive, see style.json)

Structure (user):
  Part 1  0:00–1:47  no Takopi entrance. Symbolic/MG opening, then nothing but bullying and torment, the boy's childhood
                     under his mother cut in; the very last moment turns: Takopi's counter-kill, "ありがとう タコピー"
                     on 谁言语淬毒, flash-cuts of Marina's death on 封锁我歌喉, 1:47 music stop = 原罪.
  Part 2  1:49–2:59  Marina's first loop (2022), misunderstanding-route: mother's domestic violence (not her death),
                     three parent/child pairs on 只窥得世人心中纲常丑恶, ends with Marina jumping from the school roof
                     on 高空坠落当作赌注以搏.
  Part 3  2:59–3:51  Shizuka alone (no Takopi POV) -> the ribbon -> 唯 死以解脱 = the hanging.
Craft rules:
  * every panel is a plate placed in a coloured 3D space; each take is ONE continuous camera move through its stations
  * takes join by flying into fog/black and out again, or through a shared element (thread, black page); no hard cuts
    except the flash-cut montage the user asked for
  * a character slot sits 0.5 m in front of every plate that has a person (cutouts drop in later)
"""
import json
import math
import os

import cv2
import numpy as np
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
STYLE = json.load(open(os.path.join(ROOT, "style.json"), encoding="utf-8"))
LIM = STYLE["limits"]
EF = LIM["effects"]
FONT_Q = "assets/fonts/" + LIM["typography"]["fonts"]["quiet"]
FONT_H = "assets/fonts/" + LIM["typography"]["fonts"]["heavy"]
TXT = LIM["typography"]["color"]
FOV = 40.0
ASPECT = 16 / 9

# ------------------------------------------------------------------ colour worlds (gradient maps: shadow, mid, highlight)
WORLDS = {
    "void": dict(gmap=["#05080a", "#3a4a4c", "#cfdcd8"], bg=["#0a1214", "#020304"], fog="#04090a", light="#cfe2dc"),
    "school": dict(gmap=["#07100e", "#4f6a5e", "#dbe8d8"], bg=["#0e1a17", "#030605"], fog="#06100d", light="#d4ecdc"),
    "forest": dict(gmap=["#050a06", "#3e5a3a", "#d4dfc2"], bg=["#0a140b", "#020402"], fog="#060d07", light="#dfe8c8"),
    "blood": dict(gmap=["#0d0203", "#7a1c1e", "#f2d8cc"], bg=["#1a0405", "#030000"], fog="#140304", light="#ffb0a0"),
    "night": dict(gmap=["#08061a", "#4a3c7a", "#e6dcf6"], bg=["#120c2a", "#030208"], fog="#0a0820", light="#d8ccff"),
    "home": dict(gmap=["#120a03", "#7a5624", "#f4e2c0"], bg=["#1e1206", "#050301"], fog="#140c04", light="#ffd59a"),
    "parents": dict(gmap=["#06080c", "#4e5662", "#e2e6ea"], bg=["#0e1218", "#020304"], fog="#080a10", light="#e0e8f4"),
    "dusk": dict(gmap=["#1a0a14", "#a0506a", "#ffe2c8"], bg=["#4a1c34", "#0c0410"], fog="#2a0e1e", light="#ffc8a0"),
    "summer": dict(gmap=["#0c1014", "#6a7a84", "#f6f2e6"], bg=["#28323a", "#06080a"], fog="#141a1e", light="#fff2d8"),
    "room": dict(gmap=["#05070c", "#3e4a5e", "#e8e2d2"], bg=["#0c1220", "#020306"], fog="#060a12", light="#ffe0b0"),
}

ASP_CACHE = {}


def src(pid):
    for d, ext in (("panels_clean", ".png"), ("panels", ".png"), ("pages", ".jpg")):
        if os.path.exists(os.path.join(ROOT, d, pid + ext)):
            return f"{d}/{pid}{ext}"
    raise FileNotFoundError(pid)


def aspect(pid, crop=None):
    if pid not in ASP_CACHE:
        im = cv2.imread(os.path.join(ROOT, src(pid)))
        ASP_CACHE[pid] = im.shape[0] / im.shape[1]
    a = ASP_CACHE[pid]
    if crop:
        a = a * crop[3] / crop[2]
    return a


def fill_w(dist, asp, margin=0.86):
    vh = 2 * dist * math.tan(math.radians(FOV) / 2)
    vw = vh * ASPECT
    w = vw * margin
    if w * asp < vh * margin:
        w = vh * margin / asp
    return w


def rot_y(deg):
    a = math.radians(deg)
    return np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])


# ------------------------------------------------------------------ takes
SHOTS, TEXTS, SFX, MG = [], [], [], []
FLASH_AT = []


class Take:
    """One continuous camera move through stations placed in a coloured space."""

    def __init__(self, t0, t1, world, note=""):
        self.t0, self.t1 = t0, t1
        self.world = WORLDS[world]
        self.stations = []
        self.layers = []
        self.keys = []
        self.note = note
        self.cursor = np.array([0.0, 0.0, 0.0])
        self.side = 1
        self.fog = 0.035
        self.join_in = "fog"   # fog | none
        self.join_out = "fog"

    # station = a plate in space + the camera position that frames it
    def station(self, t, pid, *, crop=None, char=True, mode="wall", dist=6.0, ry=None, dy=0.0, step=7.0, creep=0.12,
                drift=(0.25, 0.08), roll=(0.0, 0.0), gmap=None, note="", frame=None, look_off=(0, 0), extra=None, world=None):
        w_ = WORLDS[world] if world else self.world
        asp = aspect(pid, crop)
        if ry is None:
            ry = 16 * self.side
        self.side *= -1
        if mode == "wall":
            P = self.cursor + np.array([2.6 * -self.side, dy, step])
            R = rot_y(ry)
            n = R @ np.array([0, 0, -1.0])
            C = P + n * dist
            rot = [0, ry, 0]
        else:  # floor: plate lies on the ground, camera looks down
            P = self.cursor + np.array([1.5 * -self.side, -3.2 + dy, step * 0.8])
            n = np.array([0, 1.0, -0.12])
            n /= np.linalg.norm(n)
            C = P + n * dist
            rot = [-90, ry * 0.5, 0]
        self.cursor = P.copy()
        self.cursor[1] = 0
        width = fill_w(dist, asp)
        L = {"kind": "image", "src": src(pid), "pos": P.round(3).tolist(), "rot": rot, "width": round(width, 3),
             "gmap": gmap or w_["gmap"]}
        if crop:
            L["crop"] = crop
        if frame:
            L["frame"] = frame
        self.layers.append(L)
        if char:
            off = n * 0.45
            S = {"kind": "slot", "slot": pid, "pos": (P + off).round(3).tolist(), "rot": rot, "width": round(width * (dist - 0.45) / dist, 3)}
            if crop:
                S["crop"] = crop
            self.layers.append(S)
            SLOTS.add(pid)
        for e in (extra or []):
            self.layers.append(e)
        self.stations.append(dict(t=t, P=P, C=C, n=n, dist=dist, creep=creep, drift=drift, roll=roll, look_off=look_off,
                                  note=note, pid=pid, mode=mode))
        return P, n

    def add(self, *layers):
        self.layers += list(layers)

    def build(self):
        st = self.stations
        keys = []
        def key(t, pos, look, roll=0.0, ease="sine"):
            keys.append({"at": (t - self.t0) / (self.t1 - self.t0), "pos": [round(float(v), 3) for v in pos],
                         "look": [round(float(v), 3) for v in look], "roll": roll, "ease": ease})
        for i, s in enumerate(st):
            t_in = max(s["t"], self.t0)
            t_out = st[i + 1]["t"] if i + 1 < len(st) else self.t1
            glide = min(1.4, 0.4 * (t_out - t_in)) if i + 1 < len(st) else 0
            side = np.cross(np.array([0, 1.0, 0]), s["n"]) if s["mode"] == "wall" else np.array([1.0, 0, 0])
            up = np.array([0, 1.0, 0]) if s["mode"] == "wall" else np.array([0, 0, 1.0])
            look = s["P"] + side * s["look_off"][0] + up * s["look_off"][1]
            d0 = s["C"] - side * s["drift"][0] - up * s["drift"][1]
            d1 = s["P"] + (s["C"] - s["P"]) * (1 - s["creep"]) + side * s["drift"][0] + up * s["drift"][1]
            if i == 0 and self.join_in == "fog":
                # come out of the fog: start further back
                key(self.t0, d0 - s["n"] * -4.0, look, s["roll"][0])
            key(t_in, d0, look, s["roll"][0], "ease_in_out" if i else "sine")
            key(t_out - glide, d1, look, s["roll"][1])
        if self.join_out == "fog" and st:
            s = st[-1]
            keys[-1]["at"] = min(keys[-1]["at"], (self.t1 - 1.0 - self.t0) / (self.t1 - self.t0))
            key(self.t1, s["P"] + (s["C"] - s["P"]) * 0.25, s["P"], s["roll"][1], "ease_in")
        keys.sort(key=lambda k: k["at"])
        # fog density ramps up at the join so the take dissolves into its own darkness
        dens = {"keys": [[self.t0, 0.30 if self.join_in == "fog" else self.fog], [self.t0 + 1.0, self.fog],
                         [self.t1 - 1.0, self.fog], [self.t1, 0.32 if self.join_out == "fog" else self.fog]], "ease": "ease_in_out"}
        sc = {"bg": self.world["bg"], "fov": FOV, "fog": {"color": self.world["fog"], "density": dens},
              "dof": {"focus": 6.0, "aperture": 1.3},
              "light": {"dir": [0.3, -0.5, 1.0], "color": self.world["light"], "ambient": 0.86},
              "camera": {"keys": keys, "handheld": LIM["camera"]["handheld"]},
              "layers": self.layers + [{"kind": "particles", "preset": "dust", "volume": self.volume(), "count": 260,
                                        "opacity": EF["particle_opacity"], "color": self.world["light"], "speed": 0.4}]}
        SHOTS.append({"start": self.t0, "scene": sc, "_note": self.note, "_stations": [(s["t"], s["pid"], s["note"]) for s in st]})

    def volume(self):
        ps = np.array([s["P"] for s in self.stations] + [s["C"] for s in self.stations]) if self.stations else np.zeros((1, 3))
        lo, hi = ps.min(0) - 5, ps.max(0) + 5
        return [[round(lo[i], 1), round(hi[i], 1)] for i in range(3)]


SLOTS = set()


def words(volume, opacity=0.3, count=10):
    return {"kind": "words", "layout": "cloud", "words": ["しね", "どろぼう", "寄生虫", "ゴミ", "くさい", "きもい", "消えろ"],
            "count": count, "volume": volume, "size": 150, "color": "#c8d0c8", "height": 0.5, "opacity": opacity, "font": FONT_Q,
            "light": False}


def text(t0, t1, s, pos=(0.84, 0.5), size=44, font=FONT_Q, stagger=0.07):
    TEXTS.append({"start": t0, "end": t1, "text": s, "pos": list(pos), "size": size, "vertical": True, "font": font, "color": TXT,
                  "stroke": {"width": 0},
                  "kinetic": {"in": "blur_in", "out": "blur", "idle": "none", "stagger": stagger, "in_dur": 0.9, "out_dur": 0.7,
                              "tracking": 0.35, "shadow": {"color": "#000000", "offset": [0, 0], "blur": 10, "opacity": 0.8}}})


# ================================================================== PART 1 — torment
# T1  0:00–0:47  symbolic opening -> bullying
T = Take(0.0, 47.32, "void", "开场象征/MG → 霸凌")
T.join_in = "fog"
T.add(words([[-5, 5], [-2.5, 2.5], [2, 16]], opacity=0.35, count=14))
T.station(7.0, "c2_p02_p01", char=False, crop=[0.18, 0.55, 0.7, 0.45], dist=4.5, world="school",
          note="被涂满“去死”的课桌（局部）浮在黑暗里——象征开场")
T.station(13.0, "c1_p11_p04", char=False, world="school", note="不对吧——被折断的垫板/低头")
T.station(18.5, "c2_p01_p03", char=False, world="school", note="教室门口“青空”——空无一人的走廊")
T.station(24.80, "c2_p02_p01", world="school", note="旁人不掩的冷漠：教室全景，所有人在看")
T.station(27.82, "c2_p03_p01", world="school", note="扬唇讽我执着：真理奈“早啊寄生虫”")
T.station(31.14, "c1_p11_p02", world="school", note="抹杀最后的虚弱：围住她的人")
T.station(36.96, "c2_p19_p01", world="school", note="挣扎中迷失自我：倒在地上被踢")
T.station(40.06, "c2_p20_p03", world="school", note="黑暗逐渐吞没：哭着的脸")
T.station(43.10, "c1_p17_p01", crop=[0.0, 0.0, 0.72, 1.0], world="forest", note="胸中残存的余热：和查比奔跑的记忆（唯一的暖色）",
          gmap=["#0e0a04", "#7a6a3a", "#f6ecd0"])
T.build()
text(2.5, 6.6, "タコピーの原罪", pos=(0.5, 0.47), size=72, font=FONT_H, stagger=0.14)
MG.append({"type": "line", "start": 3.4, "end": 6.6, "a": [0.36, 0.6], "b": [0.64, 0.6], "draw": 1.8, "width": 1, "color": TXT, "opacity": 0.3})
MG.append({"type": "grid", "start": 0.0, "end": 12.0, "spacing": 0.06, "dot": 1, "color": TXT, "opacity": 0.07, "drift": [0.0, 0.006]})

# T2  0:47–1:04  faces / the boy's childhood / Chappy taken / puppet walk
T = Take(47.32, 64.34, "school", "谁笑着…不如木偶")
T.join_in = "fog"
T.station(47.32, "c2_p03_p01", crop=[0.25, 0.0, 0.75, 0.75], step=5, note="谁笑着：真理奈在笑")
T.station(49.12, "c2_p20_p03", step=5, note="似哭了：静香在哭")
T.station(50.38, "c2_p35_p01", step=5, world="home", note="挣扎着：真理奈也在哭（母亲那边）")
T.station(52.42, "c9_p03_p01", crop=[0.0, 0.55, 1.0, 0.45], step=5, world="parents", note="麻木了：东君小时候——拿着 95 分")
T.station(53.88, "c8_p17_p01", char=False, step=5, world="parents", note="刀划破血肉竟如此快活：54 分的试卷，红叉")
T.station(56.31, "c3_p09_p02", step=6, world="blood", note="查比咬伤真理奈——血")
T.station(57.82, "c3_p21_p02", char=False, step=5, world="parents", note="町立保健所：查比被带走")
T.station(59.52, "c3_p33_p01", dist=7.5, step=7, world="forest", note="麻木地行走着不如木偶：两人走进森林，头顶垂下提线",
          extra=[{"kind": "strings", "top": 7, "color": "#d8d2c4", "opacity": 0.5, "width": 0.006, "sway": 0.04,
                  "targets": [[0, 0, 0]]}])
T.build()
# strings need the station position: patch after build
_st = SHOTS[-1]["scene"]["layers"]
for L in _st:
    if L.get("kind") == "strings":
        P = [x for x in _st if x.get("kind") == "image" and "c3_p33" in x["src"]][0]["pos"]
        L["targets"] = [[P[0] - 0.6, P[1] + 0.9, P[2] - 0.3], [P[0] + 0.5, P[1] + 0.8, P[2] - 0.3],
                        [P[0] - 0.9, P[1] - 1.2, P[2] - 0.3], [P[0] + 0.8, P[1] - 1.3, P[2] - 0.3]]
        L["top"] = P[1] + 8

# T3  1:04–1:47  the forest — extreme torment, then the counter-kill
T = Take(64.34, 104.30, "forest", "森林：极致折磨 → 反杀 → 谢谢你")
T.station(64.34, "c4_p04_p01", note="不予借口辩驳：“狗啊，已经死了”")
T.station(67.08, "c4_p05_p01", char=False, note="如何做个哑巴苟活：被踢倒")
T.station(69.80, "c4_p05_p02", note="真理奈“那当然是要被弃死的啊”")
P, n = T.station(71.52, "c4_p06_p02", dist=5.5, note="绝望的藤蔓生于指尖交错：荆棘从四周长进画面")
T.add({"kind": "vines", "pos": (P + n * 1.6).round(3).tolist(), "rot": [0, 0, 0], "width": 9, "aspect": 0.62,
       "grow": {"keys": [[71.4, 0.0], [76.5, 0.85]], "ease": "ease_in_out"}, "seed": 3, "branches": 6,
       "origins": [[0.0, 1.0, -50], [1.0, 1.0, -130], [0.0, 0.2, 10], [1.0, 0.3, 170]], "light": False, "color": "#050805"})
T.station(74.30, "c4_p07_p02", crop=[0.0, 0.0, 0.62, 1.0], note="“你这种人只是活着就会给别人添麻烦的寄生虫”")
T.station(77.84, "c4_p08_p02", note="逐渐吞噬不堪重负的躯壳")
T.station(80.32, "c4_p11_p02", mode="floor", dist=6.0, note="倒在地上的静香，俯视")
T.station(83.48, "c4_p13_p01", world="blood", note="嘶吼着试图驱逐心里的魔：真理奈“把爸爸还给我”")
T.station(89.38, "c4_p14_p01", world="blood", note="殊不知灵魂早已被妖魔胁迫：反杀——照相机举起")
P, n = T.station(95.60, "c4_p15_p02", char=False, dist=5.0, world="blood", note="★咚（闪白 1）")
FLASH_AT.append(95.60)
T.station(97.40, "c4_p17_p01", mode="floor", dist=6.5, world="blood", note="不得的自由：倒下的真理奈，血在身下扩散")
T.add({"kind": "blood", "seed": 8, "pos": (T.stations[-1]["P"] + np.array([0.3, 0.03, 0])).round(3).tolist(), "rot": [-90, 0, 0],
       "width": {"keys": [[97.4, 1.0], [99.6, 3.6]]}, "opacity": 0.75, "light": False, "color": "#5a0508"})
T.station(99.82, "c4_p25_p01", dist=5.2, world="blood", creep=0.08, note="谁言语淬毒：闭眼笑——ありがとう タコピー（原片语音）")
T.station(102.82, "c4_p26_p01", dist=4.6, world="blood", creep=0.15, note="封锁我歌喉：睁眼——第二句原片语音")
T.join_out = "none"
T.build()
text(100.30, 102.75, "ありがとう　タコピー", pos=(0.84, 0.5), size=44, stagger=0.06)
SFX += [{"file": "assets/voice_1.wav", "at": 100.28, "gain": 1.6, "duck": 0.3},
        {"file": "assets/voice_2.wav", "at": 103.86, "gain": 1.6, "duck": 0.3}]
# flash-cuts of Marina's death (user asked for these hard cuts), then the music stop
for k, (pid, crop) in enumerate([("c4_p23_p01", None), ("c4_p19_p01", None), ("c4_p17_p02", None), ("c4_p21_p01", [0, 0, 1, 0.6]),
                                 ("c4_p23_p01", [0.2, 0.4, 0.6, 0.6]), ("c4_p26_p01", [0.1, 0.25, 0.8, 0.5]), ("c4_p17_p01", None),
                                 ("c4_p19_p01", [0.2, 0.2, 0.6, 0.6])]):
    sh = {"start": round(104.30 + k * 0.372, 3), "image": src(pid), "camera": {"zoom": [1.08, 1.12], "ease": "linear"},
          "_note": "真理奈之死 闪切" if k == 0 else "", "_montage": True, "_gmap": WORLDS["blood"]["gmap"]}
    if crop:
        sh["crop"] = crop
    SHOTS.append(sh)
SHOTS.append({"start": 107.30, "image": src("c4_p29_p01"), "camera": {"zoom": [1.0, 1.0]}, "_note": "■音乐骤停：原罪", "_montage": True})

# ================================================================== PART 2 — Marina, first loop (misunderstanding route)
T = Take(108.96, 131.80, "night", "2022 真理奈：家暴的根")
T.station(108.96, "c11_p18_p01", crop=[0.0, 0.0, 0.62, 1.0], note="孤独已将我吞没：2022 年的真理奈")
T.station(112.12, "c12_p02_p01", note="为掩心底无措：带着伤疤走进学校")
T.station(115.12, "c12_p16_p01", note="于人前故作淡漠：“最近好像也没那么坏了”")
T.station(120.62, "c12_p04_p01", crop=[0, 0, 1, 0.56], char=False, world="home", note="狂奔着捂住耳朵：回到家，酒瓶")
T.station(124.08, "c12_p07_p01", crop=[0, 0, 1, 0.48], world="home", note="奢求就此逃脱：母亲的怒吼（家暴）")
P, n = T.station(127.10, "c12_p08_p01", crop=[0, 0.36, 1, 0.64], world="home", note="如蛆附骨的折磨：玻璃杯划伤的童年——画面碎开")
T.station(129.82, "c2_p34_p04", world="home", note="“你是站在妈妈这边的吧”——母亲的手抓着小真理奈")
T.build()
text(109.6, 114.0, "２０２２年", pos=(0.16, 0.45), size=30)
text(110.4, 114.0, "雲母坂まりな", pos=(0.12, 0.52), size=40)

T = Take(131.80, 151.00, "home", "崩坏")
T.station(131.80, "c2_p36_p01", note="肆意地：睁大的眼")
T.station(133.60, "c2_p33_p01", crop=[0, 0, 1, 0.78], char=False, note="发泄着：父亲离开的那晚")
T.station(134.64, "c2_p34_p01", char=False, note="咆哮着：母亲的手、戒指")
T.station(136.46, "c2_p36_p02", note="毁灭了：醉倒的母亲和独自缩着的孩子（闪白 2）")
FLASH_AT.append(136.46)
T.station(137.58, "c12_p08_p01", crop=[0, 0, 1, 0.38], world="night", note="与这深渊拼个鱼死网破")
T.station(143.42, "c12_p19_p01", world="night", note="像地底蝼蚁在自我撕扯：夜路上的真理奈与直树")
P, n = T.station(148.26, "c13_p08_p01", world="night", dist=5.0, note="深陷绝望漩涡：血泪")
T.build()

# three parents / three children — puppet strings from each parent to their child
T = Take(151.00, 166.30, "parents", "人心丑恶：三对父母与孩子")
pairs = [("c12_p07_p01", [0, 0, 1, 0.48], "c2_p35_p01", "真理奈与母亲"),
         ("c8_p19_p01", None, "c9_p03_p01", "东君与母亲"),
         ("c3_p22_p01", None, "c3_p21_p01", "静香与母亲")]
times = [(151.00, 153.40), (155.32, 158.30), (160.30, 163.20)]
for (par, pcrop, kid, label), (ta, tb) in zip(pairs, times):
    Pp, npar = T.station(ta, par, crop=pcrop, dy=1.6, step=6.0, dist=6.0, ry=0, note=f"{label}：家长")
    Pk, nk = T.station(tb, kid, crop=[0, 0.55, 1, 0.45] if kid == "c9_p03_p01" else None, dy=-1.6, step=0.4, dist=6.0, ry=0,
                       note=f"{label}：孩子")
    T.add({"kind": "strings", "top": float(Pp[1]), "color": "#d6dbe2", "opacity": 0.45, "width": 0.006, "sway": 0.03,
           "targets": [[float(Pk[0]) + dx, float(Pk[1]) + 1.0, float(Pk[2]) - 0.3] for dx in (-0.7, -0.2, 0.3, 0.8)]})
T.build()

# misunderstanding route: Marina goes up and jumps — the camera falls with her
T = Take(166.30, 179.04, "dusk", "高空坠落：真理奈跳楼（误解向）")
T.join_out = "fog"
P1, n1 = T.station(166.30, "c12_p16_p01", dist=5.0, note="彻底沦为腐化败坏的偏颇：屋顶，最后看一眼")
# the school facade stands tall; the camera drops past it
fac = {"kind": "image", "src": src("c12_p02_p01"), "pos": [float(P1[0]) + 1.0, float(P1[1]) - 9.0, float(P1[2]) + 6.0], "rot": [0, 0, 0],
       "width": 9.0, "gmap": WORLDS["dusk"]["gmap"]}
T.add(fac)
mem = ["c12_p02_p01", "c2_p35_p01", "c12_p08_p01", "c2_p36_p01", "c12_p07_p01", "c2_p03_p01"]
for i, pid in enumerate(mem):
    T.add({"kind": "image", "src": src(pid), "frame": "border", "pos": [float(P1[0]) + (-1.8 if i % 2 else 1.8), float(P1[1]) - 4 - i * 3.2,
           float(P1[2]) + 3.5], "rot": [0, 20 if i % 2 else -20, (-6 if i % 2 else 6)], "width": 2.4, "gmap": WORLDS["dusk"]["gmap"]})
T.build()
cam = SHOTS[-1]["scene"]["camera"]
fall_top = [float(P1[0]), float(P1[1]) + 0.2, float(P1[2]) - 4.5]
def at(t): return (t - 166.30) / (179.04 - 166.30)
cam["keys"] = [k for k in cam["keys"] if k["at"] <= at(169.3)]
cam["keys"] += [
    {"at": at(169.42), "pos": fall_top, "look": [float(P1[0]), float(P1[1]) - 1.5, float(P1[2]) + 2], "roll": 0, "ease": "ease_in"},
    {"at": at(172.96), "pos": [fall_top[0], fall_top[1] - 9, fall_top[2] + 1], "look": [float(P1[0]), float(P1[1]) - 14, float(P1[2]) + 4],
     "roll": 6, "ease": "ease_in"},
    {"at": at(178.6), "pos": [fall_top[0], fall_top[1] - 24, fall_top[2] + 2], "look": [float(P1[0]), float(P1[1]) - 32, float(P1[2]) + 5],
     "roll": 14, "ease": "expo_in"},
    {"at": 1.0, "pos": [fall_top[0], fall_top[1] - 26, fall_top[2] + 2], "look": [float(P1[0]), float(P1[1]) - 34, float(P1[2]) + 5], "roll": 15}]
SHOTS[-1]["scene"]["layers"].append({"kind": "slot", "slot": "c12_p16_p01", "pos": [float(P1[0]), float(P1[1]) - 6, float(P1[2]) + 0.5],
                                     "rot": [0, 0, 0], "width": 2.2})
SHOTS[-1]["_stations"] += [(169.42, "c12_p02_p01", "高空坠落当作赌注以搏：镜头随她坠落，校舍外墙与记忆从身边掠过"),
                           (178.9, "-", "落地——黑")]

# ================================================================== PART 3 — Shizuka (no Takopi)
T = Take(179.04, 231.30, "summer", "静香：丝带 → 唯 死以解脱")
thread_pts = []
P, n = T.station(179.04, "c3_p20_p02", dist=6.5, note="渺茫的洒脱：保健所长椅上，一个人")
thread_pts.append(P + n * 0.8 + np.array([0, -1.2, 0]))
P, n = T.station(184.30, "c3_p22_p01", note="母亲出门“晚饭随便吃点”，门关上")
thread_pts.append(P + n * 0.8 + np.array([0, -1.2, 0]))
P, n = T.station(189.80, "c1_p27_p01", dist=6.5, note="★DROP：满身伤痕站在路上（闪白 3）")
FLASH_AT.append(189.80)
thread_pts.append(P + n * 0.8 + np.array([0, -1.2, 0]))
P, n = T.station(191.26, "c11_p14_p01", world="room", note="如困兽在夹缝中辗转流落：黑色的眼")
T.add({"kind": "cage", "pos": (P + n * 2.0).round(3).tolist(), "rot": [0, 0, 0], "width": 6.5, "bars": 9, "aspect": 0.7, "color": "#06080c",
       "light": False})
thread_pts.append(P + n * 0.8 + np.array([0, -1.2, 0]))
P, n = T.station(197.54, "c3_p11_p01", world="room", note="倘若选择死亡是否能解脱：哭着喊查比")
thread_pts.append(P + n * 0.8 + np.array([0, -1.2, 0]))
P, n = T.station(203.44, "c1_p32_p01", crop=[0.16, 0.48, 0.34, 0.52], char=False, world="room",
                 note="跃下后形同小丑：借来的和好丝带（只拍丝带）")
thread_pts.append(P + n * 0.6)
P, n = T.station(209.46, "c2_p19_p01", world="room", note="微弱呼救却被笑声所淹没：笑声（回忆中的霸凌）")
thread_pts.append(P + n * 0.8 + np.array([0, -1.2, 0]))
P, n = T.station(215.54, "c1_p37_p01", crop=[0.28, 0.0, 0.36, 1.0], char=False, world="room", note="放弃吧：悬空的鞋")
T.station(217.03, "c1_p37_p02", crop=[0.28, 0.0, 0.36, 1.0], char=False, world="room", step=1.5, note="")
T.station(218.52, "c1_p37_p03", crop=[0.28, 0.0, 0.36, 1.0], char=False, world="room", step=1.5, note="认清这结果")
P, n = T.station(220.28, "c1_p36_p03", char=False, world="room", dist=6.0, note="但 伏诛俗世：横梁上的丝带")
thread_pts.append(P + n * 0.5 + np.array([0, 1.5, 0]))
P, n = T.station(224.40, "c1_p35_p01", dist=7.5, world="room", creep=-0.35, note="唯 死以解脱：上吊的房间，缓慢后拉，结束于黑")
T.add({"kind": "thread", "points": [p.round(3).tolist() for p in thread_pts], "width": 0.035, "color": "#a01a26", "sag": 0.35,
       "sway": 0.04, "grow": {"keys": [[179.4, 0.02], [222.0, 1.0]], "ease": "linear"}, "light": False})
T.add({"kind": "glow", "pos": (P + np.array([3.0, 1.5, 2.0])).round(3).tolist(), "width": 8, "color": "#5a4a30"})
T.build()
text(180.0, 184.0, "久世しずか", pos=(0.84, 0.5), size=40)


# ================================================================== assemble
def build():
    S = sorted(SHOTS, key=lambda s: s["start"])
    shots = []
    for i, s in enumerate(S):
        sh = {k: v for k, v in s.items() if not k.startswith("_")}
        sh["id"] = f"t{i + 1:02d}"
        efx = [{"type": "flicker", "amount": EF.get("flicker", 0.04)}, {"type": "drift_shake", "amount": 2}]
        if s.get("_montage"):
            if s.get("_gmap"):
                g = s["_gmap"]
                efx.insert(0, {"type": "duotone", "shadow": g[0], "mid": g[1], "highlight": g[2], "amount": 0.95})
            else:
                efx.insert(0, {"type": "mono"})
            efx += [{"type": "rgb_split", "amount": EF["rgb_split_max"]}, {"type": "flash", "on": "start", "amount": 0.25, "decay": 0.12}]
        for ft in FLASH_AT:
            if sh.get("scene") and s["start"] <= ft < (S[i + 1]["start"] if i + 1 < len(S) else 999):
                efx += [{"type": "flash", "on": [ft], "amount": 0.85, "decay": 0.6},
                        {"type": "shake", "on": [ft], "amount": EF["shake_max"], "freq": EF["shake_freq"], "decay": 0.6},
                        {"type": "zoom_punch", "on": [ft], "amount": EF["zoom_punch_max"], "attack": 0.08, "decay": 0.8}]
        sh["effects"] = efx
        prev = S[i - 1] if i else None
        if i == 0:
            sh["transition"] = {"type": "fade", "dur": 2.0}
        elif s.get("_montage") or (prev and prev.get("_montage")):
            sh["transition"] = {"type": "cut"}
        else:
            sh["transition"] = {"type": "fade", "dur": 0.6}   # both sides are deep in fog: an invisible join
        shots.append(sh)
    project = {
        "meta": {"title": "takopi_mad_v3", "width": 1920, "height": 1080, "fps": 24, "audio": "song.mp3", "beats": "beats.json",
                 "start": 0, "end": 231.3, "crf": 20, "cutouts": "cutouts", "font": FONT_Q, "sfx": SFX},
        "style": {"effects": [{"type": "grain", "amount": EF["grain"]}, {"type": "vignette", "amount": EF["vignette"]},
                              {"type": "flash", "on": [229.4], "attack": 1.8, "decay": 3, "color": "#000000", "amount": 1.0}],
                  "mg": MG + [{"type": "glitch_blocks", "on": [104.30, 104.67, 105.04, 105.42, 105.79, 106.16], "count": 6,
                               "color": "#ffffff", "dur": 0.08, "blend": "difference", "opacity": 0.5}]},
        "shots": shots,
        "texts": TEXTS,
    }
    def clean(x):
        if isinstance(x, dict):
            return {k: clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [clean(v) for v in x]
        if isinstance(x, np.generic):
            return x.item()
        if isinstance(x, np.ndarray):
            return clean(x.tolist())
        return x
    project = clean(project)
    with open(os.path.join(ROOT, "project_v3.yaml"), "w", encoding="utf-8") as f:
        f.write("# generated by build_v3.py\n")
        yaml.safe_dump(project, f, allow_unicode=True, sort_keys=False, width=200)
    L = ["# 分镜 v3 — 章鱼噼的原罪 × 唯死以解脱（压抑 / 三段式 / 长镜头 3D 空间）", "",
         "每个“长镜头”是一次不间断的摄像机运动，依次经过空间中的画格站点；长镜头之间通过飞入雾中/黑页衔接，唯一的硬切是你要求的真理奈之死闪切。", ""]
    for s in S:
        if s.get("scene"):
            L.append(f"## {int(s['start'] // 60)}:{s['start'] % 60:05.2f}  {s['_note']}")
            for t, pid, note in s["_stations"]:
                if note:
                    L.append(f"- {int(t // 60)}:{t % 60:05.2f}  `{pid}`  {note}")
            L.append("")
        elif s.get("_note"):
            L.append(f"## {int(s['start'] // 60)}:{s['start'] % 60:05.2f}  {s['_note']}（平面闪切）")
            L.append("")
    L.append(f"闪白：{FLASH_AT}（上限 {LIM['transitions']['flash_max_total']}）")
    L.append(f"人物槽位（{len(SLOTS)}）：" + "、".join(sorted(SLOTS)))
    open(os.path.join(ROOT, "storyboard_v3.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    assert len(FLASH_AT) <= LIM["transitions"]["flash_max_total"]
    print(f"{len(shots)} shots, {sum(1 for s in S if s.get('scene'))} long takes, {len(SLOTS)} slots, flashes {FLASH_AT}")
    return SLOTS


if __name__ == "__main__":
    build()
