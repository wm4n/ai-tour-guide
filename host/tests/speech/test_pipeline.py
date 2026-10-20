import contextlib
import json
import wave
from pathlib import Path

import numpy as np
import pytest

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
    config.setdefault("opening_extra_seeds", ())  # 既有測試不涉及「開場句多試 seed」
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


# ---- 句首檢查與短句門檻（#5 的實測回饋）----

from buddy_host.speech.preroll import WordTiming  # noqa: E402


class FixedSynth:
    """固定 2 秒、值等於 seed 的音訊（sr=1000），方便驗證裁切長度。"""

    sample_rate = SR

    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def synthesize(self, text: str, seed: int) -> np.ndarray:
        self.calls.append((text, seed))
        return np.full(2000, seed / 10000, dtype=np.float32)


class WordsRecognizer:
    """依音訊長度決定第一個詞的起始秒數：完整 2 秒的音訊有 lead 秒的前導，裁過就是 0。"""

    def __init__(self, synth, lead=0.9, text_for=None, first_word=None):
        self.synth, self.lead, self.text_for, self.first_word = (
            synth,
            lead,
            text_for or {},
            first_word,
        )
        self.calls = 0

    def transcribe(self, audio, sample_rate):
        return self.transcribe_words(audio, sample_rate)[0]

    def transcribe_words(self, audio, sample_rate):
        self.calls += 1
        text, seed = self.synth.calls[-1]
        hyp = self.text_for.get((text, seed), text)
        start = self.lead if len(audio) >= 2000 else 0.0
        first = self.first_word or hyp[0]
        return hyp, [
            WordTiming(first, start, start + 0.2),
            WordTiming(hyp[1:2] or "。", start + 0.3, start + 0.5),
        ]


def make_words(lead=0.9, text_for=None, first_word=None, **config):
    config.setdefault("opening_extra_seeds", ())
    synth = FixedSynth()
    asr = WordsRecognizer(synth, lead, text_for, first_word)
    return SpeechPipeline(synth, asr, PipelineConfig(**config)), synth, asr


def test_long_lead_in_is_trimmed_and_recorded():
    pipeline, _, asr = make_words(lead=0.9)

    result = pipeline.run("我恢復了，我們繼續。")

    [chunk] = result.chunks
    attempt = chunk.attempts[0]
    assert chunk.status == "ok"
    assert attempt.trimmed_seconds == pytest.approx(0.75)
    assert len(result.audio) == 2000 - 750
    assert asr.calls == 2  # 裁完要再驗一次


def test_clean_start_is_not_trimmed_and_not_rechecked():
    pipeline, _, asr = make_words(lead=0.1)

    result = pipeline.run("我恢復了，我們繼續。")

    assert result.chunks[0].attempts[0].trimmed_seconds == 0
    assert len(result.audio) == 2000
    assert asr.calls == 1


def test_wrong_first_word_rejects_the_attempt_even_with_perfect_cer():
    pipeline, synth, _ = make_words(lead=0.0, first_word="謝")

    result = pipeline.run("我恢復了，我們繼續。")

    assert result.chunks[0].status == "skipped"
    assert len(synth.calls) >= 4
    assert all(a.rejected for a in result.chunks[0].attempts)


def test_short_text_needs_an_almost_exact_transcript():
    short = "額度用完了，我先安靜陪你走。"  # 12 字
    wrong = {(short, s): "眾度用完了，我先安靜陪你走。" for s in (1234, 7, 42, 2026)}
    # approx_cer=0：關掉「差一點就收下」，只看短句門檻（固定短句挑選走這條嚴格路徑）
    pipeline, _, _ = make_words(lead=0.0, text_for=wrong, first_word="額", approx_cer=0.0)

    result = pipeline.run(short)

    assert result.chunks[0].status == "skipped"  # CER 約 0.083，舊門檻 0.2 會放行


def test_long_text_keeps_the_looser_threshold():
    long_text = "這裡每年會設計不同的主題，利用大量燈光創造出山脈海洋花卉或其他壯觀場景。"
    wrong = {(long_text, 1234): long_text.replace("設計", "社記")}
    pipeline, _, _ = make_words(lead=0.0, text_for=wrong)

    result = pipeline.run(long_text)

    assert result.chunks[0].status == "ok"
    assert [a.seed for a in result.chunks[0].attempts] == [1234]


