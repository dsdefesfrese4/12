"""SDXL anime inpaint / outpaint (Animagine XL 4.0) on CPU.

  python3 sdxl_tools.py init.png mask.png out.png --prompt "..." [--strength 0.9 --steps 28 --mp 0.9 --seed 1]

init.png : canvas to start from (original pasted in, plus a rough guide painted where things are missing)
mask.png : white = (re)draw, black = keep
Output is composited back onto init at full resolution with a feathered mask, so kept pixels stay
pixel-identical to the source.
Prompts use Danbooru tags; quality tags are appended automatically.
"""
import argparse
import math
import os
import sys
import time

import cv2
import numpy as np
import torch
from PIL import Image

MODEL = os.environ.get("MAD_SDXL", "cagliostrolab/animagine-xl-4.0")
QUALITY = ", masterpiece, high score, great score, absurdres"
NEG = ("lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, fewer digits, cropped, "
       "worst quality, low quality, low score, bad score, average score, signature, watermark, username, "
       "blurry, speech bubble, frame, border")

torch.set_num_threads(os.cpu_count() or 4)
DTYPE = {"bf16": torch.bfloat16, "fp32": torch.float32}[os.environ.get("MAD_SDXL_DTYPE", "fp32")]


def encode_prompts(prompt, neg):
    """Run both text encoders, then free them (SDXL in fp32 does not fit in 14 GB otherwise)."""
    import gc
    from diffusers import StableDiffusionXLPipeline
    tp = StableDiffusionXLPipeline.from_pretrained(MODEL, unet=None, vae=None, torch_dtype=torch.float32,
                                                   use_safetensors=True)
    with torch.no_grad():
        pe, npe, ppe, nppe = tp.encode_prompt(prompt, device="cpu", num_images_per_prompt=1,
                                              do_classifier_free_guidance=True, negative_prompt=neg)
    del tp
    gc.collect()
    return pe, npe, ppe, nppe


def pipe():
    from diffusers import StableDiffusionXLInpaintPipeline, EulerAncestralDiscreteScheduler
    p = StableDiffusionXLInpaintPipeline.from_pretrained(MODEL, text_encoder=None, text_encoder_2=None,
                                                         tokenizer=None, tokenizer_2=None, torch_dtype=DTYPE,
                                                         use_safetensors=True, low_cpu_mem_usage=True)
    p.vae.to(torch.float32)  # fp32 VAE avoids colour/NaN artefacts
    p.scheduler = EulerAncestralDiscreteScheduler.from_config(p.scheduler.config)
    p.enable_attention_slicing()
    p.vae.enable_tiling()
    p.set_progress_bar_config(disable=False)
    return p


def gen_size(w, h, mp):
    s = math.sqrt(mp * 1e6 / (w * h))
    return int(round(w * s / 64) * 64), int(round(h * s / 64) * 64)


def inpaint(init_bgr, mask, prompt, neg="", strength=0.9, steps=28, mp=0.9, seed=1, cfg=6.0, feather=6):
    h, w = init_bgr.shape[:2]
    W, H = gen_size(w, h, mp)
    img = Image.fromarray(cv2.cvtColor(cv2.resize(init_bgr, (W, H), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB))
    m = Image.fromarray(cv2.resize(mask, (W, H), interpolation=cv2.INTER_LINEAR))
    g = torch.Generator().manual_seed(seed)
    pe, npe, ppe, nppe = encode_prompts(prompt + QUALITY, NEG + (", " + neg if neg else ""))
    p = pipe()
    out = p(prompt_embeds=pe.to(DTYPE), negative_prompt_embeds=npe.to(DTYPE), pooled_prompt_embeds=ppe.to(DTYPE),
            negative_pooled_prompt_embeds=nppe.to(DTYPE), image=img, mask_image=m, width=W, height=H,
            strength=strength, num_inference_steps=steps, guidance_scale=cfg, generator=g).images[0]
    out = cv2.resize(cv2.cvtColor(np.array(out), cv2.COLOR_RGB2BGR), (w, h), interpolation=cv2.INTER_LANCZOS4)
    mf = cv2.GaussianBlur((mask > 127).astype(np.float32), (0, 0), feather)[..., None]
    return (init_bgr * (1 - mf) + out * mf).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("init")
    ap.add_argument("mask")
    ap.add_argument("out")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--neg", default="")
    ap.add_argument("--strength", type=float, default=0.9)
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--mp", type=float, default=0.9, help="generation size in megapixels")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--cfg", type=float, default=6.0)
    a = ap.parse_args()
    t = time.time()
    init = cv2.imread(a.init, cv2.IMREAD_COLOR)
    mask = cv2.imread(a.mask, cv2.IMREAD_GRAYSCALE)
    out = inpaint(init, mask, a.prompt, a.neg, a.strength, a.steps, a.mp, a.seed, a.cfg)
    cv2.imwrite(a.out, out)
    print(f"{a.out} in {time.time() - t:.0f}s")


if __name__ == "__main__":
    sys.exit(main())
