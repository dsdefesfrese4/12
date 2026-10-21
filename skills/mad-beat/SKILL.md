---
name: mad-beat
description: Analyse a song for MAD editing — tempo, beats, bars (downbeats), strong hits, energy sections, and lyric timing via Whisper. Use before storyboarding any music video / MAD, or when cuts need to land on the beat or on lyric lines.
---

# 音乐分析

```
python3 scripts/analyze_beats.py song.mp3 -o beats.json [--bpm 160] [--start 60 --dur 30]
python3 scripts/transcribe.py song.mp3 -o asr.json --prompt-file lyrics.txt [--model medium]
```

- `beats.json`：`tempo, duration, beats[], downbeats[], hits[], drops[], sections[{label,start,end,energy,level}]`。
  时间都是原曲秒数。渲染器里可写 `b16`（第16拍）、`d4`（第4小节）、`h3`、段落名 `chorus1`，以及 `b16+2b` / `d4-0.1`。
- 速度识别成一半/两倍时用 `--bpm` 提示。分段是自动聚类，只作参考；做分镜前再按小节打印 RMS / 低频 / 人声强度表
  （见 mad-director 流程第 3 步）找真正的爆点和骤停。
- `transcribe.py`：faster-whisper，CPU int8，medium 模型约 3 分钟一首。唱歌识别会有同音错字，但**时间戳可靠**；
  用官方歌词逐句对齐到 ASR 句子/词的开始时间，写 `lyrics_timed.json`：
  `[{"i":0,"text":"…","start":25.02,"end":28.0,"parts":[47.32,49.12]}]`（parts = 句内逐词卡点时间）。
- 依赖：`pip install librosa faster-whisper`。faster-whisper 读不了某些 mp3 时脚本已改为 librosa 先解码。
