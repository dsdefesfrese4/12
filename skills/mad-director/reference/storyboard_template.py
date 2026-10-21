"""章鱼噼的原罪 × 唯死以解脱 — full-song storyboard -> project.yaml, storyboard.md, cutout_tasks.md

Edit the SHOTS table and re-run:  python3 build_storyboard.py
Times are song seconds (or b/d expressions). Image ids are panel ids (panels/<id>.png) or page ids (pages/<id>.jpg).
"""
import json
import os

import cv2
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------ section palettes / moods
SECTIONS = [
    # name, start, end, duotone (shadow, mid, highlight), particles, energy
    ("intro", 0.0, 24.80, ("#05070f", "#2a3150", "#e6ecff"), "stars", 0),
    ("verse1", 24.80, 47.30, ("#0e0c0b", "#5a5148", "#efe6d8"), "dust", 1),
    ("build", 47.30, 60.81, ("#0d0a0a", "#5e3c38", "#f3e7df"), "ash", 2),
    ("chorus1", 60.81, 107.30, ("#0b0204", "#6e1418", "#f6e8e2"), "ash", 3),
    ("stop", 107.30, 108.96, ("#000000", None, "#ffffff"), None, 0),
    ("verse2", 108.96, 131.80, ("#03090c", "#2c4a50", "#e0f0ee"), "snow", 1),
    ("chorus3", 131.80, 179.04, ("#0a0103", "#7a1016", "#ffe9e0"), "ash", 3),
    ("bridge", 179.04, 189.80, ("#140c04", "#8a6a3a", "#fff6df"), "dust", 2),
    ("final", 189.80, 227.40, ("#0a0814", "#5a4a6a", "#fff4e6"), "stars", 3),
    ("outro", 227.40, 232.0, ("#202020", None, "#ffffff"), None, 0),
]


def section_at(t):
    for s in SECTIONS:
        if s[1] <= t < s[2]:
            return s
    return SECTIONS[-1]


# ------------------------------------------------------------------ the storyboard
# (start, image, options)
#   cam: preset name or dict;  fx: extra effects;  tr: transition into this shot
#   char: True -> character slot (auto box) / list box;  card: 3D floating panel spec
#   crop: [x,y,w,h] normalised;  note: what / why (goes into storyboard.md)
S = []


def shot(t, img, **o):
    S.append((t, img, o))


# INTRO — stars, the encounter. slow, cold, breathing
shot(0.00, "c1_p03_p02", cam="pan_right", tr="fade", note="宇宙中的快乐星人飞船，黑场渐显")
shot(6.80, "c1_p26_p01", cam={"keys": [{"at": 0, "zoom": 1.05, "center": [0.5, 0.78]}, {"at": 1, "zoom": 1.25, "center": [0.5, 0.42]}], "ease": "sine"},
     card={"scale": 0.86, "ry": {"from": -9, "to": 6}, "rx": {"from": 5, "to": -2}}, char=True, tr="fade",
     note="银河下的静香与查比（第1话名场面），3D 浮空卡片缓慢转动，镜头从脚下仰到脸")
shot(12.82, "c1_p06_p02", cam="pan_left", char=True, note="静香闭眼的侧脸（“看到静香香就总感觉…”）")
shot(15.81, "c1_p05_p02", cam="push_in", char=True, note="静香回头")
shot(17.30, "c1_p17_p01", cam="pan_right", char=True, note="和查比奔跑——短暂的幸福")
shot(20.32, "c1_p21_p04", cam="push_in", char=True, note="夜路“一起来玩吧”")
shot(23.31, "TITLE", note="标题卡：唯死以解脱 / 章鱼噼的原罪")
# VERSE 1 — bullying, coldness
shot(24.80, "c2_p02_p01", cam={"keys": [{"at": 0, "zoom": 1.15, "center": [0.5, 0.35]}, {"at": 1, "zoom": 1.35, "center": [0.5, 0.62]}]},
     card={"scale": 0.84, "ry": {"from": 8, "to": -4}, "rz": -1.5}, char=True, tr="flash", note="旁人不掩的冷漠｜教室，被涂鸦的课桌")
