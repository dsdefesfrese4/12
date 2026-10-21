"""Step 0 of every MAD: decide the style BEFORE designing anything.

  python3 style_profile.py song.mp3 --lyrics lyrics.txt --story "霸凌 自杀 杀人 绝望" [--beats beats.json] -o style.json

Scores each profile in profiles.yaml from:
  audio  : tempo, major/minor mode (Krumhansl key profiles on chroma), brightness (spectral centroid),
           loudness and dynamic range, percussiveness
  lyrics : dark/bright/aggressive/tender keyword hits
  story  : free-text tags given by Claude after reading the source (most decisive for MADs)
Writes style.json {profile, scores, features, reasons, limits}. The storyboard builder must load `limits`.
A user override always wins: --force oppressive
"""
import argparse, json, os, sys
import numpy as np
import yaml

DARK = "死 绝望 黑暗 血 麻木 孤独 折磨 深渊 撕扯 漩涡 坠落 腐化 丑恶 淬毒 哑巴 木偶 魔 躯壳 冷漠 吞噬 苟活 牢 杀 痛 哭 解脱 自杀 霸凌 葬".split()
BRIGHT = "光 希望 笑 太阳 飞 梦 明天 幸福 温暖 爱 春 花 自由 晴".split()
AGGR = "燃 战 冲 咆哮 毁灭 发泄 怒 吼 拳 剑 斗 拼".split()
TENDER = "思念 回忆 温柔 雨 泪 等待 离别 再见 星".split()


def key_mode(chroma):
    maj = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    mnr = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    c = chroma.mean(axis=1)
    best = (-9, None, None)
    for k in range(12):
        for name, prof in (("major", maj), ("minor", mnr)):
            r = np.corrcoef(c, np.roll(prof, k))[0, 1]
            if r > best[0]:
                best = (r, name, k)
    return best[1], best[2], float(best[0])


def audio_features(path):
    import librosa
    y, sr = librosa.load(path, sr=22050, mono=True)
    tempo = float(np.atleast_1d(librosa.beat.beat_track(y=y, sr=sr)[0])[0])
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    mode, key, conf = key_mode(chroma)
    cent = float(np.median(librosa.feature.spectral_centroid(y=y, sr=sr)))
    rms = librosa.feature.rms(y=y)[0]
    db = 20 * np.log10(rms + 1e-6)
    yh, yp = librosa.effects.hpss(y)
    perc = float(np.mean(np.abs(yp)) / (np.mean(np.abs(y)) + 1e-9))
    return {"tempo": round(tempo, 1), "mode": mode, "key": int(key), "mode_conf": round(conf, 3),
            "brightness_hz": round(cent), "loudness_db": round(float(np.median(db)), 1),
            "dynamic_range_db": round(float(np.percentile(db, 95) - np.percentile(db, 10)), 1), "percussive": round(perc, 3)}


def lyric_scores(text):
    def hits(words):
        return sum(text.count(w) for w in words)
    return {"dark": hits(DARK), "bright": hits(BRIGHT), "aggressive": hits(AGGR), "tender": hits(TENDER)}


def score(feat, lyr, story):
    s = {k: 0.0 for k in ("oppressive", "hype", "healing", "suspense", "melancholic")}
    why = []
    if feat:
        if feat["mode"] == "minor":
            for k in ("oppressive", "suspense", "melancholic"):
                s[k] += 1.0
            why.append(f"小调({feat['mode_conf']}) → 偏暗")
        else:
            s["hype"] += 0.6; s["healing"] += 0.8
        if feat["tempo"] >= 140:
            s["hype"] += 0.8; s["oppressive"] += 0.3
            why.append(f"速度 {feat['tempo']} 快 → 节奏密，但情绪由歌词/剧情决定")
        elif feat["tempo"] < 95:
            s["healing"] += 0.6; s["melancholic"] += 0.6
        if feat["brightness_hz"] < 2200:
            s["oppressive"] += 0.5; s["melancholic"] += 0.4
            why.append("音色偏暗")
        else:
            s["hype"] += 0.4
        if feat["dynamic_range_db"] > 25:
            s["suspense"] += 0.3
    tot = max(1, sum(lyr.values()))
    s["oppressive"] += 3.0 * lyr["dark"] / tot
    s["hype"] += 2.0 * lyr["aggressive"] / tot
    s["healing"] += 2.0 * lyr["bright"] / tot
    s["melancholic"] += 2.0 * lyr["tender"] / tot
    why.append(f"歌词关键词 暗{lyr['dark']} 亮{lyr['bright']} 燃{lyr['aggressive']} 柔{lyr['tender']}")
    st = lyric_scores(story or "")
    s["oppressive"] += 2.5 * min(1, st["dark"] / 2)
    s["healing"] += 2.0 * min(1, st["bright"] / 2)
    s["hype"] += 2.0 * min(1, st["aggressive"] / 2)
    if story:
        why.append(f"剧情标签：{story}")
    return s, why


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--lyrics")
    ap.add_argument("--story", default="")
    ap.add_argument("--force")
    ap.add_argument("-o", "--out", default="style.json")
    a = ap.parse_args()
    prof = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "profiles.yaml"), encoding="utf-8"))
    feat = audio_features(a.audio)
    lyr = lyric_scores(open(a.lyrics, encoding="utf-8").read() if a.lyrics else "")
    s, why = score(feat, lyr, a.story)
    choice = a.force or max(s, key=s.get)
    out = {"profile": choice, "label": prof[choice]["label"], "scores": {k: round(v, 2) for k, v in s.items()},
           "features": feat, "lyrics": lyr, "reasons": why, "limits": prof[choice]}
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"STYLE: {choice} ({prof[choice]['label']})")
    for k, v in sorted(s.items(), key=lambda x: -x[1]):
        print(f"  {k:<12} {v:.2f}")
    for r in why:
        print("  -", r)
    print(f"-> {a.out}")


if __name__ == "__main__":
    sys.exit(main())
