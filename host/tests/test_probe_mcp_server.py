import json
import subprocess
import sys


def rpc(proc: subprocess.Popen, payload: dict) -> dict:
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())


def test_initialize_list_and_call_roundtrip():
    proc = subprocess.Popen(
        [sys.executable, "-m", "buddy_host.probe.mcp_server", "--nonce", "N-123"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        init = rpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26"},
            },
        )
        assert init["result"]["protocolVersion"] == "2025-03-26"
        assert "tools" in init["result"]["capabilities"]

        proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )

        tools = rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert [t["name"] for t in tools["result"]["tools"]] == ["probe_nonce"]

        call = rpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "probe_nonce", "arguments": {}},
            },
        )
        assert call["result"]["content"][0]["text"] == "N-123"

        unknown = rpc(proc, {"jsonrpc": "2.0", "id": 4, "method": "nope"})
        assert unknown["error"]["code"] == -32601
    finally:
        proc.kill()


def test_solid_png_is_a_valid_png(tmp_path):
    import struct
    import zlib

    from buddy_host.probe.run_probe import make_solid_png

    path = tmp_path / "x.png"
    make_solid_png(path, (220, 20, 20), size=4)

    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", data[16:24])
    assert (width, height) == (4, 4)
    idat_start = data.index(b"IDAT") + 4
    idat_len = struct.unpack(">I", data[idat_start - 8 : idat_start - 4])[0]
    raw = zlib.decompress(data[idat_start : idat_start + idat_len])
    assert raw[:4] == b"\x00\xdc\x14\x14"


def test_planned_calls_shrink_when_the_first_cold_start_was_already_done():
    from buddy_host.probe.run_probe import planned_calls

    assert planned_calls(skip_first_cold=False) == 4
    assert planned_calls(skip_first_cold=True) == 3