shot(27.82, "c2_p03_p01", cam={"zoom": [1.1, 1.45], "focus": [0.62, 0.32], "ease": "ease_out"}, char=True, note="扬唇讽我执着｜真理奈“早啊寄生虫♡”")
shot(30.81, "c1_p09_p01", cam="pan_down", char=True, note="抹杀最后的虚弱｜森林里背着书包的静香")
shot(33.81, "c2_p17_p01", cam={"zoom": [1.2, 1.45], "focus": [0.45, 0.45]}, char=True, note="静香“对不起”")
shot(36.78, "c1_p27_p01", cam={"keys": [{"at": 0, "zoom": 1.0, "center": [0.5, 0.85]}, {"at": 1, "zoom": 1.15, "center": [0.5, 0.25]}], "ease": "ease_in_out"},
     card={"scale": 0.8, "ry": {"from": -6, "to": 4}, "rx": 3}, char=True, note="挣扎中迷失自我｜满身伤痕站在路上，从脚仰到脸")
shot(39.82, "c1_p21_p01", cam="pull_out", fx=[{"type": "particles", "kind": "stars", "opacity": 0.9}], note="黑暗逐渐吞没｜夜空与电线杆")
shot(42.84, "c1_p20_p01", cam={"zoom": [1.05, 1.3], "focus": [0.35, 0.5]}, fx=[{"type": "leak", "color": "#ffb070", "amount": 0.35}],
     char=True, note="胸中残存的余热｜深夜抱着查比（暖光）")
# BUILD — words hit one by one
shot(47.32, "c1_p17_p04", cam="slam", fx=["hit"], char=True, tr="flash", note="谁笑着｜静香的笑")
shot(49.12, "c3_p11_p01", cam="slam", fx=["hit"], char=True, tr="whip_left", note="似哭了｜静香的泪")
shot(50.38, "c4_p13_p01", cam="slam", fx=["hit", "rgb"], char=True, tr="whip_right", note="挣扎着｜真理奈“把爸爸还给我”")
shot(52.42, "c11_p14_p01", cam="slam", fx=["hit"], char=True, tr="whip_left", note="麻木了｜黑眼的静香")
shot(53.88, "c4_p19_p01", cam={"zoom": [1.8, 1.15], "ease": "expo_out", "rotate": [-6, 0]},
     fx=["hit", "rgb", {"type": "flash", "on": "start", "color": "#b0141c", "amount": 0.7, "decay": 0.4}], tr="flash",
     note="刀划破血肉竟如此快活｜沾血的快乐照相机")
shot(56.31, "c4_p21_p01", cam="pan_up", char=True, note="浑身是血站着的静香")
shot(59.52, "c4_p28_p01", cam={"keys": [{"at": 0, "zoom": 1.0, "center": [0.5, 0.3]}, {"at": 1, "zoom": 1.2, "center": [0.5, 0.7]}]},
     card={"scale": 0.82, "ry": {"from": 7, "to": -7}}, char=True, note="麻木地行走着不如木偶｜树林中呆立的静香与章鱼噼")
# CHORUS 1
shot(64.34, "c10_p01_p01", cam={"zoom": [1.7, 1.2], "focus": [0.4, 0.62], "ease": "expo_out"}, fx=["hit", "lines"], char=True, tr="flash",
     note="不予借口辩驳｜润也“那人是你杀的吧”")
shot(67.08, "c8_p21_p06", cam="push_in", char=True, tr="whip_up", note="如何做个哑巴苟活｜东君哭泣")
shot(69.80, "c5_p13_p01", cam={"keys": [{"at": 0, "zoom": 1.1, "center": [0.5, 0.75]}, {"at": 1, "zoom": 1.4, "center": [0.45, 0.35]}], "ease": "expo_in"},
     char=True, note="“我只有东君了 帮帮我”——蓄力")
