import threading
import time

import numpy as np

from buddy_host.speech.pipeline import PipelineConfig, SpeechPipeline
from buddy_host.speech.scheduler import SpeechScheduler

SR = 1000


class SlowSynth:
    """每次合成都睡一下；可以讓指定文字的合成卡住，用來安排「問答在介紹合成到一半時進來」。"""

    sample_rate = SR

    def __init__(self, delay=0.03):
        self.delay = delay
        self.calls: list[str] = []
        self.inside = 0
        self.max_inside = 0
        self.started: dict[str, threading.Event] = {}
        self.blocked: dict[str, threading.Event] = {}
        self.lock = threading.Lock()

    def watch(self, text):
        self.started[text] = threading.Event()

    def block(self, text):
        self.blocked[text] = threading.Event()
        self.watch(text)

    def synthesize(self, text, seed):
        with self.lock:
            self.calls.append(text)
            self.inside += 1
            self.max_inside = max(self.max_inside, self.inside)
        if text in self.started:
            self.started[text].set()
        if text in self.blocked:
            self.blocked[text].wait(5)
        time.sleep(self.delay)
        with self.lock:
            self.inside -= 1
        return np.full(len(text) * 10, 0.1, dtype=np.float32)


class PerfectRecognizer:
    """轉寫出最後一次合成的文字（驗收一定通過）。"""

    def __init__(self, synth):
        self.synth = synth

    def transcribe(self, audio, sample_rate):
        return self.synth.calls[-1]


def make(delay=0.03):
    synth = SlowSynth(delay)
    pipeline = SpeechPipeline(
        synth, PerfectRecognizer(synth), PipelineConfig(opening_extra_seeds=())
    )
    return SpeechScheduler(pipeline), synth


STORY = "介紹第一段。\n\n介紹第二段。\n\n介紹第三段。"
ANSWER = "答案的第一段。"
ANSWER_2 = "第二個答案。"


def in_thread(fn, *args):
    out: dict = {}

    def target():
        try:
            out["result"] = fn(*args)
        except BaseException as error:  # noqa: BLE001
            out["error"] = error

    thread = threading.Thread(target=target)
    thread.start()
    return thread, out


