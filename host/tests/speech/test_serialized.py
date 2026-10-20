import threading
import time

from buddy_host.speech.serialized import SerializedSpeech


class Probe:
    """記錄同時有幾個執行緒在 run 裡面。"""

    def __init__(self):
        self.inside = 0
        self.max_inside = 0
        self.guard = threading.Lock()

    def run(self, text):
        with self.guard:
            self.inside += 1
            self.max_inside = max(self.max_inside, self.inside)
        time.sleep(0.02)
        with self.guard:
            self.inside -= 1
        return text.upper()


def test_only_one_thread_uses_the_pipeline_at_a_time():
    probe = Probe()
    speech = SerializedSpeech(probe)
    results = []
    threads = [
        threading.Thread(target=lambda i=i: results.append(speech.run(f"t{i}"))) for i in range(6)
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert probe.max_inside == 1
    assert sorted(results) == [f"T{i}" for i in range(6)]


def test_an_error_releases_the_lock_for_the_next_caller():
    class Boom:
        def __init__(self):
            self.calls = 0

        def run(self, text):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("壞了")
            return text

    speech = SerializedSpeech(Boom())
    try:
        speech.run("a")
    except RuntimeError:
        pass

    assert speech.run("b") == "b"