shot(71.31, "c1_p35_p01", cam={"zoom": [1.6, 1.05], "ease": "expo_out", "rotate": [4, 0]},
     fx=["hit", "big", {"type": "speed_lines", "opacity": 0.5, "end": 72.8}], tr="flash",
     note="★绝望的藤蔓生于指尖交错｜上吊的房间（全曲第一个大爆点）")
shot(74.30, "c1_p37_p01", cam="pan_left", note="悬空的鞋")
shot(75.81, "c1_p36_p03", cam={"zoom": [1.1, 1.3], "rotate": [0, -3]}, note="横梁上的丝带")
shot(77.84, "c1_p38_p01", cam={"zoom": [1.05, 1.35], "focus": [0.35, 0.55]}, char=True, tr="flash", note="逐渐吞噬不堪重负的躯壳｜倒地的静香“死掉了？”")
shot(80.32, "c1_p38_p02", cam="push_in", fx=[{"type": "shake", "on": "beat", "amount": 10, "decay": 0.12}], note="章鱼噼“为什么”")
shot(83.48, "c15_p07_p01", cam="slam", fx=["hit", "lines", {"type": "shake", "on": "beat", "amount": 14}], char=True, tr="flash",
     note="嘶吼着试图驱逐心里的魔｜静香崩溃大喊")
shot(86.31, "c16_p11_p01", cam={"zoom": [1.15, 1.4], "focus": [0.5, 0.4]}, fx=["rgb"], char=True, tr="whip_right", note="真理奈“把我的家人还给我!!”")
shot(89.38, "c13_p16_p01", cam={"zoom": [1.0, 1.5], "focus": [0.5, 0.62], "ease": "ease_in"},
     fx=[{"type": "glitch", "on": "downbeat", "decay": 0.15, "amount": 40}], tr="black",
     note="殊不知灵魂早已被妖魔胁迫｜章鱼噼“我必须要去杀掉久世静香”")
shot(93.81, "c13_p09_p01", cam={"keys": [{"at": 0, "zoom": 1.0, "center": [0.5, 0.8]}, {"at": 1, "zoom": 1.3, "center": [0.6, 0.25]}], "ease": "expo_in"},
     fx=["lines", {"type": "shake", "amount": 8}], tr="whip_up", note="火箭发射")
shot(95.60, "c1_p10_p03", cam="pan_right", char=True, tr="flash", note="觊觎着｜幻想中在天上飞")
shot(97.40, "c10_p19_p02", cam="pan_left", char=True, note="不得的自由｜“去东京！”")
shot(99.82, "c4_p25_p01", cam={"zoom": [1.25, 1.45], "center": [[0.5, 0.42], [0.5, 0.4]], "ease": "sine"},
     fx=["breathe", {"type": "glow", "threshold": 0.55, "amount": 0.4, "radius": 16}], char=True, tr="fade",
     note="谁言语淬毒｜“谢谢你 章鱼噼”（闭眼笑，复刻你的 AE 段）")
shot(102.82, "c4_p26_p01", cam={"zoom": [1.25, 1.6], "center": [[0.5, 0.45], [0.5, 0.48]], "ease": "ease_in"},
     fx=["breathe", {"type": "glow", "threshold": 0.55, "amount": 0.4, "radius": 16}, {"type": "zoom_blur", "on": "start", "amount": 0.12, "decay": 0.3}],
     char=True, tr="flash", note="封锁我歌喉｜睁眼“帮我杀了她”")
