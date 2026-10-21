---
name: mad-style
description: Step 0 of any MAD — decide the style profile (压抑/燃/治愈/悬疑/伤感) from the song's audio, lyrics and the story BEFORE any storyboard, then hand hard limits (palette, camera speed, cutting rate, flash budget, allowed MG/typography, fonts) to the storyboard. Use whenever starting or re-designing a MAD, or when the user says the result "doesn't match the song's feeling".
---

# 风格判定（先决条件，必须先做）

```
python3 scripts/style_profile.py song.mp3 --lyrics lyrics.txt --story "<读完原作后的剧情标签>" -o style.json [--force oppressive]
```

- 打分来源：音频（大/小调、速度、音色亮度、动态范围、打击感）+ 歌词关键词（暗/亮/燃/柔）+ **剧情标签**（最有决定性）。
  快歌 ≠ 燃：《唯死以解脱》161 BPM 但小调、歌词全暗、剧情是霸凌与自杀 → `oppressive`。
- 输出 `style.json` 的 `limits` 是**硬约束**，分镜脚本必须读取并遵守（`profiles.yaml` 可增改）：
  - palette（低饱和、压暗部）、camera.max_speed / forbid（压抑禁甩镜、快速旋转、slam zoom）
  - cutting.min_shot_beats（压抑：每镜至少 4 拍，静音处停留）
  - transitions.flash_max_total（压抑全片 ≤3 次闪白，用在剧情转折点）
  - effects 上限（shake/zoom_punch/rgb/glow/粒子）、mg.allow/forbid（压抑只允许细线、角框、网格、日文小字标签、计数器）
  - typography：**只用日文**，明朝体（Shippori Mincho / Zen Old Mincho，放 `assets/fonts/`），淡色、小字号、模糊淡入淡出；
    不加中文歌词字幕；画面上的台词只用原作日文原句（如 ありがとう タコピー），不要编造"信息感"文案（假的REC/时间戳等）。
- 用户一句话否定风格（"不压抑""太花"）→ 回到这一步改 profile / limits，再重建分镜，而不是逐个镜头修。
