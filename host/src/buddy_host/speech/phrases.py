"""固定短句（設計文件第 9.3 節）與試聽候選的產生。

python -m buddy_host.speech.phrases
    → ~/.buddy-host/out/phrases/<編號>/seed<seed>_cer<百分比>.wav
    每句產生到至少 3 個通過驗收的版本（最多試 8 個 seed），由使用者試聽挑選。

python -m buddy_host.speech.phrases --finalize 1:42 2:42 ...
    對已挑好的版本重新驗收（句首檢查、裁掉多餘的前導聲音）
    → ~/.buddy-host/out/phrases-final/<編號>.wav

python -m buddy_host.speech.phrases --voice <聲音> --auto [--max-seeds 8]
    不必人工挑選：每句試多個 seed，在通過驗收門檻的版本裡挑 CER 最低（同分取較短）的一版
    → ~/.buddy-host/out/voice-phrases/<聲音鍵>/<編號>.wav（聲音鍵含語速，如 F2@1.2）
    開頭是語氣詞的句子（嗯、喔）機器驗不準，通過的版本都另存在 candidates/<編號>_seed<seed>.wav，
    聽過覺得自動挑的不好，直接把喜歡的複製成 <編號>.wav。
    上面兩條人工流程的輸出目錄不受影響。某句沒有任何版本通過就不寫那一句，列出來並以非 0 結束。
"""

import argparse
import json
import sys
import wave
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import numpy as np

from buddy_host.config import default_home, load_config
from buddy_host.speech.pipeline import PipelineConfig, SpeechPipeline, SpeechResult, write_outputs
from buddy_host.speech.text_prep import prepare_sentences

# 編號沿用設計文件 9.3；5（額度用完）與 8（恢復）已取消，改成畫面提示與自動繼續
PHRASES: dict[int, tuple[str, str]] = {
    1: ("嗯嗯，讓我想一下。", "問答開頭"),
    2: ("喔，這個有意思，我想想看。", "問答開頭替換"),
    3: ("嗯，我整理一下該怎麼講。", "答案還沒好時補一句"),
    4: ("這個要查一下，會稍微久一點。", "需要上網查時"),
    6: ("我這邊訊號不太好，等連上了，我再接著講。", "連不上主機"),
    7: ("好，走吧，我陪你。", "按出發時"),
}
# 開頭是語氣詞的短句：Whisper 聽不準語氣詞，--auto 只驗語氣詞後面的字，語氣詞靠人耳聽
LEAD_FILLERS = {1: "嗯嗯", 2: "喔", 3: "嗯"}
CANDIDATE_SEEDS = (1234, 7, 42, 2026, 99, 314, 777, 2468)
WANTED = 3
DEFAULT_MAX_SEEDS = 8


class _Best(NamedTuple):
    cer: float
    samples: int
    seed: int
    audio: np.ndarray
    hypothesis: str


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


def voice_phrases_dir(home: Path, voice_key: str) -> Path:
    """某個聲音（含語速）的固定短句；和人工挑選流程的 out/phrases 分開。"""
    return home / "out" / "voice-phrases" / voice_key


def seed_sequence(count: int) -> tuple[int, ...]:
    """前 8 個與人工挑選流程相同；要試更多就接著往後補（不重複）。"""
    seeds = list(CANDIDATE_SEEDS[:count])
    candidate = 1
    while len(seeds) < count:
        if candidate not in seeds:
            seeds.append(candidate)
        candidate += 1
    return tuple(seeds)


def phrases_ready(home: Path, voice_key: str, phrases: Mapping[int, object] = PHRASES) -> bool:
    """這個聲音（目前語速）的固定短句是不是每一句都已經產生。改了語速，聲音鍵就變了。"""
    folder = voice_phrases_dir(home, voice_key)
    return all((folder / f"{number}.wav").is_file() for number in phrases)


