"""批次實測語助詞：python -m buddy_host.speech.particle_probe

結果逐筆追加到 ~/.buddy-host/out/particles.jsonl，中斷後重跑會跳過已完成的組合。
"""

import argparse
import json
import time
from pathlib import Path

from buddy_host.config import default_home
from buddy_host.speech.cer import cer
from buddy_host.speech.particles import CASES, SEEDS, summarize
from buddy_host.speech.pipeline import PipelineConfig
from buddy_host.speech.voice import load_reference


def load_done(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def save_listening_samples(home: Path, voice: str, out_dir: Path, words: list[str]) -> None:
    """CER 量不出「像不像粵語腔」，所以另存音檔讓人耳確認。"""
    from buddy_host.speech.engines import KittenSynthesizer
    from buddy_host.speech.pipeline import SpeechResult, write_outputs

    synth = KittenSynthesizer(load_reference(home / "voice" / voice))
    for word in words:
        audio = synth.synthesize(CASES[word][0], SEEDS[0])
        result = SpeechResult(audio, synth.sample_rate, [], 0.0)
        write_outputs(result, out_dir, f"{word}_seed{SEEDS[0]}")
        print(f"[listen] {word}: {CASES[word][0]}", flush=True)


def main() -> None:
    home = default_home()
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", default="F2")
    parser.add_argument("--out", type=Path, default=home / "out" / "particles.jsonl")
    parser.add_argument("--threshold", type=float, default=PipelineConfig.cer_threshold)
    parser.add_argument("--only", nargs="*", help="只測這幾個詞")
    parser.add_argument(
        "--listen",
        type=Path,
        help="另外把每個詞各合成一段（第 1 句、第 1 個 seed）存到這個資料夾，供人耳確認口音",
    )
    args = parser.parse_args()

    records = load_done(args.out)
    done = {(r["word"], r["sentence_index"], r["seed"]) for r in records}
    words = args.only or list(CASES)
    todo = [
        (w, i, s)
        for w in words
        for i in range(len(CASES[w]))
        for s in SEEDS
        if (w, i, s) not in done
    ]
    print(f"[plan] 待測 {len(todo)} 組（已完成 {len(done)}）", flush=True)

    if todo:
        from buddy_host.speech.engines import KittenSynthesizer, WhisperRecognizer

        synth = KittenSynthesizer(load_reference(home / "voice" / args.voice))
        asr = WhisperRecognizer(home / "cache" / "whisper")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        for n, (word, index, seed) in enumerate(todo, start=1):
            text = CASES[word][index]
            t0 = time.perf_counter()
            audio = synth.synthesize(text, seed)
            t1 = time.perf_counter()
            hypothesis = asr.transcribe(audio, synth.sample_rate)
            record = {
                "word": word,
                "sentence_index": index,
                "text": text,
                "seed": seed,
                "cer": round(cer(text, hypothesis), 3),
                "hypothesis": hypothesis,
                "audio_seconds": round(len(audio) / synth.sample_rate, 2),
                "synth_seconds": round(t1 - t0, 1),
                "check_seconds": round(time.perf_counter() - t1, 1),
            }
            with args.out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            records.append(record)
            print(f"[{n}/{len(todo)}] {word} #{index} seed={seed} cer={record['cer']}", flush=True)

    if args.listen:
        save_listening_samples(home, args.voice, args.listen, args.only or list(CASES))

    summary = summarize(records, args.threshold)
    for word, s in summary.items():
        stats = f"pass={s['passed']}/{s['runs']} mean={s['mean_cer']} max={s['max_cer']}"
        print(f"{s['label']:8} {word:4} {stats}")


if __name__ == "__main__":
    main()
