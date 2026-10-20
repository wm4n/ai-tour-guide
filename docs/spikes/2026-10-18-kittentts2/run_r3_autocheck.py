"""Round 3: KittenTTS 2 with female ref (F2) + Whisper auto-check (local only).

Long texts: split into sentence chunks; per chunk try seeds until CER <= THRESH,
keep best. Writes <name>_firsttry.wav (seed 1234 only) and <name>_checked.wav.
Short texts: one file per seed, each labelled with its CER.
"""
import json
import re
import sys
import time

import numpy as np
import opencc
import soundfile as sf
import whisper

S = sys.argv[1]
THRESH = 0.20
SEEDS = [1234, 7, 42, 2026]
OUT = f"{S}/out3"
ref_wav = f"{S}/refF2/ref_24k.wav"
ref_text = open(f"{S}/refF2/ref_text.txt", encoding="utf-8").read().strip()
t2s = opencc.OpenCC("t2s")


def norm(t):
    t = t2s.convert(t).lower()
    return "".join(re.findall(r"[一-鿿a-z0-9]", t))


def cer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    if not r:
        return 0.0
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev = cur
    return d[len(h)] / len(r)


def chunks_of(text, limit=90):
    out = []
    for line in [l.strip() for l in text.splitlines() if l.strip()]:
        sents = [s for s in re.split(r"(?<=[。！？])", line) if s.strip()]
        cur = ""
        for s in sents:
            if cur and len(cur) + len(s) > limit:
                out.append(cur)
                cur = ""
            cur += s
        if cur:
            out.append(cur)
    return out


from kittenml import KittenTTS  # noqa: E402

t0 = time.perf_counter()
tts = KittenTTS("KittenML/kitten-tts-2", device="mps", weights="packed", decoder="default")
asr = whisper.load_model("small", download_root=f"{S}/cache/whisper", device="cpu")
print(f"[load] {time.perf_counter() - t0:.1f}s", flush=True)
SR = tts.sample_rate


def synth(text, seed):
    t = time.perf_counter()
    wav = np.asarray(tts.generate(text, reference=ref_wav, reference_text=ref_text,
                                  normalize=False, advanced={"seed": seed}), dtype=np.float32)
    syn = time.perf_counter() - t
    t = time.perf_counter()
    a16 = whisper.audio.resample(wav, SR, 16000) if hasattr(whisper.audio, "resample") else None
    if a16 is None:
        import librosa
        a16 = librosa.resample(wav, orig_sr=SR, target_sr=16000)
    hyp = asr.transcribe(a16.astype(np.float32), language="zh", fp16=False,
                         initial_prompt="以下是台灣中文的旅遊導覽。")["text"]
    chk = time.perf_counter() - t
    return wav, hyp, cer(text, hyp), syn, chk


log = {}
gap = np.zeros(int(SR * 0.3), dtype=np.float32)
for name in sys.argv[2:]:
    text = open(f"{S}/texts3/{name}.txt", encoding="utf-8").read().strip()
    log[name] = []
    if len(text) < 30:
        for seed in SEEDS[:3]:
            wav, hyp, c, syn, chk = synth(text, seed)
            sf.write(f"{OUT}/{name}_seed{seed}_cer{int(c * 100):02d}.wav", wav, SR, subtype="PCM_16")
            log[name].append(dict(seed=seed, cer=round(c, 3), hyp=hyp, synth=round(syn, 1),
                                  dur=round(len(wav) / SR, 2), check=round(chk, 1)))
            print(f"[short] {name} seed={seed} cer={c:.2f} dur={len(wav) / SR:.2f}s hyp={hyp}", flush=True)
        continue
    first, best_all = [], []
    for i, ch in enumerate(chunks_of(text)):
        tries = []
        for seed in SEEDS:
            wav, hyp, c, syn, chk = synth(ch, seed)
            tries.append((c, seed, wav, hyp, syn, chk))
            print(f"[chunk] {name}#{i} seed={seed} cer={c:.2f} dur={len(wav) / SR:.1f}s "
                  f"synth={syn:.1f}s check={chk:.1f}s", flush=True)
            if c <= THRESH:
                break
        first.append(tries[0][2])
        best = min(tries, key=lambda x: x[0])
        best_all.append(best[2])
        log[name].append(dict(chunk=ch, tries=[dict(seed=s, cer=round(c, 3), hyp=h, synth=round(sy, 1),
                                                     check=round(ck, 1))
                                                for c, s, _, h, sy, ck in tries],
                              chosen_seed=best[1], chosen_cer=round(best[0], 3)))
    for tag, parts in (("firsttry", first), ("checked", best_all)):
        wav = np.concatenate([np.concatenate([p, gap]) for p in parts])
        sf.write(f"{OUT}/{name}_{tag}.wav", wav, SR, subtype="PCM_16")
        print(f"[out] {name}_{tag}.wav dur={len(wav) / SR:.1f}s", flush=True)
    json.dump(log, open(f"{OUT}/autocheck_log.json", "w"), ensure_ascii=False, indent=1)

json.dump(log, open(f"{OUT}/autocheck_log.json", "w"), ensure_ascii=False, indent=1)
print("[done]", flush=True)
