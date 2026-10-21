# 静止系 MAD 制作 Skill

一套 Claude Code skill：从漫画页 + 歌曲，代码渲染出高质量静止系 MAD（运镜、3D 卡片、人物视差槽位、节拍同步特效、歌词字幕），并能按中文改稿意见反复修改。

## 安装
把 `skills/` 下的 6 个目录复制到 `~/.claude/skills/`（或项目的 `.claude/skills/`）。
依赖：`python3 -m pip install numpy opencv-python-headless pillow pyyaml librosa faster-whisper rembg[cpu] psd-tools`，以及 ffmpeg。
可选（人物分部件/补图）：`torch transformers diffusers accelerate`。

| Skill | 作用 |
|---|---|
| mad-director | 总控：读剧情 → 分镜 → 渲染 → 改稿流程 |
| mad-beat | 节拍/小节/段落分析，Whisper 歌词时间轴 |
| mad-assets | 切格、对白气泡检测与去除、风格化 |
| mad-character | 自动抠图与占位、SAM 分部件平涂、补全身 |
| mad-render | 渲染器（project.yaml → mp4） |
| mad-review | 逐帧流畅度检查（卡顿/跳帧/方向急转） |

## 示例作品：章鱼噼的原罪 × 唯死以解脱
`projects/takopi_mad/`：分镜表 `storyboard.md`、工程 `build_storyboard.py`、抠图任务 `cutout_tasks.md`、成片 `out/takopi_mad_v1.1_720p.mp4`。
漫画原图与歌曲音频未上传（版权），重渲时放回 `pages/`、`song.mp3`，再按 `story_notes.md` 用 mad-assets 切格。
