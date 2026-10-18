"""KittenTTS 2 local synthesis for the TTS listening spike (CPU, local only)."""
import argparse
import os
import sys
import time

import numpy as np
import soundfile as sf

p = argparse.ArgumentParser()
p.add_argument("--spike", required=True)
p.add_argument("--device", default="cpu")
p.add_argument("--weights", default="packed")
p.add_argument("--decoder", default="default")
p.add_argument("--seed", type=int, default=1234)
p.add_argument("--only", default="", help="comma list of job names to run")
p.add_argument("--suffix", default="")
p.add_argument("--no-ref-prompt", action="store_true")
args = p.parse_args()

S = args.spike
script = open(f"{S}/script.txt", encoding="utf-8").read().strip()
short = open(f"{S}/short.txt", encoding="utf-8").read().strip()
ref_wav = f"{S}/ref/ref_24k.wav"
ref_text = open(f"{S}/ref/ref_text.txt", encoding="utf-8").read().strip()

from kittenml.kittentts2 import text as T  # noqa: E402

for name, t in (("script", script), ("short", short), ("ref_text", ref_text)):
    norm = T.normalize_text(t, normalize=False)
    chunks = T.split_for_synthesis(norm)
    print(f"[text] {name}: len={len(t)} normalized={norm!r} chunks={len(chunks)}", flush=True)

from kittenml import KittenTTS  # noqa: E402

t0 = time.perf_counter()
m = KittenTTS("KittenML/kitten-tts-2", device=args.device, weights=args.weights,
              decoder=args.decoder)
load_s = time.perf_counter() - t0
print(f"[load] {load_s:.2f}s device={m.device} weights={m.weights} decoder={m.decoder} "
      f"sr={m.sample_rate}", flush=True)
print(f"[voices] Chinese in voices: {'Chinese' in m.available_voices}", flush=True)

out = f"{S}/out"
jobs = [
    ("03_kitten2_chinese_short", short, dict(voice="Chinese")),
    ("03_kitten2_chinese", script, dict(voice="Chinese")),
    ("04_kitten2_clone_tw", script, dict(reference=ref_wav, reference_text=ref_text)),
    ("04_kitten2_clone_tw_short", short, dict(reference=ref_wav, reference_text=ref_text)),
]
only = set(filter(None, args.only.split(",")))
for name, text, spk in jobs:
    if only and name not in only:
        continue
    kw = dict(normalize=False, advanced={"seed": args.seed})
    if args.no_ref_prompt:
        kw["use_reference_prompt"] = False
    t1 = time.perf_counter()
    wav = m.generate(text, **spk, **kw)
    synth_s = time.perf_counter() - t1
    wav = np.asarray(wav, dtype=np.float32)
    dur = len(wav) / m.sample_rate
    peak = float(np.abs(wav).max()) if len(wav) else 0.0
    rms = float(np.sqrt((wav ** 2).mean())) if len(wav) else 0.0
    path = f"{out}/{name}{args.suffix}.wav"
    sf.write(path, wav, m.sample_rate, subtype="PCM_16")
    print(f"[out] {name}{args.suffix}: synth={synth_s:.2f}s dur={dur:.2f}s "
          f"RTF={synth_s / dur if dur else float('nan'):.2f} peak={peak:.3f} "
          f"rms={rms:.4f} -> {path}", flush=True)
