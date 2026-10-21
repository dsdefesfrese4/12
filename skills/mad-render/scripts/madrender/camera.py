"""Camera moves on a still image: zoom / pan / rotate with easing."""
import math

EASINGS = {
    "linear": lambda x: x,
    "ease_in": lambda x: x * x * x,
    "ease_out": lambda x: 1 - (1 - x) ** 3,
    "ease_in_out": lambda x: 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2,
    "expo_out": lambda x: 1.0 if x >= 1 else 1 - 2 ** (-10 * x),
    "expo_in": lambda x: 0.0 if x <= 0 else 2 ** (10 * x - 10),
    "back_out": lambda x: 1 + 2.70158 * (x - 1) ** 3 + 1.70158 * (x - 1) ** 2,
    "sine": lambda x: -(math.cos(math.pi * x) - 1) / 2,
    # fast snap at start, long slow drift: the classic "kachi" feel of still MADs
    "snap": lambda x: 1 - (1 - x) ** 6,
}


def ease(name, x):
    x = min(1.0, max(0.0, x))
    return EASINGS.get(name or "ease_in_out", EASINGS["ease_in_out"])(x)


# Presets: zoom [from,to], center [[x,y] from, [x,y] to] (normalised image coords), rotate [from,to] deg
PRESETS = {
    "static": dict(zoom=[1.0, 1.0], center=[[0.5, 0.5], [0.5, 0.5]]),
    "push_in": dict(zoom=[1.0, 1.25]),
    "push_in_fast": dict(zoom=[1.0, 1.5], ease="expo_out"),
    "pull_out": dict(zoom=[1.3, 1.0]),
    "pull_out_fast": dict(zoom=[1.6, 1.0], ease="expo_out"),
    "pan_left": dict(zoom=[1.25, 1.25], center=[[0.62, 0.5], [0.38, 0.5]]),
    "pan_right": dict(zoom=[1.25, 1.25], center=[[0.38, 0.5], [0.62, 0.5]]),
    "pan_up": dict(zoom=[1.25, 1.25], center=[[0.5, 0.62], [0.5, 0.38]]),
    "pan_down": dict(zoom=[1.25, 1.25], center=[[0.5, 0.38], [0.5, 0.62]]),
    "tilt_left": dict(zoom=[1.2, 1.3], rotate=[0, -4]),
    "tilt_right": dict(zoom=[1.2, 1.3], rotate=[0, 4]),
    "roll_in": dict(zoom=[1.5, 1.15], rotate=[-8, 0], ease="expo_out"),
    "ken_burns": dict(zoom=[1.05, 1.3], center=[[0.45, 0.55], [0.55, 0.45]]),
    "slam": dict(zoom=[2.0, 1.05], ease="expo_out"),
    "drift": dict(zoom=[1.1, 1.15], center=[[0.48, 0.5], [0.52, 0.5]], ease="linear"),
}


def resolve(cam):
    """Merge a shot's camera spec with its preset. Returns dict zoom/center/rotate/ease."""
    cam = dict(cam or {})
    preset = PRESETS.get(cam.get("preset", "static"))
    if preset is None:
        raise ValueError(f"unknown camera preset {cam.get('preset')!r}; options: {sorted(PRESETS)}")
    out = dict(zoom=[1.0, 1.0], center=[[0.5, 0.5], [0.5, 0.5]], rotate=[0, 0], ease="ease_in_out")
    out.update(preset)
    for k in ("zoom", "center", "rotate", "ease", "focus", "clamp", "keys"):
        if k in cam:
            out[k] = cam[k]
    # `focus: [x,y]` = keep the preset motion but aim it at a point of interest (e.g. a face)
    if "focus" in cam and "center" not in cam:
        fx, fy = cam["focus"]
        (ax, ay), (bx, by) = out["center"]
        out["center"] = [[fx + ax - 0.5, fy + ay - 0.5], [fx + bx - 0.5, fy + by - 0.5]]
    if not isinstance(out["zoom"], (list, tuple)):
        out["zoom"] = [out["zoom"], out["zoom"]]
    if not isinstance(out["rotate"], (list, tuple)):
        out["rotate"] = [out["rotate"], out["rotate"]]
    c = out["center"]
    if isinstance(c[0], (int, float)):
        out["center"] = [list(c), list(c)]
    out.setdefault("clamp", True)
    return out


def state(cam, p):
    """Camera state at shot progress p (0..1). Supports multi-key `keys:`."""
    if cam.get("keys"):
        # keys: [{at: 0, zoom: 1, center: [x,y], rotate: 0, ease: ...}, ...]  `at` is 0..1
        keys = sorted(cam["keys"], key=lambda k: k["at"])
        if p <= keys[0]["at"]:
            k = keys[0]
            return _key_vals(k, cam)
        for a, b in zip(keys, keys[1:]):
            if p <= b["at"]:
                q = (p - a["at"]) / max(1e-6, b["at"] - a["at"])
                q = ease(b.get("ease", cam["ease"]), q)
                va, vb = _key_vals(a, cam), _key_vals(b, cam)
                return {
                    "zoom": _lerp(va["zoom"], vb["zoom"], q),
                    "cx": _lerp(va["cx"], vb["cx"], q),
                    "cy": _lerp(va["cy"], vb["cy"], q),
                    "rot": _lerp(va["rot"], vb["rot"], q),
                }
        return _key_vals(keys[-1], cam)
    q = ease(cam["ease"], p)
    (ax, ay), (bx, by) = cam["center"]
    # zoom interpolated in log space so push-ins feel constant-speed
    z0, z1 = cam["zoom"]
    z = math.exp(_lerp(math.log(z0), math.log(z1), q))
    return {"zoom": z, "cx": _lerp(ax, bx, q), "cy": _lerp(ay, by, q),
            "rot": _lerp(cam["rotate"][0], cam["rotate"][1], q)}


def _key_vals(k, cam):
    c = k.get("center", [0.5, 0.5])
    return {"zoom": k.get("zoom", 1.0), "cx": c[0], "cy": c[1], "rot": k.get("rotate", 0.0)}


def _lerp(a, b, q):
    return a + (b - a) * q
