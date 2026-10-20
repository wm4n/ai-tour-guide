import json

from buddy_host.tour.journey import JourneyMemory

HOUR = 3600.0
T0 = 1_000_000.0


def test_the_first_start_is_a_new_trip(tmp_path):
    journey = JourneyMemory(tmp_path / "journey.json")

    result = journey.begin(T0)

    assert result.resumed is False
    assert result.abandoned is None
    assert journey.trip_started_at == T0


def test_restarting_within_two_hours_of_the_last_activity_continues_the_same_trip(tmp_path):
    journey = JourneyMemory(tmp_path / "journey.json")
    journey.begin(T0)
    journey.record_told(T0 + 600, "wiki:A", "A", "A 的稿子")
    journey.touch(T0 + 1800)  # 最後一次活動

    result = journey.begin(T0 + 1800 + 2 * HOUR - 1)

    assert result.resumed is True
    assert journey.trip_started_at == T0
    assert journey.recent_topics() == ("A",)


def test_restarting_after_two_hours_is_a_new_trip_and_hands_back_the_abandoned_one(tmp_path):
    journey = JourneyMemory(tmp_path / "journey.json")
    journey.begin(T0)
    journey.record_told(T0 + 600, "wiki:A", "A", "稿")
    journey.touch(T0 + 1800)

    result = journey.begin(T0 + 1800 + 2 * HOUR)

    assert result.resumed is False
    assert result.abandoned.started_at == T0
    assert result.abandoned.last_activity_at == T0 + 1800
    assert [stop.name for stop in result.abandoned.stops] == ["A"]
    assert journey.recent_topics() == ()  # 新的一趟，這趟剛講過的清空
    assert journey.trip_started_at == T0 + 1800 + 2 * HOUR


def test_pressing_end_closes_the_trip_so_the_next_start_is_a_new_one(tmp_path):
    journey = JourneyMemory(tmp_path / "journey.json")
    journey.begin(T0)
    journey.record_told(T0 + 60, "wiki:A", "A", "稿")
    journey.finish(T0 + 120)

    result = journey.begin(T0 + 180)

    assert result.resumed is False
    assert result.abandoned is None  # 正常結束的不算被丟下


def test_places_told_are_remembered_forever_across_trips(tmp_path):
    path = tmp_path / "journey.json"
    first = JourneyMemory(path)
    first.begin(T0)
    first.record_told(T0 + 60, "wiki:A", "A", "上次講 A 是茶行")
    first.finish(T0 + 120)

    second = JourneyMemory(path)  # 主機重啟
    second.begin(T0 + 30 * 24 * HOUR)

    assert second.told_before() == {"wiki:A": ("上次講 A 是茶行",)}
    assert second.stop_ids() == set()  # 新的一趟，A 可以再講（換角度）


def test_an_open_trip_survives_a_host_restart(tmp_path):
    path = tmp_path / "journey.json"
    first = JourneyMemory(path)
    first.begin(T0)
    first.record_told(T0 + 60, "wiki:A", "A", "稿")

    second = JourneyMemory(path)
    result = second.begin(T0 + 600)

    assert result.resumed is True
    assert second.stop_ids() == {"wiki:A"}


def test_recent_topics_are_only_the_latest_few_stops_of_this_trip_in_order(tmp_path):
    journey = JourneyMemory(tmp_path / "journey.json", max_recent=3)
    journey.begin(T0)
    for index, name in enumerate(["A", "B", "C", "D", "E"]):
        journey.record_told(T0 + index, f"wiki:{name}", name, f"{name}稿")

    assert journey.recent_topics() == ("C", "D", "E")


def test_what_was_told_is_capped_in_count_and_length(tmp_path):
    journey = JourneyMemory(tmp_path / "journey.json", told_per_place=2, told_chars=10)
    for index in range(4):  # 同一個地方在四趟裡各講過一次
        journey.begin(T0 + index * 10 * HOUR)
        journey.record_told(T0 + index * 10 * HOUR + 1, "wiki:A", "A", f"第{index}次" + "字" * 50)
        journey.finish(T0 + index * 10 * HOUR + 2)

    told = journey.told_before()["wiki:A"]

    assert len(told) == 2
    assert told[0].startswith("第2次")  # 保留最近的
    assert told[1].startswith("第3次")
    assert all(len(text) <= 10 for text in told)
    assert told[0].endswith("…")


