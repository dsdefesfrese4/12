---
name: mad-director
description: Plan, build, render and revise a high-quality 静止系MAD (static/still-image anime music video made from manga panels) end to end — story reading, lyric/beat-synced storyboard, character cutout slots, layered camera/effects, final video. Use when the user wants a MAD / 静止系 / manga music video made from comic pages and a song, or asks to change one ("第3个镜头改成推近", "副歌加闪白", "这里卡点不对").
---

# 静止系 MAD 总控

Claude 无法操作 AE，所以这套 skill 用**代码渲染出成片**：一份工程（`build_storyboard.py` → `project.yaml`）描述全部镜头，
`mad-render` 渲染 1080p 视频，用户用中文说怎么改，就改工程再重渲。高质量静止系 ≠ 幻灯片：每个镜头都要有运镜、层次、节拍反应、光影。

## 工程目录（每个作品一个）

```
<project>/
  pages/ c{话}_p{页}.jpg        原始漫画页（7-Zip 24+ 解 RAR5，系统 unar 会误报损坏）
  panels/ c{话}_p{页}_pNN.png   mad-assets/split_panels.py 切出的格
  song.mp3  beats.json  lyrics.txt  lyrics_timed.json  asr.json
  story_notes.md                剧情笔记 + 关键画格编号（先读完全部漫画再写）
  build_storyboard.py           ★分镜表（唯一需要手改的地方）
  project.yaml                  生成物，渲染器读取
  storyboard.md                 给用户看的分镜表
  cutout_tasks.md               抠图任务清单（人物槽位）
  cutouts/ <槽位>.png [_bg.png]  精修抠图，存在即自动替换占位框
  cutouts_auto/                  rembg 初版抠图 + boxes.json（占位框位置）
  out/  review/
```

## 流程

1. **素材**：解压 → `pages/`；`mad-assets/split_panels.py pages/*.jpg -o panels`（日漫默认右→左阅读序）。
2. **读剧情**：用 6 页/张的拼图（每页标 id）逐张读完全部章节，写 `story_notes.md`：每话要点 + 名场面画格 id + 情绪曲线。
3. **音乐**：`mad-beat/analyze_beats.py song.mp3 -o beats.json`（速度减半/加倍时加 `--bpm`）；
   有歌词时 `mad-beat/transcribe.py song.mp3 --prompt-file lyrics.txt`（faster-whisper，词级时间戳），
   然后把官方歌词逐句对到 ASR 时间写成 `lyrics_timed.json`（`parts` = 同一句里要逐词卡点的子句开始时间）。
   再按小节打印能量/人声强度表，找出：前奏、主歌、副歌爆点、骤停、最后的 drop。
4. **分镜**（核心）：参照 `reference/storyboard_template.py`（本作品的完整实例）写 `build_storyboard.py`：
   - 段落表 `SECTIONS`：每段一个配色（duotone 阴影/中间/高光）、粒子（stars/dust/ash/snow/rain）、能量等级 0–3。
   - 镜头表：`shot(开始秒, 画格id, cam=..., fx=[...], tr=..., char=True, card={...}, note="歌词｜画面")`。
   - 规则：切点放在小节线/歌词起点；副歌大爆点（能量跳变的小节）放全篇最有冲击力的页 + flash + slam；
     逐词子句（谁笑着/似哭了…）一词一切；骤停处用全静止的标题页；最后 drop 放情绪反转画面。
   - 歌词意义 ↔ 剧情要对得上，可以非线性剪辑；同一画格重复使用时换裁切/运镜。
   - 竖版整页用 `pan_up/pan_down` 或关键帧纵向移动，或 `card`（3D 浮空卡片，`ry/rx` 随时间转）。
   - 人物为主体的镜头 `char=True`：生成抠图槽位（占位框），抠图完成后自动变成可视差的分层。
5. **初版抠图**：`mad-character/auto_cutout.py <project> <槽位...>` → `cutouts_auto/`（也生成占位框位置）。
6. **渲染**：`python3 build_storyboard.py`；`python3 -m madrender.render project.yaml --contact` 看全部镜头缩略图 →
   修 → 全片渲染（1080p/24fps 约 5 秒渲 1 秒，4 核）→ 再出一个 720p 分享版（ffmpeg crf 25 + hqdn3d，约 80MB）。
7. **检查**：`mad-review/smoothness.py out.mp4 --beats beats.json --project project.yaml` 报告无理由的速度突变；
   每段抽帧看构图（脸有没有被裁掉、字幕是否压在主体上）。
8. **交付**：发 720p 成片 + `storyboard.md` + `cutout_tasks.md`。

## 用户改稿 → 怎么改

| 用户说 | 改什么（build_storyboard.py） |
|---|---|
| 第N个镜头/某句歌词换图 | 对应 `shot(...)` 的画格 id（看 storyboard.md 找 sNNN） |
| 推近/拉远/往下摇/仰拍 | `cam="push_in"/"pull_out"/"pan_down"`，或关键帧 `{"keys":[{at,zoom,center},…]}` |
| 卡点更狠 | `fx=["hit"]`/`["hit","big"]`，转场 `tr="flash"` |
| 不要闪白 / 换溶解 | `tr="fade"` |
| 抖动太多 / 不顺 | 去掉 `shake`，或 `decay` 变短、`freq` 变低；能量等级降一档 |
| 整体更暗/更压抑/换色调 | 改 `SECTIONS` 的 duotone 三色 |
| 字幕大小/位置/样式 | `build()` 里 texts 的 size/pos/anim |
| 人物动起来 | 抠图放进 `cutouts/` 后，在 char 里加 `puppet`（见 mad-render 参考） |

改完：`python3 build_storyboard.py` → 只渲改动区间 `--from 1:10 --to 1:25 --preview` 给用户确认 → 全片重渲。

## 已知限制（如实告诉用户）

- 云端多为 CPU：SD/SDXL 补全身一张 15+ 分钟且画风难统一。补全身、重绘交给用户（PS 生成式填充 / ComfyUI）或带 GPU 的 API。
- 对白气泡 v1 保留；去气泡用 mad-assets/layer_panel.py（LaMa），大块压在头发上的气泡补不好，宁可裁掉或交给用户。
- 上色：静止系是「一块一个颜色」的平涂 + 后期 3D 光影；整段配色用 duotone，人物平涂用 mad-character/segment.py。
