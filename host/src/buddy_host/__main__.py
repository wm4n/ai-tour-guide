"""啟動 Buddy Host。

介紹準備器有兩種，都要明確指定，沒指定時旅程端點回 503：
- `--replay-dir`：重播先前做好的介紹，不呼叫 Claude，用來在桌上跑通 App 流程；
  問答也開放，但答案是固定的假答案（`qa.replay`）、語音是提示音。
- `--max-llm-calls N`：真的寫稿與合成，同時開放問答。每次呼叫都消耗 Claude Pro 額度，
  寫稿與問答共用這 N 次，用完就停止準備、問答回報 `llm_budget`。
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
QA_LATENCY_LOG = "qa-latency.jsonl"


def build_real_services(max_llm_calls: int):
    """回傳（介紹準備器, 問答服務的工廠）；兩邊共用同一個有上限的 Claude 客戶端。"""
    import httpx2
    import truststore

    from buddy_host.llm.budget import BudgetedLlm
    from buddy_host.llm.claude_cli import ClaudeCliClient
    from buddy_host.llm.usage_log import UsageLog
    from buddy_host.narration.preparer import AreaPreparer
    from buddy_host.places.cache import JsonCache
    from buddy_host.places.fetch import RetryingHttp
    from buddy_host.places.overpass import OverpassClient
    from buddy_host.places.wikipedia import WikipediaClient
    from buddy_host.qa.service import QaService
    from buddy_host.speech.engines import KittenSynthesizer, WhisperRecognizer
    from buddy_host.speech.pipeline import PipelineConfig, SpeechPipeline
    from buddy_host.speech.scheduler import SpeechScheduler
    from buddy_host.speech.voice import load_reference

    truststore.inject_into_ssl()
    home = default_home()
    # 介紹與問答共用同一顆 GPU 與同一組模型：問答優先，介紹在合成單位之間讓路
    speech = SpeechScheduler(
        SpeechPipeline(
            KittenSynthesizer(load_reference(home / "voice" / "F2")),
            WhisperRecognizer(home / "cache" / "whisper"),
            PipelineConfig(),
        )
    )
    http = RetryingHttp(httpx2.AsyncClient(timeout=30))
    llm = BudgetedLlm(ClaudeCliClient(ClaudeSettings.for_home(home)), max_calls=max_llm_calls)
    preparer = AreaPreparer(
        OverpassClient(http, JsonCache(home / "cache" / "overpass", DAY)),
        WikipediaClient(http, JsonCache(home / "cache" / "wikipedia", 7 * DAY)),
        llm,
        speech.narration,
        persona_path=PERSONA,
        out_dir=home / "out" / "narrations",
    )

    def answerer(quota, journey):
        return QaService(
            llm,
            preparer,
            speech.answers,
            persona_path=PERSONA,
            out_dir=home / "out" / "answers",
            quota=quota,
            journey=journey,
            latency_log=UsageLog(home / QA_LATENCY_LOG),
        )

    return preparer, answerer


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
    answerer = None
    if args.replay_dir:
        from buddy_host.qa.replay import CannedLlm, NoNearby, ToneSpeech
        from buddy_host.qa.service import QaService
        from buddy_host.tour.replay import ReplayPreparer

        preparer = ReplayPreparer(args.replay_dir)

        def answerer(quota, journey):
            return QaService(
                CannedLlm(),
                NoNearby(),
                ToneSpeech(),
                persona_path=PERSONA,
                out_dir=default_home() / "out" / "answers-replay",
                quota=quota,
                journey=journey,
            )

    elif args.max_llm_calls is not None:
        preparer, answerer = build_real_services(args.max_llm_calls)

    config = load_config()
    home = default_home()
    app = create_app(
        config,
        preparer,
        usage_log_path=ClaudeSettings.for_home(home).usage_log_path,
        reports_dir=home / "out" / "reports",
        qa_latency_log_path=home / QA_LATENCY_LOG,
        # 重播模式只在桌上跑通流程，不寫進真實的「講過哪些地方」
        journey_path=None if args.replay_dir else home / "journey.json",
        answerer_factory=answerer,
    )
    uvicorn.run(app, host=config.listen_host, port=config.listen_port)


if __name__ == "__main__":
    main()
