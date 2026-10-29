"""參考聲音：從 ~/.buddy-host/voice/<名稱>/ 讀取，不入 git。

KittenTTS 2 必須同時給 reference_text。選填的 voice.toml 是這個聲音自己的語速與停頓設定，
以及 App 上顯示的名稱與描述；沒有這個檔的聲音一切照舊（原速、不壓停頓），但不會列在 App 上。
"""

import logging
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

WAV_NAME = "ref_24k.wav"
TEXT_NAME = "ref_text.txt"
SETTINGS_NAME = "voice.toml"
CURRENT_NAME = "current"  # voice/current：App 最後選的聲音，重啟時優先於 config.toml
SPEED_RANGE = (0.5, 2.0)

logger = logging.getLogger(__name__)


class VoiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReferenceVoice:
    wav_path: Path
    text: str
    name: str = ""
    # 語速倍率：在聲碼器之前把 mel 時間軸壓短（音高不變），介紹與問答都套用
    speed: float = 1.0
    # 回答問題時，超過這個長度的靜音縮到這個長度；None＝不壓（介紹永遠不壓）
    answer_max_pause_seconds: float | None = None

    @property
    def key(self) -> str:
        """聲音與語速；換了就代表同一份稿子要重新合成。"""
        return voice_key(self.name, self.speed)


def voice_key(name: str, speed: float) -> str:
    return f"{name}@{speed:g}"


@dataclass(frozen=True)
class VoiceSettings:
    """voice.toml 的內容。顯示名稱沒寫就是 None（用資料夾名）。"""

    speed: float = 1.0
    answer_max_pause_seconds: float | None = None
    display_name: str | None = None
    description: str = ""


@dataclass(frozen=True)
class VoiceProfile:
    """App 清單上的一個聲音。`name` 是資料夾名（切換用），`key` 含目前的語速。"""

    name: str
    display_name: str
    description: str
    key: str


def load_reference(voice_dir: Path) -> ReferenceVoice:
    if not voice_dir.is_dir():
        raise VoiceError(f"找不到參考聲音目錄：{voice_dir}")
    wav_path = voice_dir / WAV_NAME
    if not wav_path.is_file():
        raise VoiceError(f"參考聲音缺少 {WAV_NAME}：{voice_dir}")
    text_path = voice_dir / TEXT_NAME
    text = text_path.read_text(encoding="utf-8").strip() if text_path.is_file() else ""
    if not text:
        raise VoiceError(f"參考聲音缺少 reference_text（{TEXT_NAME}），KittenTTS 2 必須提供")
    settings = _load_settings(voice_dir / SETTINGS_NAME)
    return ReferenceVoice(
        wav_path, text, voice_dir.name, settings.speed, settings.answer_max_pause_seconds
    )


def list_voices(voices_dir: Path) -> list[VoiceProfile]:
    """只有放了 voice.toml 的資料夾才算正式聲音；其餘（篩選時留下的候選）不列出。

    每次都重讀硬碟，改了名稱、描述、語速不必重啟。某個 voice.toml 壞了（例如改到一半就存檔）
    只略過那一個聲音，其他照常列出。
    """
    if not voices_dir.is_dir():
        return []
    voices = []
    for folder in sorted(voices_dir.iterdir()):
        path = folder / SETTINGS_NAME
        if not path.is_file():
            continue
        try:
            settings = _load_settings(path)
        except VoiceError as error:
            logger.warning("略過聲音 %s：%s", folder.name, error)
            continue
        voices.append(
            VoiceProfile(
                name=folder.name,
                display_name=settings.display_name or folder.name,
                description=settings.description,
                key=voice_key(folder.name, settings.speed),
            )
        )
    return voices


def read_current_voice(home: Path, configured: str) -> str:
    """目前使用中的聲音：App 最後選的（voice/current），沒有才用 config.toml 的 voice。

    存的名稱不是 voice/ 底下的資料夾（被刪掉、檔案寫壞）就退回 config.toml，主機照樣起得來。
    """
    path = home / "voice" / CURRENT_NAME
    if not path.is_file():
        return configured
    name = path.read_text(encoding="utf-8").strip()
    if name in ("", ".", "..") or "/" in name or "\\" in name or not (path.parent / name).is_dir():
        logger.warning(
            "voice/current 記的 %r 不是可用的聲音，改用 config.toml 的 %s", name, configured
        )
        return configured
    return name


def save_current_voice(home: Path, name: str) -> None:
    """原子寫入：先寫同目錄的暫存檔再換上，寫到一半斷電也不會留下半個檔。"""
    path = home / "voice" / CURRENT_NAME
    temporary = path.with_name(f".{CURRENT_NAME}.tmp")
    temporary.write_text(f"{name}\n", encoding="utf-8")
    os.replace(temporary, path)


def _load_settings(path: Path) -> VoiceSettings:
    if not path.is_file():
        return VoiceSettings()
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise VoiceError(f"{path} 格式錯誤：{error}") from error
    unknown = set(raw) - {"speed", "answer_max_pause_seconds", "display_name", "description"}
    if unknown:
        raise VoiceError(f"{path} 有不認得的設定：{', '.join(sorted(unknown))}")

    speed = raw.get("speed", 1.0)
    low, high = SPEED_RANGE
    if not _is_number(speed) or not low <= speed <= high:
        raise VoiceError(f"{path} 的 speed 要是 {low}～{high} 之間的數字，收到 {speed!r}")

    max_pause = raw.get("answer_max_pause_seconds")
    if max_pause is not None and (not _is_number(max_pause) or max_pause <= 0):
        raise VoiceError(
            f"{path} 的 answer_max_pause_seconds 要是大於 0 的秒數，收到 {max_pause!r}"
        )

    display_name = raw.get("display_name")
    if display_name is not None and (not isinstance(display_name, str) or not display_name.strip()):
        raise VoiceError(f"{path} 的 display_name 要是非空的文字，收到 {display_name!r}")

    description = raw.get("description", "")
    if not isinstance(description, str):
        raise VoiceError(f"{path} 的 description 要是文字，收到 {description!r}")

    return VoiceSettings(
        float(speed),
        None if max_pause is None else float(max_pause),
        None if display_name is None else display_name.strip(),
        description.strip(),
    )


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)
