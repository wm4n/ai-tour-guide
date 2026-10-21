"""參考聲音：從 ~/.buddy-host/voice/<名稱>/ 讀取，不入 git。

KittenTTS 2 必須同時給 reference_text。選填的 voice.toml 是這個聲音自己的語速與停頓設定；
沒有這個檔的聲音一切照舊（原速、不壓停頓）。
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

WAV_NAME = "ref_24k.wav"
TEXT_NAME = "ref_text.txt"
SETTINGS_NAME = "voice.toml"
SPEED_RANGE = (0.5, 2.0)


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
        return f"{self.name}@{self.speed:g}"


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
    speed, max_pause = _load_settings(voice_dir / SETTINGS_NAME)
    return ReferenceVoice(wav_path, text, voice_dir.name, speed, max_pause)


def _load_settings(path: Path) -> tuple[float, float | None]:
    if not path.is_file():
        return 1.0, None
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise VoiceError(f"{path} 格式錯誤：{error}") from error
    unknown = set(raw) - {"speed", "answer_max_pause_seconds"}
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
    return float(speed), None if max_pause is None else float(max_pause)


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)
