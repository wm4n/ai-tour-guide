"""#3 的實測：冷啟動延遲、Claude 能否讀主機上的圖片、能否呼叫本機 MCP 工具。

會真的消耗 Claude Pro 額度，所以必須明確帶 --confirm-calls 4 才會執行（共 4 次 Haiku 呼叫）。
"""

import argparse
import asyncio
import json
import secrets
import struct
import sys
import time
import zlib
from pathlib import Path

from buddy_host.config import default_home
from buddy_host.llm.claude_cli import ClaudeCliClient, ClaudeSettings
from buddy_host.llm.models import LlmRequest, Purpose

PLANNED_CALLS = 4


def planned_calls(*, skip_first_cold: bool) -> int:
    return PLANNED_CALLS - 1 if skip_first_cold else PLANNED_CALLS


def make_solid_png(path: Path, rgb: tuple[int, int, int], size: int = 64) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    row = b"\x00" + bytes(rgb) * size
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(row * size))
        + chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


async def timed(client: ClaudeCliClient, request: LlmRequest) -> dict:
    first_text: list[float] = []
    started = time.perf_counter()

    def on_text(_: str) -> None:
        if not first_text:
            first_text.append(time.perf_counter() - started)

    result = await client.run(request, on_text=on_text)
    return {
        "text": result.text,
        "first_text_seconds": round(first_text[0], 2) if first_text else None,
        "total_seconds": round(time.perf_counter() - started, 2),
        "model": result.model,
        "rate_limit": result.rate_limit,
    }


async def run(home: Path, *, skip_first_cold: bool = False) -> dict:
    client = ClaudeCliClient(ClaudeSettings.for_home(home))
    probe_dir = home / "workdir" / "probe"
    image = probe_dir / "probe.png"
    make_solid_png(image, (220, 20, 20))
    nonce = f"NONCE-{secrets.token_hex(4)}"
    mcp_config = probe_dir / "mcp.json"
    mcp_config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "probe": {
                        "command": sys.executable,
                        "args": ["-m", "buddy_host.probe.mcp_server", "--nonce", nonce],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    report: dict = {}
    ping = LlmRequest(prompt="只回覆 OK 兩個字母。", purpose=Purpose.PROBE)
    if not skip_first_cold:
        report["cold_start_1"] = await timed(client, ping)
    report["cold_start_2"] = await timed(client, ping)

    report["image"] = await timed(
        client,
        LlmRequest(
            prompt=f"用 Read 工具讀取圖片 {image}，只用一個中文詞回答圖片的主要顏色。",
            purpose=Purpose.PROBE,
            allowed_tools=("Read",),
            add_dirs=(probe_dir,),
        ),
    )
    report["image"]["ok"] = "紅" in report["image"]["text"]

    report["mcp"] = await timed(
        client,
        LlmRequest(
            prompt="呼叫 probe_nonce 工具，把它回傳的暗號原樣回覆，不要加其他字。",
            purpose=Purpose.PROBE,
            mcp_config=mcp_config,
            allowed_tools=("mcp__probe__probe_nonce",),
        ),
    )
    report["mcp"]["ok"] = nonce in report["mcp"]["text"]
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-calls", type=int, required=True)
    parser.add_argument(
        "--skip-first-cold", action="store_true", help="第 1 次冷啟動已另外做過，少呼叫 1 次"
    )
    args = parser.parse_args()
    planned = planned_calls(skip_first_cold=args.skip_first_cold)
    if args.confirm_calls != planned:
        sys.exit(f"本探測會呼叫 Claude {planned} 次（Haiku），請以 --confirm-calls {planned} 確認")
    home = default_home()
    report = asyncio.run(run(home, skip_first_cold=args.skip_first_cold))
    out = home / "out" / "probe-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