def wait_until(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("等不到條件成立")


def test_an_answer_goes_before_the_narration_units_that_have_not_started_yet():
    scheduler, synth = make()
    synth.block("介紹第一段。")
    story, _ = in_thread(scheduler.narration.run, STORY)
    synth.started["介紹第一段。"].wait(5)  # 介紹的第一個單位正在合成

    answer, _ = in_thread(scheduler.answers.run, ANSWER)
    wait_until(lambda: scheduler.pending_answers == 1)
    synth.blocked["介紹第一段。"].set()
    story.join(5)
    answer.join(5)

    assert synth.calls == ["介紹第一段。", ANSWER, "介紹第二段。", "介紹第三段。"]


def test_the_unit_already_being_synthesized_is_never_interrupted():
    scheduler, synth = make()
    synth.block("介紹第一段。")
    story, _ = in_thread(scheduler.narration.run, STORY)
    synth.started["介紹第一段。"].wait(5)
    answer, _ = in_thread(scheduler.answers.run, ANSWER)
    wait_until(lambda: scheduler.pending_answers == 1)

    time.sleep(0.1)
    assert synth.calls == ["介紹第一段。"]  # 問答在等，沒有硬插進來

    synth.blocked["介紹第一段。"].set()
    story.join(5)
    answer.join(5)
    assert synth.calls[:2] == ["介紹第一段。", ANSWER]


def test_the_narration_still_finishes_after_the_answer_is_done():
    scheduler, synth = make()
    synth.block("介紹第一段。")
    story, out = in_thread(scheduler.narration.run, STORY)
    synth.started["介紹第一段。"].wait(5)
    answer, _ = in_thread(scheduler.answers.run, ANSWER)
    wait_until(lambda: scheduler.pending_answers == 1)
    synth.blocked["介紹第一段。"].set()

    story.join(5)
    answer.join(5)

    assert not story.is_alive() and "error" not in out
    assert out["result"].audio_seconds > 0
    assert synth.calls.count("介紹第三段。") == 1  # 三個單位一個不少


def test_several_answers_are_made_one_after_another_never_at_the_same_time():
    scheduler, synth = make()
    synth.block("介紹第一段。")
    story, _ = in_thread(scheduler.narration.run, STORY)
    synth.started["介紹第一段。"].wait(5)
    first, _ = in_thread(scheduler.answers.run, ANSWER)
    wait_until(lambda: scheduler.pending_answers == 1)
    second, _ = in_thread(scheduler.answers.run, ANSWER_2)
    wait_until(lambda: scheduler.pending_answers == 2)
    synth.blocked["介紹第一段。"].set()
    for thread in (story, first, second):
        thread.join(5)

    assert synth.calls == ["介紹第一段。", ANSWER, ANSWER_2, "介紹第二段。", "介紹第三段。"]
    assert synth.max_inside == 1  # 全程只有一個單位在合成


def test_a_multi_unit_answer_keeps_the_gpu_until_it_is_done():
    scheduler, synth = make()
    long_answer = "答案第一段。\n\n答案第二段。"
    synth.block("介紹第一段。")
    story, _ = in_thread(scheduler.narration.run, STORY)
    synth.started["介紹第一段。"].wait(5)
    answer, _ = in_thread(scheduler.answers.run, long_answer)
    wait_until(lambda: scheduler.pending_answers == 1)
    synth.blocked["介紹第一段。"].set()
    story.join(5)
    answer.join(5)

    assert synth.calls == [
        "介紹第一段。",
        "答案第一段。",
        "答案第二段。",
        "介紹第二段。",
        "介紹第三段。",
    ]


def test_without_any_answer_the_narration_runs_straight_through():
    scheduler, synth = make()

    result = scheduler.narration.run(STORY)

    assert synth.calls == ["介紹第一段。", "介紹第二段。", "介紹第三段。"]
    assert result.audio_seconds > 0
    assert scheduler.pending_answers == 0


def test_an_answer_that_fails_does_not_block_the_next_one_or_the_narration():
    scheduler, synth = make()
    original = synth.synthesize

    def explode_once(text, seed):
        if text == ANSWER:
            raise RuntimeError("引擎壞了")
        return original(text, seed)

    synth.synthesize = explode_once
    synth.block("介紹第一段。")
    story, _ = in_thread(scheduler.narration.run, STORY)
    synth.started["介紹第一段。"].wait(5)
    bad, bad_out = in_thread(scheduler.answers.run, ANSWER)
    wait_until(lambda: scheduler.pending_answers == 1)
    good, good_out = in_thread(scheduler.answers.run, ANSWER_2)
    wait_until(lambda: scheduler.pending_answers == 2)
    synth.blocked["介紹第一段。"].set()
    for thread in (story, bad, good):
        thread.join(5)

    assert isinstance(bad_out["error"], RuntimeError)
    assert good_out["result"].audio_seconds > 0
    assert synth.calls[-2:] == ["介紹第二段。", "介紹第三段。"]
    assert scheduler.pending_answers == 0


def test_two_narration_runs_never_synthesize_at_the_same_time():
    scheduler, synth = make()

    first, _ = in_thread(scheduler.narration.run, STORY)
    second, _ = in_thread(scheduler.narration.run, "別的介紹。\n\n別的介紹二。")
    first.join(5)
    second.join(5)

    assert synth.max_inside == 1


def test_the_narration_does_not_slip_in_between_the_segments_of_one_answer():
    scheduler, synth = make()
    synth.block("介紹第一段。")
    story, _ = in_thread(scheduler.narration.run, STORY)
    synth.started["介紹第一段。"].wait(5)
    turn = scheduler.answers.begin()  # 開始回答：從這一刻到結束都算問答優先
    first, _ = in_thread(turn.run, ANSWER)
    wait_until(lambda: scheduler.pending_answers == 1)
    synth.blocked["介紹第一段。"].set()
    first.join(5)

    time.sleep(0.15)  # 等 Claude 寫下一段的空檔：介紹不可以趁機開始新單位
    assert synth.calls == ["介紹第一段。", ANSWER]

    second, _ = in_thread(turn.run, ANSWER_2)
    second.join(5)
    assert synth.calls == ["介紹第一段。", ANSWER, ANSWER_2]

    turn.end()
    story.join(5)
    assert synth.calls == ["介紹第一段。", ANSWER, ANSWER_2, "介紹第二段。", "介紹第三段。"]


def test_a_turn_that_never_synthesized_anything_does_not_block_the_next_one():
    scheduler, synth = make()
    abandoned = scheduler.answers.begin()
    waiting = scheduler.answers.begin()

    abandoned.end()  # 例如答案寫到一半失敗，一段都沒做
    result = waiting.run(ANSWER)
    waiting.end()

    assert result.audio_seconds > 0
    assert scheduler.pending_answers == 0


def test_ending_a_turn_while_its_run_is_still_waiting_does_not_hang_or_synthesize():
    scheduler, synth = make()
    first = scheduler.answers.begin()
    second = scheduler.answers.begin()
    thread, out = in_thread(second.run, ANSWER_2)  # 還輪不到第二個
    wait_until(lambda: scheduler.pending_answers == 2)

    second.end()  # 答案被放棄
    thread.join(5)

    assert not thread.is_alive()
    assert type(out["error"]).__name__ == "TurnEnded"
    assert synth.calls == []
    first.end()
    assert scheduler.pending_answers == 0


def test_the_next_turn_waits_for_a_run_that_is_still_synthesizing_even_if_its_turn_ended():
    scheduler, synth = make()
    synth.block(ANSWER)
    first = scheduler.answers.begin()
    running, _ = in_thread(first.run, ANSWER)
    synth.started[ANSWER].wait(5)
    second = scheduler.answers.begin()
    nxt, _ = in_thread(second.run, ANSWER_2)

    first.end()  # 取消了，但合成的執行緒還沒做完
    time.sleep(0.1)
    assert synth.calls == [ANSWER]  # 下一個還不能開始

    synth.blocked[ANSWER].set()
    running.join(5)
    nxt.join(5)
    assert synth.calls == [ANSWER, ANSWER_2]
    assert synth.max_inside == 1


def test_ending_a_turn_twice_is_harmless():
    scheduler, _ = make()
    turn = scheduler.answers.begin()

    turn.end()
    turn.end()

    assert scheduler.pending_answers == 0


def test_a_narration_unit_that_crashes_releases_the_gpu_for_everyone_else():
    scheduler, synth = make()
    original = synth.synthesize

    def explode_once(text, seed):
        if text == "介紹第一段。":
            synth.synthesize = original
            raise RuntimeError("引擎壞了")
        return original(text, seed)

    synth.synthesize = explode_once
    story, out = in_thread(scheduler.narration.run, STORY)
    story.join(5)

    assert isinstance(out["error"], RuntimeError)
    assert scheduler.answers.run(ANSWER).audio_seconds > 0  # 沒有卡在「介紹忙碌中」


def test_answers_cap_pauses_but_narration_keeps_them():
    synth = SlowSynth(delay=0)
    config = PipelineConfig(
        opening_extra_seeds=(), paragraph_gap_seconds=1.5, answer_max_pause_seconds=0.45
    )
    scheduler = SpeechScheduler(SpeechPipeline(synth, PerfectRecognizer(synth), config))
    text = "甲乙丙。\n\n庚辛壬。"  # 兩段各 40 個取樣，中間 1.5 秒

    story = scheduler.narration.run(text)
    answer = scheduler.answers.run(text)

    assert len(story.audio) == 40 + 1500 + 40
    assert len(answer.audio) < 40 + 600 + 40
