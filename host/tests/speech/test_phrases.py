import json
import wave

import numpy as np

from buddy_host.speech.phrases import (
    CANDIDATE_SEEDS,
    LEAD_FILLERS,
    PHRASES,
    WANTED,
    auto_voice_phrases,
    phrases_ready,
    seed_sequence,
    voice_phrases_dir,
)
from buddy_host.speech.pipeline import Attempt, PipelineConfig, SpeechPipeline
from buddy_host.speech.text_prep import prepare_sentences


def test_there_are_six_numbered_phrases_matching_the_design_doc():
    # 5（額度用完）與 8（恢復）已取消：改成畫面提示與自動繼續
    assert sorted(PHRASES) == [1, 2, 3, 4, 6, 7]
    assert PHRASES[7][0] == "好，走吧，我陪你。"


def test_phrases_need_no_preprocessing_beyond_a_terminal_mark():
    for text, _ in PHRASES.values():
        assert (
            "".join(prepare_sentences(text)) == text
            or "".join(prepare_sentences(text)) == text + "。"
        )


def test_enough_seeds_to_find_the_wanted_candidates():
    assert len(CANDIDATE_SEEDS) >= WANTED * 2


# --- --auto：為每個聲音自動挑固定短句 ---------------------------------------------------

RATE = 1000


class ScriptedPipeline:
    """依 (句子, seed) 預先寫好的結果回覆；沒寫的視為完美通過、音訊長 100 個取樣。

    結果是 (cer, 取樣數, 句首檢查不過的原因)。短句門檻 0.05：真的 SpeechPipeline.threshold_for。
    """

    def __init__(self, scripted=None):
        self.scripted = scripted or {}
        self.calls: list[tuple[str, int]] = []
        self.filler_calls: list[tuple[str, str, int]] = []

    def threshold_for(self, text):
        return 0.05 if len(text) <= 20 else 0.20

    def attempt(self, text, seed):
        self.calls.append((text, seed))
        cer, samples, rejected = self.scripted.get((text, seed), (0.0, 100, None))
        attempt = Attempt(seed, cer, text, 0.0, 0.0, samples / RATE, rejected=rejected)
        return attempt, np.full(samples, seed / 10000, dtype=np.float32)

    def attempt_after_lead_filler(self, text, filler, seed):
        self.filler_calls.append((text, filler, seed))
        return self.attempt(text, seed)


def spoken(number):
    return "".join(prepare_sentences(PHRASES[number][0]))


def frames(path):
    with wave.open(str(path)) as wav:
        return wav.getnframes()


def run_auto(tmp_path, pipeline, **kwargs):
    return auto_voice_phrases(pipeline, RATE, tmp_path / "F2@1.2", **kwargs)


def test_voice_phrases_live_apart_from_the_hand_picked_ones(tmp_path):
    folder = voice_phrases_dir(tmp_path, "F2@1.2")

    assert folder == tmp_path / "out" / "voice-phrases" / "F2@1.2"
    assert tmp_path / "out" / "phrases" not in folder.parents  # 人工挑選流程的目錄原封不動
    assert folder.parent != tmp_path / "out" / "phrases-final"


def test_the_seed_list_starts_with_the_hand_picking_seeds_and_can_grow():
    assert seed_sequence(8) == CANDIDATE_SEEDS
    longer = seed_sequence(12)
    assert longer[:8] == CANDIDATE_SEEDS
    assert len(longer) == len(set(longer)) == 12
    assert seed_sequence(3) == CANDIDATE_SEEDS[:3]


def test_auto_writes_every_phrase_when_all_pass(tmp_path):
    failed = run_auto(tmp_path, ScriptedPipeline())

    assert failed == []
    assert sorted(p.name for p in (tmp_path / "F2@1.2").glob("*.wav")) == [
        f"{n}.wav" for n in sorted(PHRASES)
    ]


