import json
import wave
from pathlib import Path

import numpy as np

from buddy_host.speech.pipeline import PipelineConfig, SpeechPipeline, write_outputs

SR = 1000


class FakeSynth:
    """音訊長度正比於字數，數值等於 seed，方便從輸出反推用了哪個 seed。"""

    sample_rate = SR

    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def synthesize(self, text: str, seed: int) -> np.ndarray:
        self.calls.append((text, seed))
        return np.full(len(text) * 10, seed / 10000, dtype=np.float32)


class ScriptedRecognizer:
    """依「最後一次合成的 (text, seed)」回傳預先寫好的轉寫；沒寫的視為完全正確。"""

    def __init__(self, synth: FakeSynth, wrong: dict[tuple[str, int], str] | None = None):
        self.synth = synth
        self.wrong = wrong or {}

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        text, seed = self.synth.calls[-1]
        return self.wrong.get((text, seed), text)


def make(wrong=None, **config):
    synth = FakeSynth()
    pipeline = SpeechPipeline(synth, ScriptedRecognizer(synth, wrong), PipelineConfig(**config))
    return pipeline, synth


def test_first_seed_passes_with_a_single_attempt():
    pipeline, synth = make()

    result = pipeline.run("大稻埕是老街。")

    assert synth.calls == [("大稻埕是老街。", 1234)]
    [chunk] = result.chunks
    assert chunk.status == "ok"
    assert [a.seed for a in chunk.attempts] == [1234]
    assert chunk.attempts[0].cer == 0.0


def test_failed_seed_is_retried_with_the_next_seed_and_all_attempts_are_logged():
    pipeline, synth = make(wrong={("大稻埕是老街。", 1234): "完全不一樣的話"})

    result = pipeline.run("大稻埕是老街。")

    [chunk] = result.chunks
    assert chunk.status == "ok"
    assert [a.seed for a in chunk.attempts] == [1234, 7]
    assert chunk.attempts[0].cer > 0.5
    assert chunk.attempts[0].hypothesis == "完全不一樣的話"
    assert np.allclose(result.audio, 7 / 10000)


def test_seeds_and_threshold_are_configurable():
    text = "大稻埕是老街。"
    pipeline, synth = make(
        wrong={(text, 1): "大稻埕是老家"},  # 1 個錯字，CER 約 0.17
        seeds=(1, 2),
        cer_threshold=0.1,
    )

    result = pipeline.run(text)

    assert [a.seed for a in result.chunks[0].attempts] == [1, 2]


def test_all_seeds_failing_then_split_at_commas_and_pieces_pass():
    text = "走進老街，看見紅磚樓。"
    wrong = {(text, s): "亂七八糟" for s in (1234, 7, 42, 2026)}
    pipeline, synth = make(wrong=wrong)

    result = pipeline.run(text)

    [chunk] = result.chunks
    assert chunk.status == "split"
    assert [p.text for p in chunk.pieces] == ["走進老街，", "看見紅磚樓。"]
    assert all(p.status == "ok" for p in chunk.pieces)
    assert len(result.audio) == len("走進老街，") * 10 + len("看見紅磚樓。") * 10


def test_split_piece_that_still_fails_skips_the_whole_sentence():
    text = "走進老街，看見紅磚樓。"
    wrong = {(text, s): "亂" for s in (1234, 7, 42, 2026)}
    wrong.update({("看見紅磚樓。", s): "亂" for s in (1234, 7, 42, 2026)})
    pipeline, _ = make(wrong=wrong)

    result = pipeline.run(text)

    [chunk] = result.chunks
    assert chunk.status == "skipped"
    assert len(result.audio) == 0


def test_sentence_without_commas_is_skipped_after_all_seeds_fail():
    text = "大稻埕是老街。"
    pipeline, synth = make(wrong={(text, s): "亂" for s in (1234, 7, 42, 2026)})

    result = pipeline.run(text)

    assert result.chunks[0].status == "skipped"
    assert result.chunks[0].pieces == []
    assert len(synth.calls) == 4


def test_splitting_can_be_disabled():
    text = "走進老街，看見紅磚樓。"
    pipeline, synth = make(
        wrong={(text, s): "亂" for s in (1234, 7, 42, 2026)}, split_on_failure=False
    )

    result = pipeline.run(text)

    assert result.chunks[0].status == "skipped"
    assert len(synth.calls) == 4