def test_recognisers_without_word_timestamps_still_work_as_before():
    pipeline, _ = make()  # 原本的 ScriptedRecognizer 沒有 transcribe_words

    result = pipeline.run("大稻埕是老街。")

    assert result.chunks[0].status == "ok"


class BlipSynth:
    """開頭有一小段雜音與近乎靜音的空白，約 0.45 秒才開口（取樣率 1000）。"""

    sample_rate = SR

    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def synthesize(self, text: str, seed: int) -> np.ndarray:
        self.calls.append((text, seed))
        t = np.arange(1000) / SR
        speech = (0.5 * np.sin(2 * np.pi * 50 * t)).astype(np.float32)
        blip = (0.03 * np.sin(2 * np.pi * 50 * t[:100])).astype(np.float32)
        quiet = (0.002 * np.sin(2 * np.pi * 50 * t[:350])).astype(np.float32)
        return np.concatenate([blip, quiet, speech])


def test_energy_based_lead_in_trim_removes_the_faint_sound_whisper_did_not_report():
    synth = BlipSynth()
    pipeline = SpeechPipeline(synth, ScriptedRecognizer(synth), PipelineConfig())

    result = pipeline.run("我恢復了，我們繼續。")

    attempt = result.chunks[0].attempts[0]
    assert attempt.trimmed_seconds == pytest.approx(0.37, abs=0.05)
    assert len(result.audio) == pytest.approx(1450 - 370, abs=50)


# ---- 開場句多試 seed（使用者決定 A：不要因為驗收不過就丟掉含名字的開場句）----

EXTRA = (314, 777)


def test_opening_chunk_tries_extra_seeds_before_giving_up():
    text = "台北霞海城隍廟就在前方。"
    wrong = {(text, s): "亂" for s in (1234, 7, 42, 2026)}
    pipeline, synth = make(wrong=wrong, opening_extra_seeds=EXTRA)

    result = pipeline.run(text)

    [chunk] = result.chunks
    assert chunk.status == "ok"
    assert [a.seed for a in chunk.attempts] == [1234, 7, 42, 2026, 314]


def test_later_chunks_do_not_get_extra_seeds():
    first, second = "甲" * 90 + "。", "乙乙乙乙。"
    wrong = {(second, s): "亂" for s in (1234, 7, 42, 2026)}
    pipeline, synth = make(wrong=wrong, opening_extra_seeds=EXTRA)

    result = pipeline.run(first + second)

    assert [c.status for c in result.chunks] == ["ok", "skipped"]
    assert len([c for c in synth.calls if c[0] == second]) == 4


def test_first_sentence_of_a_split_opening_keeps_the_extra_seeds():
    one, two = "台北霞海城隍廟就在前方。", "它在迪化街上。"
    chunk_text = one + two
    wrong = {(chunk_text, s): "亂" for s in (1234, 7, 42, 2026, *EXTRA)}
    wrong.update({(one, s): "亂" for s in (1234, 7, 42, 2026)})
    wrong.update({(two, s): "亂" for s in (1234, 7, 42, 2026, *EXTRA)})
    pipeline, _ = make(wrong=wrong, opening_extra_seeds=EXTRA, gap_seconds=0)

    result = pipeline.run(chunk_text)

    [chunk] = result.chunks
    assert chunk.status == "split"
    assert [p.status for p in chunk.pieces] == ["ok", "skipped"]
    assert chunk.pieces[0].attempts[-1].seed == 314


def test_extra_seeds_that_repeat_a_base_seed_are_only_tried_once():
    text = "台北霞海城隍廟就在前方。"
    wrong = {(text, s): "亂" for s in (1234, 7, 42, 2026, 314, 777)}
    pipeline, synth = make(wrong=wrong, opening_extra_seeds=(7, 314, 777))

    pipeline.run(text)

    seeds = [seed for t, seed in synth.calls if t == text]
    assert seeds == [1234, 7, 42, 2026, 314, 777]


def test_paragraph_break_gets_a_longer_pause_than_a_sentence_break():
    pipeline, _ = make(gap_seconds=0.5, paragraph_gap_seconds=1.5, chunk_chars=4)

    result = pipeline.run("甲乙丙。丁戊己。\n\n庚辛壬。")

    assert len(result.audio) == 3 * 40 + 500 + 1500