def test_auto_tries_at_most_max_seeds_per_phrase_and_max_seeds_is_adjustable(tmp_path):
    pipeline = ScriptedPipeline()
    run_auto(tmp_path, pipeline)
    assert [c for c in pipeline.calls if c[0] == spoken(1)] == [
        (spoken(1), seed) for seed in CANDIDATE_SEEDS
    ]

    pipeline = ScriptedPipeline()
    run_auto(tmp_path, pipeline, max_seeds=3)
    assert len([c for c in pipeline.calls if c[0] == spoken(1)]) == 3

    pipeline = ScriptedPipeline()
    run_auto(tmp_path, pipeline, max_seeds=12)
    assert len([c for c in pipeline.calls if c[0] == spoken(1)]) == 12


def test_auto_keeps_the_lowest_cer_among_the_passing_versions(tmp_path):
    long_text = "甲" * 30 + "。"  # 超過 20 字：門檻 0.20（已含句號，和前處理後的樣子一致）
    phrases = {9: (long_text, "test")}
    scripted = {(long_text, seed): (0.30, 100, None) for seed in CANDIDATE_SEEDS}  # 預設都超過門檻
    scripted[(long_text, 1234)] = (0.15, 300, None)
    scripted[(long_text, 7)] = (0.05, 500, None)  # 通過、而且最低
    pipeline = ScriptedPipeline(scripted)

    failed = auto_voice_phrases(pipeline, RATE, tmp_path, phrases=phrases)

    assert failed == []
    assert frames(tmp_path / "9.wav") == 500


def test_auto_prefers_the_shorter_audio_when_cer_ties(tmp_path):
    pipeline = ScriptedPipeline(
        {
            (spoken(7), 1234): (0.0, 300, None),
            (spoken(7), 7): (0.0, 120, None),  # 同分取較短
            (spoken(7), 42): (0.0, 200, None),
        }
    )

    run_auto(tmp_path, pipeline)

    assert frames(tmp_path / "F2@1.2" / "7.wav") == 100  # 其餘 seed 預設 100 個取樣、最短


def test_auto_only_accepts_versions_that_pass_the_gate(tmp_path):
    pipeline = ScriptedPipeline(
        {
            (spoken(2), 1234): (0.0, 50, "句首有多餘的聲音"),  # 句首不過：CER 再低也不採用
            (spoken(2), 7): (0.10, 60, None),  # 短句超過 0.05
            (spoken(2), 42): (0.0, 70, None),
        }
    )
    pipeline.scripted.update({(spoken(2), seed): (0.2, 10, None) for seed in CANDIDATE_SEEDS[3:]})

    run_auto(tmp_path, pipeline)

    assert frames(tmp_path / "F2@1.2" / "2.wav") == 70


def test_a_phrase_with_no_passing_version_is_not_written_and_is_reported(tmp_path):
    pipeline = ScriptedPipeline({(spoken(3), seed): (0.2, 100, None) for seed in CANDIDATE_SEEDS})

    failed = run_auto(tmp_path, pipeline)

    assert failed == [3]
    folder = tmp_path / "F2@1.2"
    assert not (folder / "3.wav").exists()
    assert sorted(p.name for p in folder.glob("*.wav")) == [
        "1.wav",
        "2.wav",
        "4.wav",
        "6.wav",
        "7.wav",
    ]


def test_a_phrase_that_fails_this_time_drops_the_old_file_so_the_voice_is_not_ready(tmp_path):
    folder = voice_phrases_dir(tmp_path, "F2@1.2")
    auto_voice_phrases(ScriptedPipeline(), RATE, folder)  # 先全部產生
    assert phrases_ready(tmp_path, "F2@1.2") is True

    # 稿子改過之後重跑：3 號這次沒有版本通過，舊的 3 號音檔講的是舊稿，不能留
    failing = ScriptedPipeline({(spoken(3), seed): (0.2, 100, None) for seed in CANDIDATE_SEEDS})
    failed = auto_voice_phrases(failing, RATE, folder)

    assert failed == [3]
    assert not (folder / "3.wav").exists()
    assert phrases_ready(tmp_path, "F2@1.2") is False
    index = json.loads((folder / "index.json").read_text(encoding="utf-8"))
    assert "3" not in index and "1" in index  # 失敗那句的舊記錄也不留


