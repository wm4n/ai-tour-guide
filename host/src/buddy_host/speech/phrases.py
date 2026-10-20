"""固定短句（設計文件第 9.3 節）與試聽候選的產生。

python -m buddy_host.speech.phrases
    → ~/.buddy-host/out/phrases/<編號>/seed<seed>_cer<百分比>.wav
    每句產生到至少 3 個通過驗收的版本（最多試 8 個 seed），由使用者試聽挑選。

python -m buddy_host.speech.phrases --finalize 1:42 2:42 ...
    對已挑好的版本重新驗收（句首檢查、裁掉多餘的前導聲音）
    → ~/.buddy-host/out/phrases-final/<編號>.wav
"""

import argparse
import json
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from buddy_host.config import default_home
from buddy_host.speech.pipeline import PipelineConfig, SpeechPipeline, SpeechResult, write_outputs
from buddy_host.speech.text_prep import prepare_sentences

# 編號沿用設計文件 9.3；5（額度用完）與 8（恢復）已取消，改成畫面提示與自動繼續
PHRASES: dict[int, tuple[str, str]] = {
    1: ("好，我來查一下，你稍等我一下。", "問答開頭"),
    2: ("這個問題很好，讓我想一下。", "問答開頭替換"),
    3: ("我想想怎麼說比較好。", "答案還沒好時補一句"),
    4: ("我上網查一下，可能要多等一下。", "需要上網查時"),
    6: ("我連不上家裡的電腦了，先安靜一下，連上了再跟你說。", "連不上主機"),
    7: ("好，我們出發吧！", "按出發時"),
}
CANDIDATE_SEEDS = (1234, 7, 42, 2026, 99, 314, 777, 2468)
WANTED = 3


@dataclass
class Candidate:
    seed: int
    cer: float
    hypothesis: str
    wav: str | None
    trimmed_seconds: float = 0.0
    rejected: str | None = None


class _ReviewOnly:
    """只做驗收（不合成）時用的替身，省下載入 KittenTTS 的記憶體與時間。"""

    def __init__(self, sample_rate: int):
        self.sample_rate = sample_rate

    def synthesize(self, text: str, seed: int) -> np.ndarray:
        raise RuntimeError("review-only synthesizer cannot synthesize")


def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path)) as wav:
        rate = wav.getframerate()
        pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
    return pcm.astype(np.float32) / 32768, rate


def finalize(home: Path, voice_picks: dict[int, int]) -> None:
    from buddy_host.speech.engines import WhisperRecognizer

    asr = WhisperRecognizer(home / "cache" / "whisper")
    source, target = home / "out" / "phrases", home / "out" / "phrases-final"
    for number, seed in voice_picks.items():
        text = PHRASES[number][0]
        spoken = "".join(prepare_sentences(text))
        matches = sorted((source / str(number)).glob(f"seed{seed}_cer*.wav"))
        if not matches:
            print(f"[{number}] 找不到 seed{seed} 的音檔")
            continue
        audio, rate = _read_wav(matches[0])
        pipeline = SpeechPipeline(_ReviewOnly(rate), asr, PipelineConfig())
        attempt, final_audio = pipeline.review(spoken, audio, seed=seed)
        ok = attempt.rejected is None
        warn = " ⚠ CER 高於門檻" if attempt.cer > pipeline.threshold_for(spoken) else ""
        print(
            f"[{number}] seed{seed} {'句首OK' if ok else '句首不通過'} cer={attempt.cer:.3f}{warn} "
            f"裁掉前導 {attempt.trimmed_seconds:.2f}s rejected={attempt.rejected} "
            f"轉寫={attempt.hypothesis}"
        )
        if ok:  # 你已經用耳朵挑過了，所以句首沒問題就輸出；CER 只當提示
            write_outputs(SpeechResult(final_audio, rate, [], 0.0), target, str(number))


def main() -> None:
    home = default_home()
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", default="F2")
    parser.add_argument("--out-dir", type=Path, default=home / "out" / "phrases")
    parser.add_argument("--only", type=int, nargs="*")
    parser.add_argument(
        "--finalize", nargs="*", metavar="編號:seed", help="例如 1:42 2:42，只重新驗收不合成"
    )
    args = parser.parse_args()

    if args.finalize is not None:
        picks = {int(a.split(":")[0]): int(a.split(":")[1]) for a in args.finalize}
        finalize(home, picks)
        return

    from buddy_host.speech.engines import KittenSynthesizer, WhisperRecognizer
    from buddy_host.speech.voice import load_reference

    synth = KittenSynthesizer(load_reference(home / "voice" / args.voice))
    pipeline = SpeechPipeline(
        synth, WhisperRecognizer(home / "cache" / "whisper"), PipelineConfig()
    )
    index: dict[str, dict] = {}
    for number, (text, usage) in PHRASES.items():
        if args.only and number not in args.only:
            continue
        spoken = "".join(prepare_sentences(text))
        passed = 0
        tries: list[Candidate] = []
        for seed in CANDIDATE_SEEDS:
            attempt, audio = pipeline.attempt(spoken, seed)
            threshold = pipeline.threshold_for(spoken)
            wav = None
            if attempt.rejected is None and attempt.cer <= threshold:
                passed += 1
                name = f"seed{seed}_cer{round(attempt.cer * 100):02d}"
                path, _ = write_outputs(
                    SpeechResult(audio, synth.sample_rate, [], 0.0),
                    args.out_dir / str(number),
                    name,
                )
                wav = str(path)
            tries.append(
                Candidate(
                    seed, round(attempt.cer, 3), attempt.hypothesis, wav,
                    round(attempt.trimmed_seconds, 2), attempt.rejected,
                )
            )  # fmt: skip
            note = f" 裁{attempt.trimmed_seconds:.2f}s" if attempt.trimmed_seconds else ""
            print(
                f"[{number}] seed={seed} cer={attempt.cer:.2f}{note} {'OK' if wav else 'x'}",
                flush=True,
            )
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
