"""Stable Diffusion helpers for manga character work (CPU friendly).

  colorize : B&W manga -> anime colour, line art locked with ControlNet lineart_anime
  inpaint  : redraw / complete masked regions with ControlNet inpaint (anime base model)

  python3 sd_tools.py colorize in.png out.png --prompt "..." [--steps 24 --size 768 --strength 1.0]
  python3 sd_tools.py inpaint in.png mask.png out.png --prompt "..." [--steps 24]
"""
import argparse
import os
import sys
import time

import cv2
import numpy as np
import torch
from PIL import Image

BASE = os.environ.get("MAD_SD_BASE", "gsdf/Counterfeit-V2.5")
CN_LINE = "lllyasviel/control_v11p_sd15s2_lineart_anime"
CN_INPAINT = "lllyasviel/control_v11p_sd15_inpaint"
NEG = ("lowres, bad anatomy, bad hands, worst quality, low quality, jpeg artifacts, monochrome, greyscale, "
       "text, signature, watermark, speech bubble, extra eyes, deformed")
QUALITY = "masterpiece, best quality, anime screencap, "

torch.set_num_threads(os.cpu_count() or 4)
_P = {}


def _pipe(kind):
    if kind in _P:
        return _P[kind]
    from diffusers import ControlNetModel, StableDiffusionControlNetPipeline, \
        StableDiffusionControlNetInpaintPipeline, DPMSolverMultistepScheduler
    cn = ControlNetModel.from_pretrained(CN_LINE if kind == "line" else CN_INPAINT, variant="fp16",
                                         torch_dtype=torch.float32)
    cls = StableDiffusionControlNetPipeline if kind == "line" else StableDiffusionControlNetInpaintPipeline
    p = cls.from_pretrained(BASE, controlnet=cn, torch_dtype=torch.float32, safety_checker=None,
                            requires_safety_checker=False)
    p.scheduler = DPMSolverMultistepScheduler.from_config(p.scheduler.config, use_karras_sigmas=True)
    p.set_progress_bar_config(disable=True)
    _P[kind] = p
    return p


def _fit(w, h, size):
    s = size / max(w, h)
    return int(round(w * s / 8) * 8), int(round(h * s / 8) * 8)


def lineart_from_manga(bgr, strength=1.0):
    """White lines on black: what lineart_anime expects. Keeps hatching/tone as texture."""
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    inv = 1 - g
    inv = np.clip(inv * strength, 0, 1)
    return (inv * 255).astype(np.uint8)


def colorize(src_bgr, prompt, steps=24, size=768, seed=1, cfg=7.0, cn_scale=1.0, neg=""):
    h, w = src_bgr.shape[:2]
    W, H = _fit(w, h, size)
    line = lineart_from_manga(cv2.resize(src_bgr, (W, H), interpolation=cv2.INTER_AREA))
    ctrl = Image.fromarray(line).convert("RGB")
    g = torch.Generator().manual_seed(seed)
    out = _pipe("line")(QUALITY + prompt, negative_prompt=NEG + ", " + neg, image=ctrl, num_inference_steps=steps,
                        guidance_scale=cfg, controlnet_conditioning_scale=cn_scale, generator=g,
                        width=W, height=H).images[0]
    return cv2.cvtColor(np.array(out), cv2.COLOR_RGB2BGR)


def inpaint(src_bgr, mask, prompt, steps=24, size=768, seed=1, cfg=7.0, strength=1.0, neg=""):
    h, w = src_bgr.shape[:2]
    W, H = _fit(w, h, size)
    img = cv2.resize(src_bgr, (W, H), interpolation=cv2.INTER_AREA)
    m = cv2.resize(mask, (W, H), interpolation=cv2.INTER_NEAREST) > 127
    ctrl = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    ctrl[m] = -1.0  # ControlNet-inpaint convention: masked pixels = -1
    ctrl_t = torch.from_numpy(ctrl.transpose(2, 0, 1))[None]
    g = torch.Generator().manual_seed(seed)
    out = _pipe("inpaint")(QUALITY + prompt, negative_prompt=NEG + ", " + neg,
                           image=Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)),
                           mask_image=Image.fromarray((m * 255).astype(np.uint8)), control_image=ctrl_t,
                           num_inference_steps=steps, guidance_scale=cfg, strength=strength, generator=g,
                           width=W, height=H).images[0]
    out = cv2.cvtColor(np.array(out), cv2.COLOR_RGB2BGR)
    out = cv2.resize(out, (w, h), interpolation=cv2.INTER_CUBIC)
    # keep original pixels outside the (feathered) mask
    mf = cv2.GaussianBlur((mask > 127).astype(np.float32), (0, 0), 3)[..., None]
    return (src_bgr * (1 - mf) + out * mf).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("colorize")
    c.add_argument("src")
    c.add_argument("out")
    i = sub.add_parser("inpaint")
    i.add_argument("src")
    i.add_argument("mask")
    i.add_argument("out")
    for p in (c, i):
        p.add_argument("--prompt", required=True)
        p.add_argument("--steps", type=int, default=24)
        p.add_argument("--size", type=int, default=768)
        p.add_argument("--seed", type=int, default=1)
        p.add_argument("--cfg", type=float, default=7.0)
        p.add_argument("--neg", default="")
    c.add_argument("--cn", type=float, default=1.0)
    i.add_argument("--strength", type=float, default=1.0)
    a = ap.parse_args()
    t = time.time()
    src = cv2.imread(a.src, cv2.IMREAD_COLOR)
    if a.cmd == "colorize":
        out = colorize(src, a.prompt, a.steps, a.size, a.seed, a.cfg, a.cn, a.neg)
    else:
        out = inpaint(src, cv2.imread(a.mask, cv2.IMREAD_GRAYSCALE), a.prompt, a.steps, a.size, a.seed, a.cfg,
                      a.strength, a.neg)
    cv2.imwrite(a.out, out)
    print(f"{a.out} {out.shape[1]}x{out.shape[0]} in {time.time() - t:.0f}s")


if __name__ == "__main__":
    sys.exit(main())