shot(107.30, "c4_p29_p01", cam={"zoom": [1.0, 1.04], "ease": "linear"}, fx=["mono"], tr="cut", note="■音乐骤停：《章鱼噼的原罪》标题页，全静止")
# VERSE 2 — loneliness, the 2022 world, cold teal
shot(108.96, "c14_p13_p02", cam="pan_right", tr="fade", note="孤独已将我吞没｜章鱼噼独自在土管上等待")
shot(112.12, "c12_p16_p01", cam={"zoom": [1.1, 1.3], "focus": [0.45, 0.4]}, char=True, note="为掩心底无措｜真理奈“最近好像也没那么坏了”")
shot(115.12, "c12_p02_p01", cam="pan_down", card={"scale": 0.84, "ry": {"from": -8, "to": 3}}, char=True, note="于人前故作淡漠｜脸上带疤走进学校")
shot(120.62, "c8_p21_p03", cam="pull_out", note="狂奔着捂住耳朵｜夜色中远处的人影")
shot(122.28, "c8_p21_p04", cam="push_in", char=True, note="缩成一团的东君")
shot(124.08, "c10_p19_p02", cam={"zoom": [1.3, 1.1], "center": [[0.3, 0.5], [0.6, 0.5]]}, char=True, tr="whip_left", note="奢求就此逃脱｜涩谷人群")
shot(127.10, "c12_p07_p01", cam="pan_down", fx=[{"type": "glitch", "on": "beat", "every": 2, "decay": 0.12, "amount": 30}], char=True,
     note="如蛆附骨的折磨｜酗酒的母亲")
shot(129.82, "c13_p06_p01", cam={"zoom": [1.05, 1.4], "center": [[0.3, 0.5], [0.25, 0.7]], "ease": "expo_in"}, tr="black",
     note="命案现场——蓄力进副歌")
# CHORUS 3 — the original sin, blood
shot(131.80, "c13_p08_p01", cam="slam", fx=["hit", "rgb"], char=True, tr="flash", note="肆意地｜血泪的真理奈")
shot(133.60, "c4_p14_p01", cam="slam", fx=["hit", "lines"], char=True, tr="whip_right", note="发泄着｜章鱼噼挥起照相机")
shot(134.64, "c10_p10_p01", cam="slam", fx=["hit"], char=True, tr="whip_left", note="咆哮着｜“直树!!!”")
shot(136.46, "c4_p15_p02", cam={"zoom": [1.3, 1.0], "ease": "expo_out"}, fx=["hit", "big"], tr="flash", note="毁灭了｜“咚”")
shot(137.58, "c4_p17_p01", cam={"zoom": [1.0, 1.35], "focus": [0.45, 0.4]}, char=True, note="与这深渊拼个鱼死网破｜倒在地上的真理奈")
shot(140.29, "c4_p23_p01", cam={"keys": [{"at": 0, "zoom": 1.0, "center": [0.5, 0.2]}, {"at": 1, "zoom": 1.15, "center": [0.5, 0.7]}]},
     card={"scale": 0.8, "ry": {"from": 10, "to": -4}, "rz": {"from": 2, "to": -2}}, char=True, note="“就好像魔法一样”")
shot(143.42, "c5_p11_p03", cam="pan_left", char=True, tr="flash", note="像地底蝼蚁在自我撕扯｜黑暗中的眼")
shot(146.31, "c11_p15_p01", cam={"zoom": [1.0, 1.3]}, fx=[{"type": "glitch", "on": "beat", "decay": 0.12, "amount": 50}], note="“你的原罪”")
shot(148.26, "c3_p13_p02", cam={"zoom": [1.0, 1.25], "rotate": [-8, 0], "ease": "expo_out"}, fx=["hit"], tr="zoom", note="深陷绝望漩涡｜第3次")
shot(149.30, "c3_p13_p04", cam={"zoom": [1.0, 1.25], "rotate": [8, 0], "ease": "expo_out"}, fx=["hit"], tr="zoom", note="第10次 / 第25次")
shot(150.06, "c3_p12_p01", cam={"zoom": [1.3, 1.0], "rotate": [-10, 0], "ease": "expo_out"}, char=True, tr="zoom", note="时间循环的静香")
shot(151.00, "c16_p04_p02", cam="pan_right", fx=["rgb"], char=True, tr="flash", note="谁能说破孰对孰错｜真理奈的眼")
shot(153.81, "c16_p11_p02", cam="pan_left", note="夜里森林中的两人")
shot(155.32, "c8_p19_p01", cam={"zoom": [1.1, 1.4], "focus": [0.35, 0.5]}, char=True, tr="flash", note="只窥得世人心中纲常丑恶｜“我对你已经不抱希望了”")
shot(158.31, "c8_p19_p03", cam="pan_right", note="54分的试卷")
shot(161.66, "c13_p14_p01", cam="pan_down", card={"scale": 0.82, "ry": {"from": -9, "to": 5}}, char=True, tr="flash",
     note="彻底沦为腐化败坏的偏颇｜“我一定会让你快乐的噗”")