def test_telling_the_same_place_twice_in_one_trip_is_recorded_once(tmp_path):
    journey = JourneyMemory(tmp_path / "journey.json")
    journey.begin(T0)

    journey.record_told(T0 + 1, "wiki:A", "A", "稿一")
    journey.record_told(T0 + 2, "wiki:A", "A", "稿二")

    assert journey.told_before()["wiki:A"] == ("稿一",)
    assert journey.recent_topics() == ("A",)


def test_without_a_path_the_memory_lives_only_in_memory(tmp_path):
    journey = JourneyMemory(None)
    journey.begin(T0)
    journey.record_told(T0 + 1, "wiki:A", "A", "稿")

    assert journey.stop_ids() == {"wiki:A"}
    assert list(tmp_path.iterdir()) == []


def test_a_corrupt_file_is_kept_aside_and_memory_starts_empty(tmp_path):
    path = tmp_path / "journey.json"
    path.write_text("{broken", encoding="utf-8")

    journey = JourneyMemory(path)
    journey.begin(T0)

    assert journey.told_before() == {}
    [kept] = list(tmp_path.glob("journey.json.corrupt-*"))
    assert kept.read_text(encoding="utf-8") == "{broken"


def test_saving_never_leaves_a_half_written_file(tmp_path):
    path = tmp_path / "journey.json"
    journey = JourneyMemory(path)
    journey.begin(T0)
    journey.record_told(T0 + 1, "wiki:A", "A", "稿")

    assert json.loads(path.read_text(encoding="utf-8"))["visited"]["wiki:A"]
    assert [p.name for p in tmp_path.iterdir()] == ["journey.json"]  # 沒有留下暫存檔


def test_activity_updates_are_not_written_to_disk_every_time(tmp_path):
    path = tmp_path / "journey.json"
    journey = JourneyMemory(path)
    journey.begin(T0)
    written = path.stat().st_mtime_ns

    journey.touch(T0 + 10)
    assert path.stat().st_mtime_ns == written

    journey.touch(T0 + 120)
    reloaded = JourneyMemory(path)
    assert reloaded.begin(T0 + 120 + 2 * HOUR - 1).resumed is True


def test_a_disk_error_never_breaks_the_trip(tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("擋住", encoding="utf-8")
    journey = JourneyMemory(blocker / "journey.json")  # 上層是檔案，永遠寫不進去

    journey.begin(T0)
    journey.record_told(T0 + 1, "wiki:A", "A", "稿")
    journey.touch(T0 + 600)
    journey.finish(T0 + 700)

    assert journey.told_before() == {"wiki:A": ("稿",)}  # 記憶體裡照常運作


def test_last_told_is_the_most_recent_narration_that_finished_playing(tmp_path):
    journey = JourneyMemory(tmp_path / "journey.json")
    journey.begin(T0)
    assert journey.last_told() is None  # 這趟還沒講過任何東西

    journey.record_told(T0 + 60, "wiki:A", "A", "A 的稿子")
    journey.record_told(T0 + 600, "wiki:B", "B", "B 的稿子")

    assert journey.last_told() == ("B", "B 的稿子")


def test_last_told_is_clipped_like_the_rest_of_the_summary(tmp_path):
    journey = JourneyMemory(tmp_path / "journey.json", told_chars=10)
    journey.begin(T0)
    journey.record_told(T0 + 60, "wiki:A", "A", "一二三四五六七八九十十一十二")

    name, script = journey.last_told()

    assert name == "A"
    assert len(script) == 10 and script.endswith("…")


def test_last_told_does_not_carry_over_to_a_new_trip(tmp_path):
    journey = JourneyMemory(tmp_path / "journey.json")
    journey.begin(T0)
    journey.record_told(T0 + 60, "wiki:A", "A", "稿")
    journey.finish(T0 + 120)

    journey.begin(T0 + 180)

    assert journey.last_told() is None
