"""KittenTTS 2 的標記實測：<pause>、[情緒]、(((強調)))。同一段話、同樣的 seed，只差標記。"""
import json, re, time
import numpy as np
from buddy_host.config import default_home
from buddy_host.speech.cer import cer
from buddy_host.speech.engines import KittenSynthesizer, WhisperRecognizer
from buddy_host.speech.pipeline import SpeechResult, write_outputs
from buddy_host.speech.voice import load_reference

CASES = {
    "A_none": "你看右手邊那棟紅磚老屋。它已經兩百年了。想想看，那時候這裡全是河岸。",
    "B_pause": "你看右手邊那棟紅磚老屋。<pause> 它已經兩百年了。<pause> 想想看，那時候這裡全是河岸。",
    "C_contemplative": "[contemplative] 你看右手邊那棟紅磚老屋。它已經兩百年了。想想看，那時候這裡全是河岸。",
    "D_emphasis": "你看右手邊那棟紅磚老屋。它已經(((兩百年)))了。想想看，那時候這裡全是河岸。",
    "E_pause_contemplative": "[contemplative] 你看右手邊那棟紅磚老屋。<pause> 它已經兩百年了。<pause> 想想看，那時候這裡全是河岸。",
}
SEEDS = (1234, 42)
TAG = re.compile(r"\[[a-z]+\]|<[a-z]+>|\(\(\(|\)\)\)")

def silences(audio, rate, floor_db=-40.0, min_s=0.15):
    frame = int(rate * 0.02)
    n = len(audio) // frame
    rms = np.sqrt((audio[: n * frame].reshape(n, frame) ** 2).mean(axis=1) + 1e-12)
    quiet = 20 * np.log10(rms) < floor_db
    out, run = [], 0
    for q in quiet:
        if q: run += 1
        elif run:
            if run * 0.02 >= min_s: out.append(round(run * 0.02, 2))
            run = 0
    return out

home = default_home()
synth = KittenSynthesizer(load_reference(home / "voice" / "F2"))
asr = WhisperRecognizer(home / "cache" / "whisper")
out_dir = home / "out" / "tags-listen"
rows = []
for name, text in CASES.items():
    for seed in SEEDS:
        t0 = time.perf_counter()
        audio = synth.synthesize(text, seed)
        hyp = asr.transcribe(audio, synth.sample_rate)
        spoken = TAG.sub("", text)
        row = dict(case=name, seed=seed, seconds=round(len(audio) / synth.sample_rate, 2),
                   cer=round(cer(spoken, hyp), 3), hypothesis=hyp,
                   pauses=silences(audio, synth.sample_rate), took=round(time.perf_counter() - t0))
        rows.append(row)
        write_outputs(SpeechResult(audio, synth.sample_rate, [], 0.0), out_dir, f"{name}_seed{seed}")
        print(json.dumps(row, ensure_ascii=False), flush=True)
(out_dir / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print("TAGS_DONE", flush=True)