def test_chunks_never_merge_across_a_paragraph_break():
    pipeline, synth = make(gap_seconds=0, paragraph_gap_seconds=0, chunk_chars=90)

    pipeline.run("甲乙丙。\n\n丁戊己。")

    assert [text for text, _ in synth.calls] == ["甲乙丙。", "丁戊己。"]


def test_skipped_chunk_keeps_the_longer_pause_it_sat_on():
    text = "丁戊己。"
    pipeline, _ = make(
        wrong={(text, s): "亂" for s in (1234, 7, 42, 2026)},
        gap_seconds=0.5,
        paragraph_gap_seconds=1.5,
        chunk_chars=4,
    )

    result = pipeline.run("甲乙丙。\n\n丁戊己。\n\n庚辛壬。")

    assert len(result.audio) == 2 * 40 + 1500


def _wrong_by_one(text: str) -> str:
    return text[:3] + "錯" + text[4:]


def test_near_miss_is_accepted_as_is_instead_of_being_split_or_dropped():
    text = "等一下經過的時候可以瞄一眼門口。"  # 16 字：錯一個字是 0.0625，超過短句門檻 0.05
    wrong = {(text, s): _wrong_by_one(text) for s in (1234, 7, 42, 2026)}
    pipeline, synth = make(wrong=wrong)

    result = pipeline.run(text)

    [chunk] = result.chunks
    assert chunk.status == "approx"
    assert chunk.pieces == []
    assert len(result.audio) == len(text) * 10


def test_near_miss_uses_the_attempt_with_the_lowest_cer():
    text = "等一下經過的時候可以瞄一眼門口。"
    wrong = {
        (text, 1234): text[:3] + "錯錯" + text[5:],
        (text, 7): _wrong_by_one(text),
        (text, 42): text[:3] + "錯錯" + text[5:],
        (text, 2026): text[:3] + "錯錯" + text[5:],
    }
    pipeline, _ = make(wrong=wrong, approx_cer=0.1)

    result = pipeline.run(text)

    assert float(result.audio[0]) == pytest.approx(7 / 10000)


def test_rejected_attempts_are_never_used_as_the_near_miss():
    text = "等一下經過的時候可以瞄一眼門口。"
    wrong = {(text, s): "亂" for s in (1234, 7, 42, 2026)}
    pipeline, _ = make(wrong=wrong, split_on_failure=False)

    assert pipeline.run(text).chunks[0].status == "skipped"


def test_clear_misses_still_get_split_first():
    text = "甲乙丙丁，戊己庚辛。"
    wrong = {(text, s): "完全不一樣的句子啦" for s in (1234, 7, 42, 2026)}
    pipeline, _ = make(wrong=wrong)

    assert pipeline.run(text).chunks[0].status == "split"


def test_last_resort_piece_accepts_a_worse_attempt_than_a_near_miss():
    text = "甲乙丙丁戊己庚。"  # 不能再拆
    wrong = {(text, s): text[:2] + "錯錯" + text[4:] for s in (1234, 7, 42, 2026)}  # 2/7 ≈ 0.29
    pipeline, _ = make(wrong=wrong, leaf_approx_cer=0.3)

    assert pipeline.run(text).chunks[0].status == "approx"

    pipeline, _ = make(wrong=wrong, leaf_approx_cer=0.2)

    assert pipeline.run(text).chunks[0].status == "skipped"


def test_the_unit_guard_wraps_every_synthesis_unit_but_not_the_gaps_between_them():
    events: list[str] = []
    pipeline, synth = make()

    @contextlib.contextmanager
    def guard():
        events.append("enter")
        yield
        events.append("exit")

    synth_calls_before = len(synth.calls)
    pipeline.run("第一段話。\n\n第二段話。\n\n第三段話。", unit_guard=guard)

    assert events == ["enter", "exit"] * 3
    assert len(synth.calls) - synth_calls_before == 3


def test_a_unit_that_needs_retries_is_one_guarded_unit():
    entered = []
    text = "大稻埕是老街。"
    pipeline, synth = make(wrong={(text, 1234): "完全不一樣的話"})

    @contextlib.contextmanager
    def guard():
        entered.append(len(synth.calls))
        yield

    pipeline.run(text, unit_guard=guard)

    assert entered == [0]  # 換 seed 重試（共兩次合成）都在同一次守門裡
    assert len(synth.calls) == 2


def test_without_a_guard_nothing_changes():
    pipeline, synth = make()

    result = pipeline.run("大稻埕是老街。")

    assert result.audio_seconds > 0