def test_phrases_are_ready_only_when_every_phrase_exists_for_the_current_speed(tmp_path):
    assert phrases_ready(tmp_path, "F2@1.2") is False

    auto_voice_phrases(ScriptedPipeline(), RATE, voice_phrases_dir(tmp_path, "F2@1.2"))

    assert phrases_ready(tmp_path, "F2@1.2") is True
    assert phrases_ready(tmp_path, "F2@1.5") is False  # 改了語速：短句要重新產生
    assert phrases_ready(tmp_path, "M1@1.2") is False


def test_one_missing_phrase_makes_the_voice_not_ready(tmp_path):
    failed = auto_voice_phrases(
        ScriptedPipeline({(spoken(6), seed): (0.5, 100, None) for seed in CANDIDATE_SEEDS}),
        RATE,
        voice_phrases_dir(tmp_path, "F2@1.2"),
    )

    assert failed == [6]
    assert phrases_ready(tmp_path, "F2@1.2") is False


def test_auto_works_with_the_real_pipeline_and_fake_engines(tmp_path):
    class Synth:
        sample_rate = RATE

        def __init__(self):
            self.last = ("", 0)

        def synthesize(self, text, seed):
            self.last = (text, seed)
            return np.full(len(text) * 10, 0.1, dtype=np.float32)

    class Asr:
        def __init__(self, synth):
            self.synth = synth

        def transcribe(self, audio, sample_rate):
            return self.synth.last[0]

    synth = Synth()
    pipeline = SpeechPipeline(synth, Asr(synth), PipelineConfig())

    failed = auto_voice_phrases(pipeline, RATE, tmp_path / "F2@1.2")

    assert failed == []
    assert sorted(p.name for p in (tmp_path / "F2@1.2").glob("*.wav")) == [
        f"{n}.wav" for n in sorted(PHRASES)
    ]


def test_phrases_that_start_with_a_filler_are_checked_after_the_filler(tmp_path):
    pipeline = ScriptedPipeline()

    run_auto(tmp_path, pipeline, max_seeds=2)

    assert set(LEAD_FILLERS) == {2, 3}
    fillered = {text for text, _, _ in pipeline.filler_calls}
    assert fillered == {spoken(n) for n in LEAD_FILLERS}
    for number, (text, _) in PHRASES.items():  # 語氣詞真的是句子的開頭
        if number in LEAD_FILLERS:
            assert text.startswith(LEAD_FILLERS[number])


def test_filler_phrases_keep_every_passing_version_as_a_candidate_to_listen_to(tmp_path):
    scripted = {(spoken(3), 7): (0.2, 100, None)}  # 這個 seed 沒通過：不留
    pipeline = ScriptedPipeline(scripted)

    run_auto(tmp_path, pipeline, max_seeds=3)

    folder = tmp_path / "F2@1.2" / "candidates"
    assert sorted(p.name for p in folder.glob("*.wav")) == sorted(
        [
            f"{n}_seed{seed}.wav"
            for n in LEAD_FILLERS
            for seed in CANDIDATE_SEEDS[:3]
            if (n, seed) != (3, 7)
        ]
    )


def test_phrases_without_a_filler_leave_no_candidates(tmp_path):
    run_auto(tmp_path, ScriptedPipeline(), max_seeds=3)

    names = [p.name for p in (tmp_path / "F2@1.2" / "candidates").glob("*.wav")]
    assert all(int(name.split("_")[0]) in LEAD_FILLERS for name in names)
