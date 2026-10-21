from pathlib import Path

import pytest

from buddy_host.config import ConfigError, default_home, load_config


def write_config(home: Path, body: str) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.toml").write_text(body, encoding="utf-8")


def test_loads_values_from_config_file(tmp_path: Path):
    write_config(tmp_path, 'listen_host = "100.64.0.1"\nlisten_port = 9000\ntoken = "s3cret"\n')

    config = load_config(tmp_path)

    assert config.listen_host == "100.64.0.1"
    assert config.listen_port == 9000
    assert config.token == "s3cret"
    assert config.home == tmp_path


def test_missing_file_falls_back_to_safe_defaults(tmp_path: Path):
    config = load_config(tmp_path)

    assert config.listen_host == "127.0.0.1"
    assert config.listen_port == 8765
    assert config.token is None


def test_empty_token_is_rejected(tmp_path: Path):
    write_config(tmp_path, 'token = ""\n')

    with pytest.raises(ConfigError, match="token"):
        load_config(tmp_path)


def test_wildcard_listen_host_is_rejected(tmp_path: Path):
    # 設計文件：Buddy Host 只聽 Tailscale 介面，絕不監聽所有介面
    write_config(tmp_path, 'listen_host = "0.0.0.0"\n')

    with pytest.raises(ConfigError, match="listen_host"):
        load_config(tmp_path)


def test_default_home_honours_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("BUDDY_HOST_HOME", str(tmp_path))

    assert default_home() == tmp_path


def test_default_home_is_dot_buddy_host(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("BUDDY_HOST_HOME", raising=False)

    assert default_home() == Path.home() / ".buddy-host"


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "::1",
        "localhost",
        "100.64.0.1",
        "100.100.100.100",
        "100.127.255.254",
        "fd7a:115c:a1e0::1",
    ],
)
def test_tailscale_and_loopback_listen_hosts_are_accepted(tmp_path: Path, host: str):
    write_config(tmp_path, f'listen_host = "{host}"\n')

    assert load_config(tmp_path).listen_host == host


@pytest.mark.parametrize(
    "host", ["192.168.1.5", "10.0.0.2", "100.128.0.1", "8.8.8.8", "mac.example.com"]
)
def test_other_interfaces_are_rejected(tmp_path: Path, host: str):
    write_config(tmp_path, f'listen_host = "{host}"\n')

    with pytest.raises(ConfigError, match="Tailscale"):
        load_config(tmp_path)


def test_voice_defaults_to_the_original_reference_voice(tmp_path: Path):
    assert load_config(tmp_path).voice == "F2"


def test_voice_picks_a_folder_under_the_voice_directory(tmp_path: Path):
    write_config(tmp_path, 'voice = "M1"\n')

    assert load_config(tmp_path).voice == "M1"


@pytest.mark.parametrize("voice", ["", "../M1", "a/b", ".", 3])
def test_voice_must_be_a_plain_folder_name(tmp_path: Path, voice):
    write_config(tmp_path, f"voice = {voice!r}\n".replace("'", '"'))

    with pytest.raises(ConfigError, match="voice"):
        load_config(tmp_path)
