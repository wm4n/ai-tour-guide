"""真正的合成／轉寫引擎。torch、kittenml、whisper 很重，只在需要時才 import。"""

from pathlib import Path

import numpy as np

from buddy_host.speech.preroll import WordTiming
from buddy_host.speech.voice import ReferenceVoice

WHISPER_SAMPLE_RATE = 16000
ASR_PROMPT = "以下是台灣中文的旅遊導覽。"


def install_speed(codec, speed: float) -> bool:
    """讓 KittenTTS 2 講快（或慢）一點：flow 產生 mel → 把時間軸線性插值成 1/speed 長 → 聲碼器。

    聲碼器從壓短的 mel 重新生成聲音，音高與音色不變（對成品做時間伸縮會有怪聲，已否決）。
    這是上游 CosyVoice 的語速做法；kittenml 的 s3gen 留了註解但沒接上，所以這裡換掉
    `codec.decode`，其餘照抄 `S3Codec.decode`（tests/speech/test_engines.py 會在 kittenml
    改版時提醒）。speed 是 1 時完全不動，聲音輸出與函式庫原本一模一樣。

    可以重複呼叫（換聲音時依新聲音的語速重設）：換成 1 會移除我們蓋在實例上的 decode，
    回到函式庫原本的方法；只認得自己裝的，不動別人蓋上去的。
    """
    if speed == 1.0:
        if getattr(vars(codec).get("decode"), "is_speed_patch", False):
            del codec.decode
        return False
    if codec.student is not None:
        raise RuntimeError("語速調整不支援量化的 student 解碼器（decoder='default' 才能用）")

    def decode(ref_conditioning, audio_ids):
        import torch
        import torch.nn.functional as F
        from kittenml.kittentts2.s3gen import S3GEN_SIL, SPEECH_VOCAB_SIZE
        from kittenml.kittentts2.vocoder import CFM_TIMESTEPS

        valid = [t for t in audio_ids if 0 <= t < SPEECH_VOCAB_SIZE]
        if not valid:
            return None
        s3gen = codec.s3gen
        # 和函式庫一樣補 3 個靜音 token：s3gen 會把最後幾個 token 當串流的預看丟掉
        tokens = torch.tensor(valid + [int(S3GEN_SIL)] * 3, dtype=torch.long, device=codec.device)
        with torch.inference_mode():
            mel = s3gen.flow_inference(
                tokens, ref_dict=ref_conditioning, n_cfm_timesteps=CFM_TIMESTEPS, finalize=True
            ).to(dtype=s3gen.dtype)
            frames = max(1, round(mel.shape[-1] / speed))
            mel = F.interpolate(mel, size=frames, mode="linear", align_corners=False)
            wav, _ = s3gen.hift_inference(mel, None)
            wav = wav.clone()
            wav[:, : len(s3gen.trim_fade)] *= s3gen.trim_fade  # 函式庫的淡入：避免參考聲音溢出
        return wav.squeeze().detach().cpu().float().numpy()

    decode.is_speed_patch = True
    codec.decode = decode
    return True


class KittenSynthesizer:
    def __init__(self, voice: ReferenceVoice, device: str = "mps"):
        from kittenml import KittenTTS

        self._tts = KittenTTS(
            "KittenML/kitten-tts-2", device=device, weights="packed", decoder="default"
        )
        self._voice = voice
        self.sample_rate: int = self._tts.sample_rate
        install_speed(self._tts.codec, voice.speed)

    def use_voice(self, voice: ReferenceVoice) -> None:
        """換聲音：不必重載模型，參考音檔與逐字稿本來就是每次 generate() 傳入。
        呼叫端（`SpeechScheduler`）保證只在合成單位之間呼叫。"""
        install_speed(self._tts.codec, voice.speed)
        self._voice = voice

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

    def transcribe_words(self, audio: np.ndarray, sample_rate: int) -> tuple[str, list[WordTiming]]:
        from math import gcd

        from scipy.signal import resample_poly

        divisor = gcd(sample_rate, WHISPER_SAMPLE_RATE)
        mono = resample_poly(audio, WHISPER_SAMPLE_RATE // divisor, sample_rate // divisor)
        result = self._model.transcribe(
            mono.astype(np.float32),
            language="zh",
            fp16=False,
            initial_prompt=ASR_PROMPT,
            word_timestamps=True,
        )
        words = [
            WordTiming(w["word"].strip(), float(w["start"]), float(w["end"]))
            for segment in result["segments"]
            for w in segment.get("words", [])
        ]
        return result["text"], words
