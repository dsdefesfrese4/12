"""Load project.yaml, resolve time expressions, build the shot timeline."""
import json
import os
import re

import yaml

DEFAULT_META = {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "audio": None,
    "beats": None,
    "start": 0,
    "end": None,
    "background": "#000000",
    "font": None,
    "crf": 18,
}


class TimeResolver:
    """Turns time expressions into seconds (song time).

    Accepted forms:
      12.5        seconds
      "1:23.5"    mm:ss
      "b16"       beat #16 (0-based), "b16.5" = halfway to beat 17
      "d4"        downbeat (bar) #4
      "h3"        strong hit #3
      "chorus1"   a marker name or section label
      any of the above + "+0.1" / "-0.25" (seconds) or "+2b" / "-1b" (beats)
    """

    def __init__(self, beats=None, markers=None):
        beats = beats or {}
        self.beats = beats.get("beats", [])
        self.downbeats = beats.get("downbeats", [])
        self.hits = beats.get("hits", [])
        self.tempo = beats.get("tempo") or 120.0
        self.named = {}
        for sec in beats.get("sections", []):
            self.named[sec["label"]] = sec["start"]
            self.named[sec["label"] + ".end"] = sec["end"]
        self.named.update(beats.get("markers", {}) or {})
        self._markers_raw = markers or {}
        for k in self._markers_raw:
            self.named[k] = None  # resolved lazily

    @property
    def beat_len(self):
        if len(self.beats) > 1:
            return (self.beats[-1] - self.beats[0]) / (len(self.beats) - 1)
        return 60.0 / self.tempo

    def beat_pos(self, t):
        """Fractional beat index of time t (inverse of b<n>)."""
        b = self.beats
        if len(b) < 2:
            return t / self.beat_len
        import bisect
        i = bisect.bisect_right(b, t) - 1
        if i < 0:
            return (t - b[0]) / self.beat_len
        if i >= len(b) - 1:
            return len(b) - 1 + (t - b[-1]) / self.beat_len
        return i + (t - b[i]) / (b[i + 1] - b[i])

    def add_beats(self, t, n):
        if len(self.beats) < 2:
            return t + n * self.beat_len
        return self._index(self.beats, max(0.0, self.beat_pos(t) + n), "b")

    def _index(self, arr, x, name):
        if not arr:
            raise ValueError(f"time '{name}' needs beats.json ({name[0]} list is empty)")
        i = int(x)
        frac = x - i
        if i >= len(arr):
            # extrapolate past the end
            step = self.beat_len if arr is self.beats else self.beat_len * 4
            return arr[-1] + (x - (len(arr) - 1)) * step
        t = arr[i]
        if frac:
            nxt = arr[i + 1] if i + 1 < len(arr) else t + self.beat_len
            t += (nxt - t) * frac
        return t

    def __call__(self, expr):
        if expr is None:
            return None
        if isinstance(expr, (int, float)):
            return float(expr)
        s = str(expr).strip()
        m = re.match(r"^(.*?)([+-]\d+(?:\.\d+)?b?)$", s)
        offset = 0.0
        if m and m.group(1) and not re.match(r"^\d+(\.\d+)?$", s):
            base, off = m.group(1), m.group(2)
            if off.endswith("b"):
                offset = float(off[:-1]) * self.beat_len
            else:
                offset = float(off)
            s = base
        return self._base(s) + offset

    def _base(self, s):
        if re.match(r"^-?\d+(\.\d+)?$", s):
            return float(s)
        m = re.match(r"^(\d+):(\d+(?:\.\d+)?)$", s)
        if m:
            return int(m.group(1)) * 60 + float(m.group(2))
        m = re.match(r"^([bdh])(\d+(?:\.\d+)?)$", s)
        if m:
            arr = {"b": self.beats, "d": self.downbeats, "h": self.hits}[m.group(1)]
            return self._index(arr, float(m.group(2)), s)
        if s in self.named:
            v = self.named[s]
            if v is None:
                v = self(self._markers_raw[s])
                self.named[s] = v
            return float(v)
        raise ValueError(f"unknown time expression: {s!r}")


