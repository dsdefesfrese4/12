"""Analyse a song for MAD editing: tempo, beats, bars, strong hits, sections.

  python3 analyze_beats.py song.mp3 -o beats.json [--start 60 --dur 30] [--bpm 174]

Output JSON (all times in seconds of the ORIGINAL song):
  tempo, duration, beats[], downbeats[], hits[], sections[{label,start,end,energy,level}],
  energy_curve (per beat, 0..1)
"""
import argparse
import json
import sys

import numpy as np


def analyze(path, start=0.0, dur=None, bpm=None, n_sections=None, sr=22050):
    import librosa

    y, sr = librosa.load(path, sr=sr, mono=True, offset=start, duration=dur)
    duration = len(y) / sr
    hop = 512
    y_h, y_p = librosa.effects.hpss(y)
    onset_env = librosa.onset.onset_strength(y=y_p, sr=sr, hop_length=hop)
    kw = {}
    if bpm:
        kw["start_bpm"] = bpm
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, hop_length=hop,
                                                 tightness=200 if bpm else 100, **kw)
    tempo = float(np.atleast_1d(tempo)[0])
    beats = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop)

    # downbeats: choose the bar phase whose beats carry the most low-frequency punch
    S = np.abs(librosa.stft(y, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr)
    low = S[freqs < 150].sum(axis=0)
    low = low / (low.max() + 1e-9)
    bf = np.clip(beat_frames, 0, len(low) - 1)
    best, phase = -1, 0
    for ph in range(4):
        v = (low[bf[ph::4]].mean() if len(bf[ph::4]) else 0) + \
            0.5 * (onset_env[np.clip(bf[ph::4], 0, len(onset_env) - 1)].mean() / (onset_env.max() + 1e-9))
        if v > best:
            best, phase = v, ph
    downbeats = beats[phase::4]

    # hits: strongest onsets, at least 0.25s apart
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=hop, units="frames")
    strengths = onset_env[onsets]
    thr = np.percentile(strengths, 88) if len(strengths) else 0
    hits = []
    for f_, st in sorted(zip(onsets, strengths), key=lambda x: -x[1]):
        if st < thr:
            break
        t = librosa.frames_to_time(f_, sr=sr, hop_length=hop)
        if all(abs(t - h) > 0.25 for h in hits):
            hits.append(float(t))
    hits.sort()

    # energy per beat
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    seg_e = []
    edges = list(bf) + [len(rms) - 1]
    for a, b in zip(edges, edges[1:]):
        seg_e.append(float(rms[a:max(a + 1, b)].mean()))
    e = np.array(seg_e) if seg_e else np.zeros(1)
    e_norm = (e - e.min()) / (e.max() - e.min() + 1e-9)

    # sections: agglomerative segmentation on beat-synced features
    if n_sections is None:
        n_sections = int(np.clip(round(duration / 18), 2, 12))
    sections = []
    if len(beat_frames) > n_sections * 2:
        chroma = librosa.feature.chroma_cqt(y=y_h, sr=sr, hop_length=hop)
        mfcc = librosa.feature.mfcc(y=y, sr=sr, hop_length=hop, n_mfcc=13)
        feat = np.vstack([librosa.util.normalize(chroma, axis=1), librosa.util.normalize(mfcc, axis=1),
                          librosa.util.normalize(rms[None], axis=1) * 3])
        sync = librosa.util.sync(feat, beat_frames, aggregate=np.median)
        bounds = librosa.segment.agglomerative(sync, n_sections)
        bounds = sorted(set([0] + list(bounds)))
        # snap boundaries to downbeats (bar lines)
        btimes = [0.0] + [float(beats[min(b, len(beats) - 1)]) for b in bounds[1:]] + [duration]
        snapped = [0.0]
        for t in btimes[1:-1]:
            if len(downbeats):
                t = float(downbeats[np.argmin(np.abs(downbeats - t))])
            if t - snapped[-1] > 3:
                snapped.append(t)
        snapped.append(duration)
        for a, b in zip(snapped, snapped[1:]):
            mask = (beats >= a) & (beats < b)
            en = float(e_norm[mask[:len(e_norm)]].mean()) if mask[:len(e_norm)].any() else 0.0
            sections.append({"start": round(a, 3), "end": round(b, 3), "energy": round(en, 3)})
    else:
        sections.append({"start": 0.0, "end": duration, "energy": float(e_norm.mean())})
    ens = sorted(s["energy"] for s in sections)
    hi = ens[int(len(ens) * 0.66)] if len(ens) > 2 else 0.6
    lo = ens[int(len(ens) * 0.33)] if len(ens) > 2 else 0.3
    counters = {}
    for i, s in enumerate(sections):
        s["level"] = "high" if s["energy"] >= hi else ("low" if s["energy"] <= lo else "mid")
        name = {"high": "chorus", "mid": "verse", "low": "calm"}[s["level"]]
        if i == 0 and s["level"] != "high":
            name = "intro"
        elif i == len(sections) - 1 and s["level"] != "high" and len(sections) > 2:
            name = "outro"
        counters[name] = counters.get(name, 0) + 1
        s["label"] = f"{name}{counters[name]}"

    # drops: biggest energy jump between consecutive bars
    drops = []
    if len(e_norm) > 8:
        bar_e = [e_norm[i:i + 4].mean() for i in range(phase, len(e_norm) - 4, 4)]
        jumps = [(bar_e[i + 1] - bar_e[i], i + 1) for i in range(len(bar_e) - 1)]
        for j, i in sorted(jumps, reverse=True)[:3]:
            if j > 0.25:
                idx = phase + i * 4
                if idx < len(beats):
                    drops.append(float(beats[idx]))
    sh = float(start)
    out = {
        "source": path,
        "analysis_offset": sh,
        "tempo": round(tempo, 2),
        "duration": round(duration + sh, 3),
        "beats": [round(float(b) + sh, 4) for b in beats],
        "downbeats": [round(float(b) + sh, 4) for b in downbeats],
        "hits": [round(h + sh, 4) for h in hits],
        "drops": sorted(round(d + sh, 4) for d in drops),
        "sections": [dict(s, start=round(s["start"] + sh, 3), end=round(s["end"] + sh, 3)) for s in sections],
        "energy_curve": [round(float(x), 3) for x in e_norm],
    }
    return out


def summary(d):
    lines = [f"tempo {d['tempo']} BPM, {len(d['beats'])} beats, {len(d['downbeats'])} bars, "
             f"{len(d['hits'])} hits, duration {d['duration']:.1f}s"]
    for s in d["sections"]:
        lines.append(f"  {s['label']:<10} {s['start']:7.2f} - {s['end']:7.2f}s  energy {s['energy']:.2f} ({s['level']})")
    if d["drops"]:
        lines.append("  drops: " + ", ".join(f"{x:.2f}s" for x in d["drops"]))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("-o", "--out", default="beats.json")
    ap.add_argument("--start", type=float, default=0.0, help="analyse from this second")
    ap.add_argument("--dur", type=float, help="analyse only this many seconds")
    ap.add_argument("--bpm", type=float, help="hint the tempo if detection is off (e.g. half/double)")
    ap.add_argument("--sections", type=int, help="number of sections")
    a = ap.parse_args()
    d = analyze(a.audio, a.start, a.dur, a.bpm, a.sections)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print(summary(d))
    print(f"-> {a.out}")


if __name__ == "__main__":
    sys.exit(main())
