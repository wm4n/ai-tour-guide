"""啟動 Buddy Host。

介紹準備器有兩種，都要明確指定，沒指定時旅程端點回 503：
- `--replay-dir`：重播先前做好的介紹，不呼叫 Claude，用來在桌上跑通 App 流程。
- `--max-llm-calls N`：真的寫稿與合成。每次呼叫都消耗 Claude Pro 額度，用完 N 次就停止準備。
"""

import argparse
import sys
from pathlib import Path

import uvicorn

from buddy_host.app import create_app
from buddy_host.config import default_home, load_config
from buddy_host.llm.claude_cli import ClaudeSettings

PERSONA = Path(__file__).resolve().parents[2] / "config" / "buddy.md"
DAY = 24 * 3600


def build_real_preparer(max_llm_calls: int):
    import httpx2
    import truststore

    from buddy_host.llm.budget import BudgetedLlm
    from buddy_host.llm.claude_cli import ClaudeCliClient
    from buddy_host.narration.preparer import AreaPreparer
    from buddy_host.places.cache import JsonCache
    from buddy_host.places.fetch import RetryingHttp
    from buddy_host.places.overpass import OverpassClient
    from buddy_host.places.wikipedia import WikipediaClient
    from buddy_host.speech.engines import KittenSynthesizer, WhisperRecognizer
    from buddy_host.speech.pipeline import PipelineConfig, SpeechPipeline
    from buddy_host.speech.voice import load_reference

    truststore.inject_into_ssl()
    home = default_home()
    speech = SpeechPipeline(
        KittenSynthesizer(load_reference(home / "voice" / "F2")),
        WhisperRecognizer(home / "cache" / "whisper"),
        PipelineConfig(),
    )
    http = RetryingHttp(httpx2.AsyncClient(timeout=30))
    return AreaPreparer(
        OverpassClient(http, JsonCache(home / "cache" / "overpass", DAY)),
        WikipediaClient(http, JsonCache(home / "cache" / "wikipedia", 7 * DAY)),
        BudgetedLlm(ClaudeCliClient(ClaudeSettings.for_home(home)), max_calls=max_llm_calls),
        speech,
        persona_path=PERSONA,
        out_dir=home / "out" / "narrations",
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="buddy_host")
    parser.add_argument("--replay-dir", type=Path, help="重播這個資料夾裡的介紹，不呼叫 Claude")
    parser.add_argument(
        "--max-llm-calls", type=int, help="真實準備時 Claude 呼叫次數的上限（每次都耗額度）"
    )
    args = parser.parse_args()
    if args.replay_dir and args.max_llm_calls is not None:
        sys.exit("--replay-dir 與 --max-llm-calls 擇一")

    preparer = None
    if args.replay_dir:
        from buddy_host.tour.replay import ReplayPreparer

        preparer = ReplayPreparer(args.replay_dir)
    elif args.max_llm_calls is not None:
        preparer = build_real_preparer(args.max_llm_calls)

    config = load_config()
    home = default_home()
    app = create_app(
        config,
        preparer,
        usage_log_path=ClaudeSettings.for_home(home).usage_log_path,
        reports_dir=home / "out" / "reports",
    )
    uvicorn.run(app, host=config.listen_host, port=config.listen_port)


if __name__ == "__main__":
    main()
