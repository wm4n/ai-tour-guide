"""固定短句（設計文件第 9.3 節）與試聽候選的產生。

python -m buddy_host.speech.phrases  → ~/.buddy-host/out/phrases/<編號>/seed<seed>_cer<百分比>.wav
每句產生到至少 3 個通過驗收的版本（最多試 8 個 seed），由使用者試聽挑選。
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from buddy_host.config import default_home
from buddy_host.speech.cer import cer
from buddy_host.speech.pipeline import PipelineConfig
from buddy_host.speech.text_prep import prepare_sentences

PHRASES: dict[int, tuple[str, str]] = {
    1: ("好，我來查一下，你稍等我一下。", "問答開頭"),
    2: ("這個問題很好，讓我想一下。", "問答開頭替換"),
    3: ("我想想怎麼說比較好。", "答案還沒好時補一句"),
    4: ("我上網查一下，可能要多等一下。", "需要上網查時"),
    5: ("額度用完了，我先安靜陪你走。", "額度用完"),
    6: ("我連不上家裡的電腦了，先安靜一下，連上了再跟你說。", "連不上主機"),
    7: ("好，我們出發吧！", "按出發時"),
    8: ("我恢復了，我們繼續。", "額度恢復或重新連上"),
}
CANDIDATE_SEEDS = (1234, 7, 42, 2026, 99, 314, 777, 2468)
WANTED = 3


@dataclass
class Candidate:
    seed: int
    cer: float
    hypothesis: str
    wav: str | None


def main() -> None:
    home = default_home()
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", default="F2")
    parser.add_argument("--out-dir", type=Path, default=home / "out" / "phrases")
    parser.add_argument("--threshold", type=float, default=PipelineConfig.cer_threshold)
    parser.add_argument("--only", type=int, nargs="*")
    args = parser.parse_args()

    from buddy_host.speech.engines import KittenSynthesizer, WhisperRecognizer
    from buddy_host.speech.pipeline import SpeechResult, write_outputs
    from buddy_host.speech.voice import load_reference

    synth = KittenSynthesizer(load_reference(home / "voice" / args.voice))
    asr = WhisperRecognizer(home / "cache" / "whisper")
    index: dict[str, dict] = {}
    for number, (text, usage) in PHRASES.items():
        if args.only and number not in args.only:
            continue
        spoken = "".join(prepare_sentences(text))
        passed = 0
        tries: list[Candidate] = []
        for seed in CANDIDATE_SEEDS:
            audio = synth.synthesize(spoken, seed)
            hypothesis = asr.transcribe(audio, synth.sample_rate)
            score = cer(spoken, hypothesis)
            wav = None
            if score <= args.threshold:
                passed += 1
                name = f"seed{seed}_cer{round(score * 100):02d}"
                result = SpeechResult(audio, synth.sample_rate, [], 0.0)
                path, _ = write_outputs(result, args.out_dir / str(number), name)
                wav = str(path)
            tries.append(Candidate(seed, round(score, 3), hypothesis, wav))
            print(f"[{number}] seed={seed} cer={score:.2f} {'OK' if wav else 'x'}", flush=True)
            if passed >= WANTED:
                break
        index[str(number)] = {
            "text": text,
            "usage": usage,
            "passed": passed,
            "candidates": [c.__dict__ for c in tries],
        }
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / "index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
