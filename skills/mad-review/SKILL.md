---
name: mad-review
description: Frame-by-frame motion analysis of a rendered MAD or AE export — finds keyframe pops, velocity jerks, direction reversals and dropped frames, separating them from intended beat hits and cuts. Use when a user says a video "isn't smooth / 不顺畅 / 卡", or before delivering a render.
---

# 流畅度检查

```
python3 scripts/smoothness.py video.mp4 [--beats beats.json --offset <首帧对应歌曲秒>] [--project project.yaml] [--plot speed.png]
```

每两帧用 ORB + RANSAC 估计全局位移/缩放/旋转，换算成「画面边角每帧移动像素」，标记：
- **POP** 单帧尖峰（关键帧数值跳、时间重映射跳帧）
- **JERK** 相邻帧速度比 > 2.2（线性关键帧、缓动手柄不连续）
- **REVERSE** 一帧内方向反转（没有减速）
- **HOLD** 运动中突然停一帧（重复帧/丢帧）

`--beats` / `--project` 让落在节拍 ±1.5 帧、或镜头切点 -0.15～+0.35s 内的标记归为「有意」。最后一行 `SUMMARY` 给出无理由数量。

经验：
- 每帧随机抖动的 shake 必然大量 JERK；用阻尼弹簧（低频 3–4Hz）代替。冲击类缩放给 ~2 帧的 attack。
- 颗粒 + 粒子 + 平涂大块的画面会让检测器在 2↔10 px/帧之间来回误报，这类交替且幅度小的可忽略，抽帧目测确认。
- 用户 AE 片段的典型问题：速度图断崖（关键帧两侧缓动不一致）、单帧跳（图钉/关键帧值突变）、方向急转无减速。
  报告时给出帧号、时间和在 AE 图表编辑器里怎么修。