class Project:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.root = os.path.dirname(self.path)
        with open(self.path, encoding="utf-8") as f:
            self.data = _fix_on_keys(yaml.safe_load(f) or {})
        self.meta = dict(DEFAULT_META)
        self.meta.update(self.data.get("meta", {}) or {})
        self.beats = {}
        if self.meta.get("beats"):
            with open(self.abspath(self.meta["beats"]), encoding="utf-8") as f:
                self.beats = json.load(f)
        self.T = TimeResolver(self.beats, self.data.get("markers"))
        self.W = int(self.meta["width"])
        self.H = int(self.meta["height"])
        self.fps = float(self.meta["fps"])
        self.t0 = self.T(self.meta.get("start") or 0)
        end = self.meta.get("end")
        if end is None:
            end = self.beats.get("duration")
        if end is None:
            raise ValueError("meta.end is required when there is no beats.json duration")
        self.t1 = self.T(end)
        self.style = self.data.get("style", {}) or {}
        self._build_shots()
        self.texts = []
        for i, tx in enumerate(self.data.get("texts", []) or []):
            tx = dict(tx)
            tx["_start"] = self.T(tx["start"])
            tx["_end"] = self.T(tx["end"]) if tx.get("end") is not None else self.t1
            tx.setdefault("id", f"t{i + 1}")
            self.texts.append(tx)

    def abspath(self, p):
        if p is None:
            return None
        return p if os.path.isabs(p) else os.path.join(self.root, p)

    def _build_shots(self):
        raw = self.data.get("shots", []) or []
        shots = []
        for i, s in enumerate(raw):
            s = dict(s)
            s.setdefault("id", f"s{i + 1}")
            s["_index"] = i
            s["_start"] = self.T(s["start"]) if "start" in s else None
            shots.append(s)
        # shots without start follow the previous one using `beats:` or `dur:`
        for i, s in enumerate(shots):
            if s["_start"] is None:
                if i == 0:
                    s["_start"] = self.t0
                else:
                    p = shots[i - 1]
                    s["_start"] = p["_start"] + _shot_len(p, self.T)
        for i, s in enumerate(shots):
            if "end" in s:
                s["_end"] = self.T(s["end"])
            elif "beats" in s or "dur" in s:
                s["_end"] = s["_start"] + _shot_len(s, self.T)
            elif i + 1 < len(shots):
                s["_end"] = shots[i + 1]["_start"]
            else:
                s["_end"] = self.t1
        shots.sort(key=lambda s: s["_start"])
        self.shots = shots

    @property
    def nframes(self):
        return max(1, int(round((self.t1 - self.t0) * self.fps)))

    def frame_time(self, n):
        return self.t0 + n / self.fps

    def shot_at(self, t):
        cur = None
        for s in self.shots:
            if s["_start"] <= t + 1e-9:
                cur = s
            else:
                break
        return cur

    def triggers(self, spec, start, end):
        """Return trigger times for an effect `on:` spec inside [start-pad, end]."""
        on = spec.get("on")
        if on is None:
            return None  # continuous
        pad = 0.5
        if isinstance(on, list):
            ts = [self.T(x) for x in on]
        elif on in ("beat", "beats"):
            ts = list(self.beats.get("beats", []))
        elif on in ("downbeat", "downbeats", "bar", "bars"):
            ts = list(self.beats.get("downbeats", []))
        elif on in ("hit", "hits"):
            ts = list(self.beats.get("hits", []))
        elif on == "start":
            ts = [start]
        elif on == "offbeat":
            b = self.beats.get("beats", [])
            ts = [(b[i] + b[i + 1]) / 2 for i in range(len(b) - 1)]
        else:
            ts = [self.T(on)]
        every = int(spec.get("every", 1))
        offset = int(spec.get("phase", 0))
        if every > 1:
            ts = ts[offset::every]
        shift = float(spec.get("shift", 0))
        ts = [x + shift for x in ts]
        return [x for x in ts if start - pad <= x <= end]


def _fix_on_keys(x):
    """YAML 1.1 reads a bare `on:` key as boolean True; turn it back into "on"."""
    if isinstance(x, dict):
        return {("on" if k is True else k): _fix_on_keys(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_fix_on_keys(v) for v in x]
    return x


def _shot_len(s, T):
    if "dur" in s:
        return float(s["dur"])
    if "beats" in s:
        return T.add_beats(s["_start"], float(s["beats"])) - s["_start"]
    raise ValueError(f"shot {s.get('id')} needs start / beats / dur")