def test_numbers_and_kana_are_prepared_before_synthesis():
    pipeline, synth = make()

    pipeline.run("2004年開始，長200公尺「なばなの里」。")

    assert synth.calls[0][0] == "二零零四年開始，長兩百公尺。"


def test_sentences_are_joined_by_a_gap_without_trailing_silence():
    pipeline, _ = make(gap_seconds=0.5, chunk_chars=4)

    result = pipeline.run("甲乙丙。丁戊己。")

    assert len(result.audio) == 4 * 10 + 500 + 4 * 10


def test_skipped_sentence_leaves_no_audio_and_no_extra_gap():
    text = "丁戊己。"
    pipeline, _ = make(
        wrong={(text, s): "亂" for s in (1234, 7, 42, 2026)}, gap_seconds=0.5, chunk_chars=4
    )

    result = pipeline.run("甲乙丙。丁戊己。庚辛壬。")

    assert [s.status for s in result.chunks] == ["ok", "skipped", "ok"]
    assert len(result.audio) == 4 * 10 + 500 + 4 * 10


def test_empty_text_gives_empty_audio():
    pipeline, synth = make()

    result = pipeline.run("   ")

    assert len(result.audio) == 0
    assert result.chunks == []
    assert synth.calls == []


def test_log_is_json_serialisable_and_has_seed_cer_per_attempt():
    pipeline, _ = make(wrong={("大稻埕是老街。", 1234): "亂"})

    result = pipeline.run("大稻埕是老街。")
    log = json.loads(json.dumps(result.to_log(), ensure_ascii=False))

    attempts = log["chunks"][0]["attempts"]
    assert [(a["seed"]) for a in attempts] == [1234, 7]
    assert all("cer" in a and "synth_seconds" in a and "check_seconds" in a for a in attempts)
    assert log["audio_seconds"] > 0
    assert "rtf" in log


def test_write_outputs_makes_a_playable_wav_and_a_report(tmp_path: Path):
    pipeline, _ = make()
    result = pipeline.run("大稻埕是老街。")

    wav_path, log_path = write_outputs(result, tmp_path, "demo")

    with wave.open(str(wav_path)) as wav:
        assert wav.getframerate() == SR
        assert wav.getnchannels() == 1
        assert wav.getnframes() == len(result.audio)
    assert json.loads(log_path.read_text(encoding="utf-8"))["chunks"]


def test_progress_callback_is_called_once_per_sentence_with_position():
    synth = FakeSynth()
    seen: list[tuple[int, int, str, str]] = []
    pipeline = SpeechPipeline(
        synth,
        ScriptedRecognizer(synth),
        PipelineConfig(chunk_chars=4),
        progress=lambda i, total, s: seen.append((i, total, s.text, s.status)),
    )

    pipeline.run("甲乙丙。丁戊己。")

    assert seen == [(1, 2, "甲乙丙。", "ok"), (2, 2, "丁戊己。", "ok")]


def test_adjacent_sentences_are_merged_into_one_chunk_before_synthesis():
    pipeline, synth = make()

    pipeline.run("哇！這是老街。")

    assert synth.calls == [("哇！這是老街。", 1234)]


def test_failing_chunk_is_split_into_sentences_and_only_the_failing_sentence_is_lost():
    bad = "乙乙乙乙。"
    chunk_text = "甲甲甲甲。" + bad
    wrong = {(chunk_text, s): "亂" for s in (1234, 7, 42, 2026)}
    wrong.update({(bad, s): "亂" for s in (1234, 7, 42, 2026)})
    pipeline, _ = make(wrong=wrong, gap_seconds=0)

    result = pipeline.run(chunk_text)

    [chunk] = result.chunks
    assert chunk.status == "split"
    assert [p.status for p in chunk.pieces] == ["ok", "skipped"]
    assert len(result.audio) == len("甲甲甲甲。") * 10


def test_chunk_whose_sentences_all_fail_is_skipped():
    chunk_text = "甲甲甲甲。乙乙乙乙。"
    wrong = {
        (t, s): "亂" for t in (chunk_text, "甲甲甲甲。", "乙乙乙乙。") for s in (1234, 7, 42, 2026)
    }
    pipeline, _ = make(wrong=wrong)

    result = pipeline.run(chunk_text)

    assert result.chunks[0].status == "skipped"
    assert len(result.audio) == 0
