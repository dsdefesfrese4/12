---
name: mad-blender
description: Build real 3D sets for a static MAD in Blender with Python (bpy) — rooms and props from primitives, flat one-colour-per-block toon materials, manga ink lines, moonlight/lamp lighting with real shadows, eased camera paths — then render and export a renderer-agnostic scene JSON (geometry, colours, lights, per-frame camera) for reproduction in After Effects. Use when a scene needs to be walked through in 3D without the stretching/parallax artefacts of depth-map "fake 3D".
---

# 真实建模布景（Blender + Python）

为什么：深度图投影（depth3d）的“假 3D”在镜头移动和上色后穿帮明显。场景改为**按原作画格用几何体建模**。

```
blender -b --factory-startup -P sets/<set>.py -- still out.png <frame>
blender -b --factory-startup -P sets/<set>.py -- anim <out_dir> <f0> <f1>
blender -b --factory-startup -P sets/<set>.py -- export <scene.json>
```
（`apt-get install blender libegl1 libgl1`；EEVEE 可用。Cycles 需 `use_denoising=False`。启动时的 `_distutils_hack` 报错无害。）

## 工具库 `scripts/toonkit.py`
- 场景：`reset(res, fps)`、`world_color(hex)`
- 材质：`toon(name, lit_hex, shadow_hex)`（Shader→RGB→常量色带 = 一块一个颜色，受光/阴影两档）、`glow_mat`（窗外夜色、灯，不投影）、`image_mat`/`card`（漫画格、人物抠图做成立牌）
- 几何：`box(name, (x,y,z), bottom_centre, mat, rot, bevel)`、`plane`、`cylinder`、`room(w,d,h, wall, floor, ceiling)`（-Y 侧开口给镜头）、`window_hole`（布尔开窗）、`table`、`chair`、`group`
- 光：`sun`（月光/日光，真实投影，透过窗洞落在桌面）、`point`、`area`
- 线：`ink_lines(thickness, color)`（Freestyle 轮廓 + 折线 = 漫画墨线）
- 镜头：`camera([(frame, pos, look_at, roll_deg), ...], fov)`，贝塞尔缓入缓出
- 输出：`still`、`render`、**`export_scene(json)`**

## 建一个场景的步骤
1. 在原作画格上叠网格（review 图）读出：房间尺寸、家具位置、视角/视平线、光源方向。
2. 用 `room` + 家具几何体按米为单位搭出来（日本住宅：层高 2.4，桌高 0.72，椅座 0.44）。
3. 每种材质一个 `toon` 颜色（受光色 + 阴影色），配色遵守 mad-style 的 palette。
4. 光：一盏主光决定情绪（夜 = 冷月光从窗入；家暴 = 顶灯硬光；黄昏 = 低角度暖光），一盏很弱的补光。
5. 镜头关键帧对齐歌词时间（frame = 秒 × fps）。人物：`card()` 立牌放进场景（抠图完成后替换）。
6. 先出 1、中、末三帧 still 检查，再渲染动画。

## AE 复现：`export_scene` 的 JSON
- `objects[]`：名称、`matrix_world`、`dimensions`、世界坐标包围盒、颜色（受光/阴影线性 RGB，或图片路径）
- `lights[]`：类型、能量、颜色、矩阵
- `camera[]`：逐帧位置、XYZ 旋转（度）、fov、焦距（像素）；`ae.position_px`（1 m = 100 px，AE：x 右、y 下、z 前）
之后由另一个 skill 把它转成 AE 的 3D 图层和摄像机（盒子 → 6 个纯色 3D 图层；平面 → 1 个；图片卡 → 素材图层）。
