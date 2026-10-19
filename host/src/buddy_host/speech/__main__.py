"""手動合成：python -m buddy_host.speech --text-file 稿子.txt --name demo"""

import argparse
import time
from pathlib import Path

from buddy_host.config import default_home
from buddy_host.speech.pipeline import PipelineConfig, SpeechPipeline, write_outputs
from buddy_host.speech.voice import load_reference


def main() -> None:
    home = default_home()
    parser = argparse.ArgumentParser(description="稿子 → 驗收過的語音")
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--voice", default="F2", help="~/.buddy-host/voice/ 底下的聲音名稱")
    parser.add_argument("--out-dir", type=Path, default=home / "out")
    parser.add_argument("--cer-threshold", type=float, default=PipelineConfig.cer_threshold)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(PipelineConfig.seeds))
    parser.add_argument("--no-split", action="store_true", help="全部 seed 失敗時不拆句")
    parser.add_argument("--device", default="mps")
    args = parser.parse_args()

    voice = load_reference(home / "voice" / args.voice)
    text = args.text_file.read_text(encoding="utf-8")

    from buddy_host.speech.engines import KittenSynthesizer, WhisperRecognizer

    t0 = time.perf_counter()
    synthesizer = KittenSynthesizer(voice, device=args.device)
    recognizer = WhisperRecognizer(home / "cache" / "whisper")
    load_seconds = time.perf_counter() - t0
    print(f"[load] {load_seconds:.1f}s", flush=True)

    config = PipelineConfig(
        seeds=tuple(args.seeds),
        cer_threshold=args.cer_threshold,
        split_on_failure=not args.no_split,
    )

    def show(index: int, total: int, sentence) -> None:
        tries = " ".join(f"{a.seed}:{a.cer:.2f}" for a in sentence.attempts)
        print(f"[{index}/{total}] {sentence.status} ({tries}) {sentence.text[:20]}", flush=True)

    result = SpeechPipeline(synthesizer, recognizer, config, progress=show).run(text)
    wav_path, log_path = write_outputs(result, args.out_dir, args.name)

    log = result.to_log()
    statuses = [s["status"] for s in log["chunks"]]
    print(f"[done] audio={log['audio_seconds']}s wall={log['wall_seconds']}s rtf={log['rtf']}")
    print(
        f"[done] chunks={len(statuses)} ok={statuses.count('ok')} "
        f"approx={statuses.count('approx')} split={statuses.count('split')} "
        f"skipped={statuses.count('skipped')}"
    )
    print(f"[out] {wav_path}\n[out] {log_path}")


if __name__ == "__main__":
    main()
