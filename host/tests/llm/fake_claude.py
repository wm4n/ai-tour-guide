"""假的 claude 可執行檔：記錄 argv／env／stdin，並依 FAKE_CLAUDE_MODE 輸出 stream-json。"""

import json
import os
import sys
import time

mode = os.environ.get("FAKE_CLAUDE_MODE", "success")
stdin_text = sys.stdin.read()

record_path = os.environ.get("FAKE_CLAUDE_RECORD")
if record_path:
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "argv": sys.argv[1:],
                "env": dict(os.environ),
                "stdin": stdin_text,
                "cwd": os.getcwd(),
            },
            f,
        )


def emit(obj):
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def delta(text):
    emit(
        {
            "type": "stream_event",
            "event": {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": text},
            },
        }
    )


MODEL_USAGE = {"claude-sonnet-5-5": {"inputTokens": 12, "outputTokens": 34, "costUSD": 0.001}}

if mode == "hang":
    time.sleep(60)
elif mode == "crash":
    sys.stderr.write("boom: " + os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "") + "\n")
    sys.exit(3)

if mode == "noisy":
    print("this is not json", flush=True)
    print("{broken", flush=True)

emit({"type": "system", "subtype": "init", "model": "claude-sonnet-5-5", "session_id": "s1"})
emit(
    {
        "type": "rate_limit_event",
        "rate_limit_info": {
            "status": "rejected" if mode == "quota" else "allowed",
            "resetsAt": 1760900000,
            "rateLimitType": "five_hour",
            "utilization": 0.42,
        },
    }
)

if mode == "quota":
    emit(
        {
            "type": "result",
            "subtype": "success",
            "is_error": True,
            "result": "You've hit your session limit · resets 5pm",
            "modelUsage": {},
            "duration_ms": 50,
            "session_id": "s1",
        }
    )
    sys.exit(1)

if mode == "fable":
    MODEL_USAGE = {"claude-fable-5-1": {"inputTokens": 1, "outputTokens": 1, "costUSD": 0.5}}

if mode == "no_partial":
    emit(
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "你好，這是完整回覆。"}]},
        }
    )
    reply = "你好，這是完整回覆。"
else:
    delta("你好，")
    delta("這是串流回覆。")
    emit(
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "你好，這是串流回覆。"}]},
        }
    )
    reply = "你好，這是串流回覆。"

emit(
    {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": reply,
        "modelUsage": MODEL_USAGE,
        "usage": {"input_tokens": 12, "output_tokens": 34},
        "total_cost_usd": 0.001,
        "duration_ms": 1234,
        "session_id": "s1",
    }
)
