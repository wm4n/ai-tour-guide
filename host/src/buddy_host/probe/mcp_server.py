"""探測用的最小 MCP stdio 伺服器（換行分隔的 JSON-RPC）：只有一個回傳暗號的工具。

用來實測 Claude Code 能否從 headless 模式呼叫主機上的本機 MCP 工具（#3），
之後 Google Places 工具（#12）走同樣的路。
"""

import argparse
import json
import sys

TOOL = {
    "name": "probe_nonce",
    "description": "回傳本次探測的暗號。要確認 MCP 工具可用時呼叫它。",
    "inputSchema": {"type": "object", "properties": {}},
}


def handle(message: dict, nonce: str) -> dict | None:
    method, msg_id = message.get("method"), message.get("id")
    if msg_id is None:  # notification
        return None
    if method == "initialize":
        version = message.get("params", {}).get("protocolVersion", "2024-11-05")
        result = {
            "protocolVersion": version,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "probe", "version": "0.1.0"},
        }
    elif method == "tools/list":
        result = {"tools": [TOOL]}
    elif method == "tools/call":
        result = {"content": [{"type": "text", "text": nonce}]}
    elif method == "ping":
        result = {}
    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"unknown method: {method}"},
        }
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nonce", required=True)
    args = parser.parse_args()
    for line in sys.stdin:
        if not line.strip():
            continue
        response = handle(json.loads(line), args.nonce)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