shot(164.30, "c11_p14_p01", cam={"zoom": [1.0, 1.25], "center": [[0.5, 0.35], [0.5, 0.42]]}, fx=["rgb"], char=True, note="黑眼的静香")
shot(167.30, "c13_p09_p01", cam={"keys": [{"at": 0, "zoom": 1.2, "center": [0.5, 0.75]}, {"at": 1, "zoom": 1.5, "center": [0.6, 0.3]}], "ease": "expo_in"},
     fx=["lines", {"type": "shake", "amount": 12}], note="火箭——")
shot(169.42, "c1_p03_p02", cam={"zoom": [1.0, 1.6], "rotate": [0, 12], "ease": "expo_in"}, fx=["lines"], tr="whip_up", note="高空坠落当作赌注以搏｜坠入宇宙")
shot(172.96, "c15_p16_p01", cam="slam", fx=["hit", {"type": "glow", "threshold": 0.5, "amount": 0.7, "radius": 20}], char=True, tr="flash",
     note="能否交换夺过｜快乐照相机“光芒四射”")
shot(175.60, "c15_p04_p01", cam={"zoom": [1.1, 1.3]}, fx=[{"type": "shake", "on": "beat", "amount": 12}], tr="whip_down", note="挣扎叛逆却不能得｜踩住章鱼噼的脚")
# BRIDGE — dissolution, gold light
shot(179.04, "c15_p17_p01", cam={"zoom": [1.05, 1.35], "ease": "sine"}, fx=["holy"], char=True, tr="flash", note="渺茫的洒脱｜章鱼噼消散“我一定会让静香香…”")
shot(182.30, "c15_p16_p04", cam="push_in", fx=["holy"], char=True, tr="fade", note="“如果连章鱼噼都不在了”")
shot(184.30, "c15_p18_p01", cam={"zoom": [1.0, 1.3], "focus": [0.4, 0.6]}, fx=["holy"], char=True, tr="fade", note="“致我最重要的你”")
shot(186.80, "c15_p18_p03", cam="pan_left", fx=["holy"], char=True, tr="fade", note="“再见了”")
shot(188.31, "c15_p16_p03", cam={"zoom": [1.0, 1.6], "ease": "expo_in"}, fx=["holy", {"type": "flash", "start": 188.9, "end": 189.9, "attack": 0.9, "on": [189.8], "decay": 0.3, "amount": 1.0}],
     tr="fade", note="“消散”——白光吞没，进入最终副歌")
# FINAL CHORUS — the world without Takopi; despair lyrics vs. the two girls finally talking
shot(189.80, "c15_p19_p01", cam={"keys": [{"at": 0, "zoom": 1.6, "center": [0.55, 0.35]}, {"at": 0.25, "zoom": 1.15, "center": [0.55, 0.4], "ease": "expo_out"}, {"at": 1, "zoom": 1.05, "center": [0.5, 0.5]}]},
     card={"scale": 0.84, "ry": {"from": -5, "to": 5}}, fx=["hit", "big"], char=True, tr="flash", note="★DROP｜没有章鱼噼的夏天，坐在土管上的静香")
