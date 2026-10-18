"""為一個座標準備介紹（真的呼叫 Claude Code 與 KittenTTS）。

會消耗 Claude Pro 額度：每個景點一次 Sonnet 呼叫，所以必須帶 --confirm-llm-calls 確認次數。
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import httpx2
import truststore

from buddy_host.config import default_home
from buddy_host.llm.claude_cli import ClaudeCliClient, ClaudeSettings
from buddy_host.narration.memory import PeakMemorySampler
from buddy_host.narration.preparer import AreaPreparer
from buddy_host.places.cache import JsonCache
from buddy_host.places.fetch import RetryingHttp
from buddy_host.places.models import Location
from buddy_host.places.overpass import OverpassClient
from buddy_host.places.wikipedia import WikipediaClient
from buddy_host.speech.pipeline import PipelineConfig, SpeechPipeline
from buddy_host.speech.voice import load_reference

DAY = 24 * 3600
PERSONA = Path(__file__).resolve().parents[3] / "config" / "buddy.md"


async def run(args: argparse.Namespace) -> dict:
    truststore.inject_into_ssl()
    home = default_home()

    from buddy_host.speech.engines import KittenSynthesizer, WhisperRecognizer

    t0 = time.perf_counter()
    synth = KittenSynthesizer(load_reference(home / "voice" / "F2"))
    asr = WhisperRecognizer(home / "cache" / "whisper")
    load_seconds = time.perf_counter() - t0
    speech = SpeechPipeline(synth, asr, PipelineConfig())

    async with httpx2.AsyncClient(timeout=30) as client:
        http = RetryingHttp(client)
        preparer = AreaPreparer(
            OverpassClient(http, JsonCache(home / "cache" / "overpass", DAY)),
            WikipediaClient(http, JsonCache(home / "cache" / "wikipedia", 7 * DAY)),
            ClaudeCliClient(ClaudeSettings.for_home(home)),
            speech,
            persona_path=PERSONA,
            out_dir=home / "out" / "narrations",
            limit=args.limit,
        )
        started = time.perf_counter()
        with PeakMemorySampler() as memory:
            prepared = await preparer.prepare(Location(args.lat, args.lon, args.heading))
        elapsed = time.perf_counter() - started

    return {
        "model_load_seconds": round(load_seconds, 1),
        "prepare_seconds": round(elapsed, 1),
        "memory": asdict(memory.report()),
        "narrations": [
            {"name": p.name, "audio_seconds": p.audio_seconds, "wav": str(p.wav_path),
             "script": p.script}
            for p in prepared
        ],
    }  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--heading", type=float, default=None)
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--confirm-llm-calls", type=int, required=True)
    args = parser.parse_args()
    if args.confirm_llm_calls != args.limit:
        sys.exit(
            f"本次最多會呼叫 Claude Sonnet {args.limit} 次（每個景點一次），"
            f"請以 --confirm-llm-calls {args.limit} 確認"
        )
    report = asyncio.run(run(args))
    out = default_home() / "out" / "prepare-report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
