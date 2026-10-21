"""Transcribe sung vocals with word timestamps (faster-whisper, CPU int8).

  python3 transcribe.py song.mp3 -o asr.json [--model medium --lang zh --prompt-file lyrics.txt]
"""
import argparse, json, sys, time
from faster_whisper import WhisperModel

ap = argparse.ArgumentParser()
ap.add_argument("audio"); ap.add_argument("-o", "--out", default="asr.json")
ap.add_argument("--model", default="medium"); ap.add_argument("--lang", default="zh")
ap.add_argument("--prompt-file")
a = ap.parse_args()
t = time.time()
m = WhisperModel(a.model, device="cpu", compute_type="int8", cpu_threads=4)
prompt = open(a.prompt_file, encoding="utf-8").read().replace("\n", "，")[:200] if a.prompt_file else None
import librosa
audio, _ = librosa.load(a.audio, sr=16000, mono=True)
segs, info = m.transcribe(audio, language=a.lang, word_timestamps=True, vad_filter=False,
                          initial_prompt=prompt, condition_on_previous_text=False, beam_size=5)
out = []
for s in segs:
    out.append({"start": s.start, "end": s.end, "text": s.text,
                "words": [{"w": w.word, "s": w.start, "e": w.end, "p": w.probability} for w in s.words]})
    print(f"{s.start:7.2f}-{s.end:7.2f} {s.text}", flush=True)
json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"done in {time.time()-t:.0f}s")
