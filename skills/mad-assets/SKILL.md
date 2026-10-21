---
name: mad-assets
description: Prepare manga pages for a MAD — split pages into panels, detect and remove speech bubbles, stylise/tint panels, build matching backdrops. Use when turning comic pages into usable shots.
---

# 素材处理

```
python3 scripts/split_panels.py pages/*.jpg -o panels [--ltr] [--min-area 0.03]
python3 scripts/layer_panel.py panel.png -o layers [--keep-bubbles] [--no-fg]
python3 scripts/stylize.py clean.png -o out.png --palette green_glow --key --feather 0.15 [--backdrop bg.png]
```

- **split_panels**：白色格线 XY 递归切割，日漫右→左阅读序（`--ltr` 改左→右）。输出 `<页>_pNN.png`、`panels.json`、
  `<页>_debug.jpg`（红框编号，切完先看它）。
- **layer_panel**：对白气泡检测（白色、凸、内部有很多小笔画；白色人物/章鱼噼会被过滤）→ `mask_bubbles.png`；
  LaMa 漫画模型补图（`~/.u2net/anime-manga-big-lama.pt`，需要 torch）→ `clean.png`；可选 rembg 抠人物 → `fg.png`/`bg.png`。
  ⚠ 气泡压在大块黑发/深色背景上时补出来会是一团黑，用户明确不接受——这种情况保留气泡、改裁切，或交给用户手工补。
  用户要的是「把气泡抠掉（透明）」而不是「涂掉」：需要透明时直接用 `mask_bubbles.png` 做 alpha。
- **stylize**：渐变映射上色（单色调氛围用；人物平涂请用 mad-character/segment.py）、纸白抠除、边缘羽化、配套背景。
- 解压 RAR5 用 7-Zip 24+（`7zz`），Ubuntu 的 unar/p7zip 会误报损坏。