def auto_voice_phrases(
    pipeline,
    sample_rate: int,
    out_dir: Path,
    *,
    max_seeds: int = DEFAULT_MAX_SEEDS,
    phrases: Mapping[int, tuple[str, str]] = PHRASES,
    only: Collection[int] | None = None,
    report: Callable[[str], None] = print,
) -> list[int]:
    """每句最多試 `max_seeds` 個 seed，把通過驗收門檻的最佳版本寫進 `out_dir/<編號>.wav`。

    最佳＝CER 最低，同分取較短（短的通常是少了拖長的尾巴）。全部 seed 都沒通過的那一句不寫，
    編號放進回傳值，呼叫端據此以非 0 結束。
    """
    failed: list[int] = []
    summary: dict[str, dict] = {}
    for number, (text, _) in phrases.items():
        if only and number not in only:
            continue
        spoken = "".join(prepare_sentences(text))
        threshold = pipeline.threshold_for(spoken)
        best: _Best | None = None
        for seed in seed_sequence(max_seeds):
            if number in LEAD_FILLERS:
                attempt, audio = pipeline.attempt_after_lead_filler(
                    spoken, LEAD_FILLERS[number], seed
                )
            else:
                attempt, audio = pipeline.attempt(spoken, seed)
            passed = attempt.rejected is None and attempt.cer <= threshold
            report(
                f"[{number}] seed={seed} cer={attempt.cer:.2f} "
                f"{'OK' if passed else 'x ' + (attempt.rejected or '')}".rstrip()
            )
            if passed and number in LEAD_FILLERS:  # 語氣詞有沒有唸出來要人耳聽：每個通過的都留著
                candidate = SpeechResult(audio, sample_rate, [], 0.0)
                write_outputs(candidate, out_dir / "candidates", f"{number}_seed{seed}")
            if passed and (best is None or (attempt.cer, len(audio)) < (best.cer, best.samples)):
                best = _Best(attempt.cer, len(audio), seed, audio, attempt.hypothesis)
        if best is None:
            failed.append(number)
            for suffix in (".wav", ".log.json"):  # 上次的檔講的可能是舊稿：留著會被當成已準備
                (out_dir / f"{number}{suffix}").unlink(missing_ok=True)
            report(f"[{number}] 沒有任何版本通過驗收，不寫入：{text}")
            continue
        cer, _, seed, audio, hypothesis = best
        write_outputs(SpeechResult(audio, sample_rate, [], 0.0), out_dir, str(number))
        summary[str(number)] = {
            "text": text,
            "seed": seed,
            "cer": round(cer, 3),
            "hypothesis": hypothesis,
        }
        report(f"[{number}] 採用 seed={seed} cer={cer:.2f} 長度={len(audio) / sample_rate:.2f}s")
    index = out_dir / "index.json"
    if summary or (failed and index.exists()):
        out_dir.mkdir(parents=True, exist_ok=True)
        previous = json.loads(index.read_text(encoding="utf-8")) if index.exists() else {}
        kept = {k: v for k, v in previous.items() if int(k) not in failed}  # 失敗那句的舊記錄作廢
        index.write_text(
            json.dumps({**kept, **summary}, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return failed


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
    parser.add_argument("--voice", default=load_config(home).voice)
    parser.add_argument("--out-dir", type=Path, default=home / "out" / "phrases")
    parser.add_argument("--only", type=int, nargs="*")
    parser.add_argument(
        "--auto", action="store_true", help="自動挑選：每句試多個 seed，存最好的一版（不必人工聽）"
    )
    parser.add_argument(
        "--max-seeds", type=int, default=DEFAULT_MAX_SEEDS, help="--auto 每句最多試幾個 seed"
    )
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

    voice = load_reference(home / "voice" / args.voice)
    synth = KittenSynthesizer(voice)
    pipeline = SpeechPipeline(
        synth, WhisperRecognizer(home / "cache" / "whisper"), PipelineConfig()
    )
    if args.auto:
        failed = auto_voice_phrases(
            pipeline,
            synth.sample_rate,
            voice_phrases_dir(home, voice.key),
            max_seeds=args.max_seeds,
            only=args.only,
            report=lambda line: print(line, flush=True),
        )
        if failed:
            sorted_failed = ", ".join(str(n) for n in sorted(failed))
            print(
                f"[{voice.key}] 這些句子沒有版本通過：{sorted_failed}"
                "（可加大 --max-seeds 再跑；沒寫入的句子，這個聲音會維持「短句未準備」）"
            )
            sys.exit(1)
        print(f"[{voice.key}] 短句都已準備")
        return
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
