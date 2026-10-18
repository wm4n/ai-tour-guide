"""真正的合成／轉寫引擎。torch、kittenml、whisper 很重，只在需要時才 import。"""

from pathlib import Path

import numpy as np

from buddy_host.speech.voice import ReferenceVoice

WHISPER_SAMPLE_RATE = 16000
ASR_PROMPT = "以下是台灣中文的旅遊導覽。"


class KittenSynthesizer:
    def __init__(self, voice: ReferenceVoice, device: str = "mps"):
        from kittenml import KittenTTS

        self._tts = KittenTTS(
            "KittenML/kitten-tts-2", device=device, weights="packed", decoder="default"
        )
        self._voice = voice
        self.sample_rate: int = self._tts.sample_rate

    def synthesize(self, text: str, seed: int) -> np.ndarray:
        wav = self._tts.generate(
            text,
            reference=str(self._voice.wav_path),
            reference_text=self._voice.text,
            normalize=False,  # 數字、假名都已在前處理處理掉
            advanced={"seed": seed},
        )
        return np.asarray(wav, dtype=np.float32)


class WhisperRecognizer:
    def __init__(self, cache_dir: Path, model: str = "small"):
        import truststore
        import whisper

        # whisper 用 urllib 下載權重；python.org 版 Python 不認系統憑證，改用系統信任庫
        truststore.inject_into_ssl()
        self._whisper = whisper
        self._model = whisper.load_model(model, download_root=str(cache_dir), device="cpu")

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        from math import gcd

        from scipy.signal import resample_poly

        divisor = gcd(sample_rate, WHISPER_SAMPLE_RATE)
        mono = resample_poly(audio, WHISPER_SAMPLE_RATE // divisor, sample_rate // divisor)
        result = self._model.transcribe(
            mono.astype(np.float32), language="zh", fp16=False, initial_prompt=ASR_PROMPT
        )
        return result["text"]