shot(191.26, "c11_p08_p01", cam="pan_up", char=True, note="如困兽在夹缝中｜满身脏污的静香")
shot(194.72, "c14_p16_p01", cam={"zoom": [1.05, 1.3], "focus": [0.4, 0.4]}, char=True, note="辗转流落｜花瓣中的静香")
shot(197.54, "c1_p43_p01", cam="pan_right", tr="flash", note="倘若选择死亡｜“让我们一起考虑在怎样的未来你才可以不用死掉”")
shot(200.10, "c1_p35_p01", cam={"zoom": [1.2, 1.1]}, fx=["mono"], tr="cut", note="是否能解脱｜上吊房间闪回")
shot(201.31, "c15_p12_p02", cam={"zoom": [1.1, 1.3], "focus": [0.35, 0.5]}, char=True, tr="flash", note="“对不起哦”——抱住静香的章鱼噼")
shot(203.44, "c16_p04_p01", cam={"zoom": [1.3, 1.1], "focus": [0.4, 0.4], "ease": "expo_out"}, fx=["hit"], char=True, tr="whip_left", note="跃下后形同小丑｜“早啊寄生虫”——循环又开始")
shot(206.31, "c16_p11_p02", cam="pan_right", note="躺在血泊｜夜里扭打的两人")
shot(209.46, "c16_p16_p01", cam={"keys": [{"at": 0, "zoom": 1.1, "center": [0.5, 0.42]}, {"at": 1, "zoom": 1.35, "center": [0.5, 0.25]}], "ease": "sine"},
     fx=[{"type": "leak", "color": "#ffc080", "amount": 0.4}], char=True, tr="flash", note="微弱呼救却被笑声所淹没｜但这次，两人抱头大哭")
shot(215.54, "c16_p18_p01", cam="pan_left", char=True, tr="flash", note="放弃吧｜你（东君）")
shot(216.80, "c16_p18_p02", cam="pan_right", char=True, tr="whip_right", note="你（真理奈）")
shot(218.29, "c16_p18_p03", cam="push_in", char=True, tr="whip_left", note="认清这结果｜你（静香）")
shot(220.28, "c16_p19_p01", cam={"keys": [{"at": 0, "zoom": 1.15, "center": [0.5, 0.75]}, {"at": 1, "zoom": 1.05, "center": [0.5, 0.3]}], "ease": "sine"},
     card={"scale": 0.86, "ry": {"from": 4, "to": -4}, "rx": {"from": -4, "to": 2}}, fx=[{"type": "particles", "kind": "stars", "count": 220}],
     char=True, tr="flash", note="但 伏诛俗世 唯 死以解脱｜星空下并肩走着的两人——“能够顺利地长大成人”")
shot(224.30, "c16_p02_p01", cam={"zoom": [1.1, 1.3], "focus": [0.45, 0.45]}, fx=[{"type": "leak", "color": "#ffd090", "amount": 0.4}], char=True,
     tr="fade", note="“早上好 静香香”——和查比在一起的早晨")
shot(227.40, "c16_p20_p01", cam={"zoom": [0.42, 0.46], "ease": "linear", "clamp": False, "center": [[0.5, 0.42], [0.5, 0.42]]}, fit="contain_white", tr="flash", note="谢谢你们 / 拜拜（白底小章鱼噼）")

FX_PRESETS = {
    "hit": [{"type": "zoom_punch", "on": "start", "amount": 0.06, "attack": 0.05, "decay": 0.4},
            {"type": "shake", "on": "start", "amount": 18, "decay": 0.35}],
    "big": [{"type": "flash", "on": "start", "amount": 0.9, "decay": 0.45},
            {"type": "zoom_blur", "on": "start", "amount": 0.18, "decay": 0.35}],
    "rgb": [{"type": "rgb_split", "on": "beat", "amount": 9, "decay": 0.15}],
    "lines": [{"type": "speed_lines", "opacity": 0.45, "count": 160}],
    "mono": [{"type": "threshold", "level": 0.55, "amount": 0.6}],
    "breathe": [{"type": "drift_shake", "amount": 3}],
    "holy": [{"type": "glow", "threshold": 0.45, "amount": 0.7, "radius": 22, "color": "#fff0c8"},
             {"type": "light_sweep", "period": 2.8, "amount": 0.3}],
}

