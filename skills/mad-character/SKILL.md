---
name: mad-character
description: Character work for static MADs — auto first-pass cutouts and placeholder boxes for every character slot, SAM point-prompt part segmentation with flat per-region colouring, and (GPU-dependent) SD/SDXL figure completion. Use when a MAD shot needs a character separated from the background, coloured, or completed.
---

# 人物：抠图 / 分部件 / 平涂 / 补图

正确顺序（用户定的）：**补全身 → 拆部件 → 补各部件被遮挡处 → 上色**。上色是「一个区块一个颜色」的平涂，立体感交给后期光影。

```
python3 scripts/auto_cutout.py <project> <槽位...>        # rembg isnet-anime 初版 + boxes.json（占位框）
python3 scripts/segment.py parts.yaml                     # SAM 点提示分部件 + 平涂
python3 scripts/complete_figure.py page.jpg out --bubbles mask.png --keep-mask char.png --prompt "..."   # SD1.5 补全身
python3 scripts/sdxl_tools.py init.png mask.png out.png --prompt "..."   # SDXL(Animagine XL 4.0) 重绘
```

- **槽位约定**：分镜里 `char=True` 的镜头槽位名 = 画格 id。精修抠图放 `cutouts/<槽位>.png`（与原图同尺寸 RGBA），
  可选 `cutouts/<槽位>_bg.png`（去人物并补好的背景）。渲染器发现文件就自动：背景换 _bg、人物作为视差层（parallax 1.12），
  可加 `puppet`。没有文件时显示青色虚线占位框 + 槽位名。
- **segment.py**（parts.yaml）：每个区块给几个正点 `points`、负点 `neg`，可用 `box`、`poly`（手补多边形）、`within`（只在某区块内）、
  `light_only/dark_only`（眼白/牙齿/刘海）、`clip_poly`、`close`、`line_color`（皮肤上的线条用红棕）。后写的区块覆盖前面的。
  每轮看 `preview.jpg`，加负点/多边形修正，重跑（SAM 嵌入有缓存，很快）。也可手画 `mask_<名>_fix.png` / `_cut.png`。
- **补全身**：CPU 上 SD1.5 质量不够，SDXL 一张约 17 分钟（需关掉文本编码器分步加载，fp32；bf16 在无 AMX 的 CPU 上慢 4 倍），
  画风/接缝仍难统一。如实告诉用户，建议 PS 生成式填充 / 本地 ComfyUI / GPU API 完成这一步，再交回来做后面的工序。
- 模型：rembg `isnet-anime`（github 下载）、SAM `facebook/sam-vit-base`、`gsdf/Counterfeit-V2.5` + ControlNet lineart_anime/inpaint、
  `cagliostrolab/animagine-xl-4.0`（需要 huggingface.co 及 `*.hf.co` CDN 网络白名单）。
