from datetime import datetime

from buddy_host.narration.traveler import Companions, TravelerContext, TravelMode


def text(**kw) -> str:
    return "\n".join(TravelerContext(**kw).describe())


def test_nothing_known_says_nothing():
    assert TravelerContext().describe() == []


def test_walking_invites_him_to_look_around():
    assert "走路" in text(mode=TravelMode.WALKING)
    assert "看一下" in text(mode=TravelMode.WALKING)


def test_driving_never_asks_him_to_stop_or_look_down():
    said = text(mode=TravelMode.DRIVING)

    assert "開車" in said
    assert "不要請他停下" in said


def test_companions_are_named():
    assert "一個人" in text(companions=Companions.SOLO)
    assert "家人" in text(companions=Companions.FAMILY)
    assert "朋友" in text(companions=Companions.FRIENDS)
    assert "兩個人" in text(companions=Companions.COUPLE)


def test_children_rule_out_scary_and_adult_topics():
    said = text(with_children=True)

    assert "小朋友" in said
    assert "鬼" in said and "酒" in said


def test_time_of_day_is_described_in_words():
    assert "早上" in text(local_time=datetime(2026, 10, 19, 8, 30))
    assert "下午" in text(local_time=datetime(2026, 10, 19, 15, 0))
    assert "晚上" in text(local_time=datetime(2026, 10, 19, 21, 0))
    assert "深夜" in text(local_time=datetime(2026, 10, 19, 2, 0))


def test_key_ignores_the_exact_minute_but_not_the_part_of_day_or_companions():
    morning = TravelerContext(local_time=datetime(2026, 10, 19, 8, 0))

    assert morning.key() == TravelerContext(local_time=datetime(2026, 10, 19, 9, 40)).key()
    assert morning.key() != TravelerContext(local_time=datetime(2026, 10, 19, 15, 0)).key()
    assert TravelerContext(companions=Companions.SOLO).key() != TravelerContext().key()