# per-energy beat-sync defaults (applied on top of each shot)
ENERGY_FX = {
    0: [{"type": "drift_shake", "amount": 3}],
    1: [{"type": "drift_shake", "amount": 4}],
    2: [{"type": "drift_shake", "amount": 4}, {"type": "zoom_punch", "on": "downbeat", "amount": 0.015, "attack": 0.07, "decay": 0.4}],
    3: [{"type": "drift_shake", "amount": 5},
        {"type": "zoom_punch", "on": "downbeat", "amount": 0.022, "attack": 0.07, "decay": 0.45},
        {"type": "flash", "on": "downbeat", "amount": 0.12, "decay": 0.25, "mode": "add"}],
}


def image_path(img):
    if os.path.exists(os.path.join(ROOT, "panels", img + ".png")):
        return f"panels/{img}.png"
    if os.path.exists(os.path.join(ROOT, "pages", img + ".jpg")):
        return f"pages/{img}.jpg"
    raise FileNotFoundError(img)


def char_boxes():
    p = os.path.join(ROOT, "cutouts_auto", "boxes.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def build():
    boxes = char_boxes()
    shots, md, tasks = [], [], []
    lyrics = json.load(open(os.path.join(ROOT, "lyrics_timed.json"), encoding="utf-8"))
    for i, (t, img, o) in enumerate(S):
        sec = section_at(t)
        end = S[i + 1][0] if i + 1 < len(S) else 231.3
        sid = f"s{i + 1:03d}"
        if img == "TITLE":
            sh = {"id": sid, "start": t, "image": "assets/black.png", "camera": {"preset": "static"},
                  "effects": [{"type": "particles", "kind": "stars", "count": 200}], "transition": {"type": "fade", "dur": 0.4}}
            shots.append(sh)
            md.append((sid, t, end, "—", "标题卡", o.get("note", ""), sec[0]))
            continue
        cam = o.get("cam", "static")
        cam = {"preset": cam} if isinstance(cam, str) else cam
        sh = {"id": sid, "start": t, "image": image_path(img), "camera": cam}
        if o.get("fit") == "contain_white":
            sh["fit"] = "contain"
            sh["bg_color"] = "#ffffff"
        efx = []
        shadow, mid, high = sec[3]
        if sec[0] not in ("outro",):
            d = {"type": "duotone", "shadow": shadow, "highlight": high, "amount": 0.92 if sec[0] != "stop" else 1.0}
            if mid:
                d["mid"] = mid
            efx.append(d)
        efx += [dict(e) for e in ENERGY_FX[sec[5]]]
        if sec[4] and not any(isinstance(x, dict) and x.get("type") == "particles" for x in o.get("fx", [])):
            efx.append({"type": "particles", "kind": sec[4], "opacity": 0.55 if sec[4] != "ash" else 0.5,
                        "seed": 3 + i})
        for e in o.get("fx", []):
            efx += [dict(x) for x in FX_PRESETS[e]] if isinstance(e, str) else [e]
        sh["effects"] = efx
        tr = o.get("tr", "cut")
        dur = {"flash": 0.18, "fade": 0.5, "black": 0.4, "zoom": 0.25, "whip_left": 0.22, "whip_right": 0.22,
               "whip_up": 0.22, "whip_down": 0.22, "glitch": 0.2}.get(tr, 0.2)
        sh["transition"] = {"type": tr, "dur": dur}
        if o.get("card"):
            sh["card"] = o["card"]
        if o.get("crop"):
            sh["crop"] = o["crop"]
        if o.get("char"):
            slot = img
            box = o["char"] if isinstance(o["char"], list) else boxes.get(img, [0.15, 0.08, 0.7, 0.9])
            sh["char"] = {"slot": slot, "box": [round(v, 3) for v in box]}
            tasks.append((slot, sh["image"], o.get("note", "")))
        shots.append(sh)
        camtxt = cam.get("preset") or ("关键帧" if cam.get("keys") else f"zoom {cam.get('zoom')}")
        extra = []
        if o.get("card"):
            extra.append("3D卡片")
        for e in o.get("fx", []):
            extra.append(e if isinstance(e, str) else e["type"])
        md.append((sid, t, end, img, camtxt + (" + " + "/".join(extra) if extra else ""), o.get("note", ""), sec[0]))

    texts = []
    for L in lyrics:
        sec = section_at(L["start"])
        loud = sec[5] >= 3
        size = 66 if loud else 54
        if L.get("parts"):
            chunks = L["text"].split()
            n = len(chunks)
            for k, (c, ts) in enumerate(zip(chunks, L["parts"] + [L["parts"][-1]] * (n - len(L["parts"])))):
                texts.append({"start": ts, "end": L["end"], "text": c, "anim": "slam" if loud else "pop",
                              "pos": [0.5 + (k - (n - 1) / 2) * 0.17, 0.86], "size": size,
                              "color": "#ffffff", "stroke": {"width": 6, "color": "#120608"}, "out": 0.15})
        else:
            texts.append({"start": L["start"], "end": L["end"], "text": L["text"],
                          "anim": "pop" if loud else ("typewriter" if sec[0] in ("verse1", "verse2") else "fade"),
                          "pos": [0.5, 0.86], "size": size, "color": "#ffffff",
                          "stroke": {"width": 6 if loud else 5, "color": "#120608"}, "out": 0.15})
    texts.append({"start": 23.6, "end": 24.75, "text": "唯死以解脱", "anim": "fade", "fade": 0.4, "pos": [0.5, 0.45], "size": 120,
                  "color": "#f4ecff", "stroke": {"width": 0}, "spacing": 0.35, "out": 0.25})
    texts.append({"start": 23.9, "end": 24.75, "text": "章鱼噼的原罪  ×  STRANGER_BTS", "anim": "fade", "fade": 0.4,
                  "pos": [0.5, 0.58], "size": 34, "color": "#b8c0e0", "stroke": {"width": 0}, "out": 0.25})
    texts.append({"start": 227.9, "end": 231.3, "text": "谢谢你们", "anim": "typewriter", "pos": [0.5, 0.2], "size": 60,
                  "color": "#303030", "stroke": {"width": 0}, "out": 0.6})

    project = {
        "meta": {"title": "takopi_mad_v1", "width": 1920, "height": 1080, "fps": 24, "audio": "song.mp3",
                 "beats": "beats.json", "start": 0, "end": 231.3, "crf": 19, "cutouts": "cutouts"},
        "style": {"effects": [{"type": "grain", "amount": 0.035}, {"type": "vignette", "amount": 0.5},
                              {"type": "flash", "on": [231.3], "attack": 2.5, "decay": 1, "color": "#000000", "amount": 1.0}]},
        "shots": shots,
        "texts": texts,
    }
    with open(os.path.join(ROOT, "project.yaml"), "w", encoding="utf-8") as f:
        f.write("# generated by build_storyboard.py — edit SHOTS there, not here\n")
        yaml.safe_dump(project, f, allow_unicode=True, sort_keys=False, width=200)

    lines = ["# 分镜表 — 章鱼噼的原罪 × 唯死以解脱", "",
             "镜头 | 时间 | 时长 | 段落 | 素材 | 运镜/特效 | 内容", "---|---|---|---|---|---|---"]
    for sid, t, end, img, cam, note, sec in md:
        lines.append(f"{sid} | {int(t // 60)}:{t % 60:05.2f} | {end - t:.2f}s | {sec} | {img} | {cam} | {note}")
    open(os.path.join(ROOT, "storyboard.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

    seen, tl = set(), ["# 抠图任务清单", "", "完成后放到 `cutouts/<槽位>.png`（与原图同尺寸 RGBA，人物不透明）；"
                       "可选 `cutouts/<槽位>_bg.png`（去掉人物并补好背景）。渲染时自动替换占位框。", "",
                       "槽位 | 原图 | 用途", "---|---|---"]
    for slot, path, note in tasks:
        if slot in seen:
            continue
        seen.add(slot)
        tl.append(f"{slot} | {path} | {note}")
    open(os.path.join(ROOT, "cutout_tasks.md"), "w", encoding="utf-8").write("\n".join(tl) + "\n")
    print(f"{len(shots)} shots, {len(texts)} text items, {len(seen)} cutout slots")


if __name__ == "__main__":
    build()
