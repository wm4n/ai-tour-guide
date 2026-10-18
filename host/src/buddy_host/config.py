"""Buddy Host 設定：一律從 repo 外的 ~/.buddy-host/config.toml 讀取。"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LISTEN_HOST = "127.0.0.1"
DEFAULT_LISTEN_PORT = 8765
WILDCARD_HOSTS = {"0.0.0.0", "::", ""}


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class HostConfig:
    home: Path
    listen_host: str = DEFAULT_LISTEN_HOST
    listen_port: int = DEFAULT_LISTEN_PORT
    token: str | None = None


def default_home() -> Path:
    override = os.environ.get("BUDDY_HOST_HOME")
    return Path(override) if override else Path.home() / ".buddy-host"


def load_config(home: Path | None = None) -> HostConfig:
    home = home or default_home()
    path = home / "config.toml"
    raw = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    listen_host = raw.get("listen_host", DEFAULT_LISTEN_HOST)
    if listen_host in WILDCARD_HOSTS:
        raise ConfigError("listen_host 不可監聽所有介面，請填 Tailscale 位址或 127.0.0.1")

    token = raw.get("token")
    if token is not None and not token:
        raise ConfigError("token 不可為空字串；不需要驗證請直接移除這個欄位")

    return HostConfig(
        home=home,
        listen_host=listen_host,
        listen_port=int(raw.get("listen_port", DEFAULT_LISTEN_PORT)),
        token=token,
    )
