---
name: mad-render
description: Render a static-MAD project.yaml to video — camera moves on stills, 3D floating cards, character-slot parallax layers, puppet pins, beat-synced effects (zoom punch, spring shake, flash, glow, duotone, particles, light sweeps, glitch, speed lines), transitions and animated lyrics. Use to produce or re-render the final video, previews, stills or contact sheets.
---

# 渲染器

```
export PYTHONPATH=<this skill>/scripts
python3 -m madrender.render project.yaml                       # 1080p 全片 -> out/<title>.mp4（多进程分段 + 合并音频）
python3 -m madrender.render project.yaml --preview             # 半分辨率
python3 -m madrender.render project.yaml --from 1:10 --to b200 # 只渲一段
python3 -m madrender.render project.yaml --still 71.5 d47      # 单帧 PNG（自己检查构图用）
python3 -m madrender.render project.yaml --contact             # 每镜头一格的缩略总表
```
1080p/24fps 带全部特效约 4.5 帧/秒（4 核）。母版很大（颗粒吃码率），交付另转 720p：
`ffmpeg -i master.mp4 -vf "scale=1280:720:flags=lanczos,hqdn3d=1.5:1.5:4:4" -c:v libx264 -preset slow -crf 25 -c:a aac out_720p.mp4`

## project.yaml

```yaml
meta: {title, width: 1920, height: 1080, fps: 24, audio: song.mp3, beats: beats.json,
       start: 0, end: 231.3, crf: 19, cutouts: cutouts, background: "#000"}
style:   {effects: [...]}            # 全局特效（grain、vignette、结尾黑场）
markers: {swap: 102.818}             # 具名时间，可在任何时间表达式里用
shots:
  - id: s025
    start: 71.31                     # 秒 / "1:11.3" / b120 / d47 / chorus1 / swap+0.1 / d47-1b
    image: panels/c1_p35_p01.png
    crop: [x, y, w, h]               # 可选，归一化裁切
    fit: cover | contain             # contain 可配 bg_color
    camera: {preset: slam} | {zoom: [a,b], center: [[x,y],[x,y]], rotate: [a,b], ease, focus: [x,y], clamp}
            | {keys: [{at: 0, zoom, center, rotate, ease}, ...]}
    card: {scale: 0.84, ry: {from: -8, to: 4}, rx, rz, x, y, bg: blur|"#hex", border: true}   # 3D 浮空卡片
    char: {slot: c1_p35_p01, box: [x,y,w,h], parallax: 1.12, puppet: {...}}   # 人物槽位
    layers: [{image, parallax, place: {center, height, move}, opacity: <value>, crop, puppet}]
    effects: [...]
    transition: {type: flash, dur: 0.18}
texts: [{start, end, text, anim: pop|slam|typewriter|fade|slide_up|glitch, pos: [x,y], size, color,
         stroke: {width, color}, vertical, per: beat, out}]
```
相机预设：static push_in push_in_fast pull_out pull_out_fast pan_left/right/up/down tilt_left/right roll_in ken_burns slam drift。
缓动：linear ease_in ease_out ease_in_out expo_in expo_out back_out sine snap。

## 特效（`on:` beat / downbeat / hit / offbeat / start / [时间列表]，`every`、`phase`、`shift`、`attack`、`decay`；不写 on = 持续）
- 运动：`zoom_punch`(amount)、`shake`(amount, freq=3.5 阻尼弹簧，不要每帧随机)、`drift_shake`(amount, 呼吸式漂移)、`rot_punch`
- 画面：`flash`(color, amount, mode add)、`duotone`(shadow, mid, highlight) 段落配色、`grade`、`mono`、`threshold`、`glow`(color)、
  `zoom_blur`、`motion_blur`、`blur`、`rgb_split`、`glitch`、`invert`、`strobe`、`speed_lines`、`vignette`、`grain`、`letterbox`、`scanlines`
- 氛围：`particles`(kind: stars|dust|ash|snow|rain, count, opacity, speed)、`light_sweep`(period, angle, width)、`leak`(color, x, y)
- 转场：cut fade flash black whip_left/right/up/down slide_* zoom glitch wipe_left/right circle（以切点为中心）

## 可动画数值 `<value>`（puppet 引脚、card、layer opacity/move 都能用）
`3.0` | `{from, to, ease, start, end}` | `{keys: [[时间, 值], ...]}` | `{wave: 幅度, period: 4b}` | `{pulse: 幅度, on: beat, decay}` | `[叠加...]`

## 人偶 puppet（作用在 layer / char 上）
`{step: 1|2|3, pins: [{center, radius, hard, pivot, rotate, move: [x,y], scale, lag}]}` — 头摆/点头、头发延迟跟随、肩膀呼吸。
`step: 3` = 一拍三（原画感），相机仍逐帧动。更完整的分部件骨骼（眨眼/视线/嘴型/伪3D转头/头发物理）见 `scripts/madrender/rig.py`。

## 3D 场景（shot.scene，v2）
真透视摄像机 + 图版/元素放在真实深度，自带景深、雾、方向光、体积光、3D 粒子。详细字段见 `scripts/madrender/scene3d.py`、`elements.py` 文件头。
```yaml
scene:
  fov: 40
  fog: {color: "#030303", density: 0.02}
  dof: {focus: 10, aperture: 1.4}
  light: {dir: [0.35, -0.55, 1], color: "#ece6da", ambient: 0.86}
  camera: {keys: [{at: 0, pos: [0,0,0], look: [0,0,10], roll: 0}, {at: 1, pos: [0.2,0,0.9], look: [0,0,10], ease: sine}], handheld: 0.015}
  layers:
    - {kind: image, src: panels/x.png, pos: [0,0,10], width: 9, rot: [0,0,0], frame: border}
    - {kind: slot, slot: x, pos: [0,0,9.4], width: 8.5}        # 抠图到位前是半透明轮廓占位
    - {kind: particles, preset: dust, volume: [[-7,7],[-4,4],[1,11]]}
    - {kind: vines|ribbon|strings|cage|blood|shatter|words|glow|clock|text, ...}
```
## MG 层（shot.mg / style.mg）与日文动态字（texts[].kinetic）
- `mg.py`：ring burst bars frame line crosshair grid stripes ticker counter glitch_blocks invert_rect halftone label
- `kinetic.py`：逐字 in/out/idle 动画、关键词强调色、巨型描边底字、下划线/框线描画、色散、阴影
- 风格限制由 mad-style 决定（压抑只用 frame/line/grid/counter/label + blur_in/fade 的明朝体）。
## 语音/音效混入
`meta.sfx: [{file: assets/voice_1.wav, at: 100.28, gain: 1.6, duck: 0.3, from: 0, to: 0}]` — 在该时间点叠加，原曲压低到 duck。
