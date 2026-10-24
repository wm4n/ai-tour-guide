import inspect
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from buddy_host.speech.engines import KittenSynthesizer, install_speed
from buddy_host.speech.voice import ReferenceVoice


def test_original_speed_leaves_the_library_decoder_untouched():
    library_decode = object()
    codec = SimpleNamespace(decode=library_decode, student=None)

    assert install_speed(codec, 1.0) is False
    assert codec.decode is library_decode


def test_quantised_student_decoder_is_not_supported():
    codec = SimpleNamespace(decode=object(), student=object())

    with pytest.raises(RuntimeError, match="student"):
        install_speed(codec, 1.2)


class FakeS3Gen:
    """flow 產生 mel（每個 token 兩格）、聲碼器每格 mel 出 10 個取樣，記下收到什麼。"""

    def __init__(self, torch):
        self.torch = torch
        self.dtype = torch.float32
        self.trim_fade = torch.zeros(4)
        self.flow_kwargs = None
        self.mel_frames = None

    def flow_inference(self, speech_tokens, **kwargs):
        self.flow_kwargs = kwargs
        return self.torch.ones(1, 80, speech_tokens.shape[-1] * 2)

    def hift_inference(self, speech_feat, cache_source=None):
        self.mel_frames = speech_feat.shape[-1]
        return self.torch.ones(1, speech_feat.shape[-1] * 10), None


def test_faster_voice_shortens_the_mel_before_the_vocoder():
    torch = pytest.importorskip("torch")
    s3gen = FakeS3Gen(torch)
    codec = SimpleNamespace(decode=None, student=None, s3gen=s3gen, device="cpu")

    install_speed(codec, 1.2)
    wav = codec.decode({"ref": 1}, [5] * 57)

    tokens = 57 + 3  # 函式庫補 3 個靜音 token 保住最後一個音節，這裡也要補
    assert s3gen.mel_frames == round(tokens * 2 / 1.2)
    assert len(wav) == s3gen.mel_frames * 10
    assert s3gen.flow_kwargs["ref_dict"] == {"ref": 1}
    assert s3gen.flow_kwargs["finalize"] is True
    assert wav[0] == 0  # 開頭照函式庫的做法淡入，避免參考聲音溢出


def test_out_of_range_tokens_are_dropped_and_nothing_left_gives_no_audio():
    torch = pytest.importorskip("torch")
    codec = SimpleNamespace(decode=None, student=None, s3gen=FakeS3Gen(torch), device="cpu")

    install_speed(codec, 1.2)

    assert codec.decode({}, [-1, 10**6]) is None


def test_the_kittenml_internals_we_rely_on_are_still_there():
    """升級 kittenml 後這裡失敗，代表語速解碼要跟著檢查（我們複製了 S3Codec.decode 的做法）。"""
    vocoder = pytest.importorskip("kittenml.kittentts2.vocoder")
    s3gen = pytest.importorskip("kittenml.kittentts2.s3gen")

    decode_source = inspect.getsource(vocoder.S3Codec.decode)
    assert "S3GEN_SIL" in decode_source and "(3,)" in decode_source
    assert "s3gen.inference" in decode_source
    flow = inspect.signature(s3gen.S3Token2Wav.flow_inference).parameters
    assert {"speech_tokens", "ref_dict", "n_cfm_timesteps", "finalize"} <= set(flow)
    hift = inspect.signature(s3gen.S3Token2Wav.hift_inference).parameters
    assert {"speech_feat", "cache_source"} <= set(hift)
    assert "trim_fade" in inspect.getsource(s3gen.S3Token2Wav.__init__)
    assert vocoder.CFM_TIMESTEPS == 2


class LibraryCodec:
    """函式庫的 S3Codec：decode 是類別上的方法，語速調整把它蓋在實例上。"""

    student = None

    def __init__(self):
        self.s3gen = None
        self.device = "cpu"

    def decode(self, ref_conditioning, audio_ids):
        return "library"


def test_switching_back_to_original_speed_restores_the_library_decoder():
    codec = LibraryCodec()

    assert install_speed(codec, 1.2) is True
    assert "decode" in vars(codec)
    assert install_speed(codec, 1.0) is False

    assert "decode" not in vars(codec)
    assert codec.decode(None, []) == "library"


def test_speed_can_go_1_2_then_1_0_then_1_2_again():
    codec = LibraryCodec()

    install_speed(codec, 1.2)
    first = codec.decode
    install_speed(codec, 1.0)
    install_speed(codec, 1.2)

    assert "decode" in vars(codec)
    assert codec.decode is not first  # 重新裝一份，不殘留舊的
    assert codec.decode is not LibraryCodec.decode


def test_resetting_to_original_speed_only_removes_our_own_decoder():
    foreign = object()
    codec = SimpleNamespace(decode=foreign, student=None)

    install_speed(codec, 1.0)

    assert codec.decode is foreign


def test_changing_speed_replaces_the_previous_speed_up():
    torch = pytest.importorskip("torch")
    s3gen = FakeS3Gen(torch)
    codec = SimpleNamespace(student=None, s3gen=s3gen, device="cpu")

    install_speed(codec, 1.2)
    install_speed(codec, 2.0)
    codec.decode({}, [5] * 57)

    assert s3gen.mel_frames == round((57 + 3) * 2 / 2.0)


class FakeTts:
    sample_rate = 24000

    def __init__(self):
        self.codec = LibraryCodec()
        self.calls: list[dict] = []

    def generate(self, text, **kwargs):
        self.calls.append(kwargs)
        return [0.0, 0.1]


def make_synthesizer(voice):
    """不載入真正的 KittenTTS：只測「換聲音」這層，所以繞過建構子。"""
    synth = object.__new__(KittenSynthesizer)
    synth._tts = FakeTts()
    synth._voice = voice
    synth.sample_rate = 24000
    install_speed(synth._tts.codec, voice.speed)
    return synth


def reference(name, speed=1.0):
    return ReferenceVoice(Path(f"/voices/{name}/ref_24k.wav"), f"{name}的參考逐字稿", name, speed)


def test_the_next_synthesis_uses_the_new_reference_voice():
    synth = make_synthesizer(reference("F2"))

    synth.synthesize("你好。", seed=1)
    synth.use_voice(reference("M1"))
    audio = synth.synthesize("你好。", seed=1)

    first, second = synth._tts.calls
    assert first["reference"].endswith("F2/ref_24k.wav")
    assert first["reference_text"] == "F2的參考逐字稿"
    assert second["reference"].endswith("M1/ref_24k.wav")
    assert second["reference_text"] == "M1的參考逐字稿"
    assert audio.dtype == np.float32


def test_switching_voice_resets_speed_to_the_new_voice():
    synth = make_synthesizer(reference("F2", speed=1.2))
    sped_up = synth._tts.codec.decode

    synth.use_voice(reference("M1", speed=1.0))
    assert "decode" not in vars(synth._tts.codec)  # 原速的聲音不留舊的加速

    synth.use_voice(reference("F2", speed=1.2))
    assert synth._tts.codec.decode is not sped_up
    assert "decode" in vars(synth._tts.codec)
