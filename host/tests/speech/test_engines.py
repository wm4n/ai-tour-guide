import inspect
from types import SimpleNamespace

import pytest

from buddy_host.speech.engines import install_speed


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
