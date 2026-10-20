"""參考聲音：從 ~/.buddy-host/voice/<名稱>/ 讀取，不入 git。

KittenTTS 2 必須同時給 reference_text。
"""

from dataclasses import dataclass
from pathlib import Path

WAV_NAME = "ref_24k.wav"
TEXT_NAME = "ref_text.txt"


class VoiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReferenceVoice:
    wav_path: Path
    text: str


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
    return ReferenceVoice(wav_path, text)
