"""Buddy Host 設定：一律從 repo 外的 ~/.buddy-host/config.toml 讀取。"""

import ipaddress
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LISTEN_HOST = "127.0.0.1"
DEFAULT_LISTEN_PORT = 8765
DEFAULT_VOICE = "F2"
TAILSCALE_NETWORKS = (
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("fd7a:115c:a1e0::/48"),
)


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class HostConfig:
    home: Path
    listen_host: str = DEFAULT_LISTEN_HOST
    listen_port: int = DEFAULT_LISTEN_PORT
    token: str | None = None
    voice: str = DEFAULT_VOICE  # ~/.buddy-host/voice/ 底下的資料夾名稱


def default_home() -> Path:
    override = os.environ.get("BUDDY_HOST_HOME")
    return Path(override) if override else Path.home() / ".buddy-host"


def _is_allowed_listen_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or any(address in net for net in TAILSCALE_NETWORKS)


def load_config(home: Path | None = None) -> HostConfig:
    home = home or default_home()
    path = home / "config.toml"
    raw = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    listen_host = raw.get("listen_host", DEFAULT_LISTEN_HOST)
    if not _is_allowed_listen_host(listen_host):
        raise ConfigError(
            f"listen_host 只能是 127.0.0.1／localhost 或 Tailscale 位址"
            f"（100.64.0.0/10、fd7a:115c:a1e0::/48），收到 {listen_host!r}"
        )

    token = raw.get("token")
    if token is not None and not token:
        raise ConfigError("token 不可為空字串；不需要驗證請直接移除這個欄位")

    voice = raw.get("voice", DEFAULT_VOICE)
    if not isinstance(voice, str) or voice in ("", ".", "..") or "/" in voice or "\\" in voice:
        raise ConfigError(f"voice 要是 voice/ 底下的資料夾名稱，收到 {voice!r}")

    return HostConfig(
        home=home,
        listen_host=listen_host,
        listen_port=int(raw.get("listen_port", DEFAULT_LISTEN_PORT)),
        token=token,
        voice=voice,
    )
