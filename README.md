# 静止系 MAD 制作 Skill

一套 Claude Code skill：从漫画页 + 歌曲，代码渲染出高质量静止系 MAD（运镜、3D 卡片、人物视差槽位、节拍同步特效、歌词字幕），并能按中文改稿意见反复修改。

## 安装
把 `skills/` 下的 7 个目录复制到 `~/.claude/skills/`（或项目的 `.claude/skills/`）。
依赖：`python3 -m pip install numpy opencv-python-headless pillow pyyaml librosa faster-whisper rembg[cpu] psd-tools`，以及 ffmpeg。
可选（人物分部件/补图）：`torch transformers diffusers accelerate`。

| Skill | 作用 |
|---|---|
| mad-style | **先决条件**：按音频/歌词/剧情判定风格（压抑/燃/治愈/悬疑/伤感），输出硬性限制 |
| mad-director | 总控：读剧情 → 分镜 → 渲染 → 改稿流程 |
| mad-beat | 节拍/小节/段落分析，Whisper 歌词时间轴 |
| mad-assets | 切格、对白气泡检测与去除、风格化 |
| mad-character | 自动抠图与占位、SAM 分部件平涂、补全身 |
| mad-render | 渲染器：2D 运镜 + 3D 场景（透视摄像机/景深/雾/光/粒子）+ 自设计元素 + MG + 日文动态字 + 语音混入 |
| mad-review | 逐帧流畅度检查（卡顿/跳帧/方向急转） |

## 示例作品：章鱼噼的原罪 × 唯死以解脱
`projects/takopi_mad/`：分镜表 `storyboard.md`、工程 `build_storyboard.py`、抠图任务 `cutout_tasks.md`、成片 `out/takopi_mad_v1.1_720p.mp4`。
漫画原图与歌曲音频未上传（版权），重渲时放回 `pages/`、`song.mp3`，再按 `story_notes.md` 用 mad-assets 切格。

### v2（3D 场景版，压抑风格）
`build_v2.py` / `project_v2.yaml` / `storyboard_v2.md` / `style.json`。三段式：真理奈之死 → 真理奈第一次轮回 → 静香自杀。字体（Shippori Mincho / Zen Old Mincho，OFL）需放到 `assets/fonts/`。
