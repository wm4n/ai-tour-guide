from pathlib import Path

import pytest

from buddy_host import __main__ as entry

# App 端 dart:io HttpClient 的 idleTimeout 預設值
APP_IDLE_TIMEOUT_SECONDS = 15


def test_idle_connections_stay_open_longer_than_the_app_keeps_them(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """主機比 App 先關閒置連線的話，App 每 5 秒的輪詢會拿到剛被關掉的連線
    （Connection closed before full header was received），畫面在「已連線／未連線」間跳。"""
    monkeypatch.setenv("BUDDY_HOST_HOME", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["buddy_host"])
    started = {}
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **options: started.update(options))

    entry.main()

    assert started["timeout_keep_alive"] > APP_IDLE_TIMEOUT_SECONDS
