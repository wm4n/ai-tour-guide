from buddy_host.llm.quota import QuotaGate


class Clock:
    def __init__(self, now: float = 1000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


def gate(clock: Clock, retry_after_s: float = 900.0) -> QuotaGate:
    return QuotaGate(retry_after_s=retry_after_s, wall_clock=clock)


def test_a_fresh_gate_lets_everything_through():
    g = gate(Clock())

    assert not g.tripped
    assert not g.blocked()
    assert not g.may_probe()


def test_blocked_until_the_reported_reset_time_then_the_next_call_is_the_probe():
    clock = Clock(1000)
    g = gate(clock)

    g.trip(resets_at=1500)

    assert g.tripped and g.blocked() and not g.may_probe()
    clock.now = 1500
    assert g.tripped and not g.blocked() and g.may_probe()


def test_without_a_usable_reset_time_it_retries_after_the_fallback_interval():
    clock = Clock(1000)
    g = gate(clock, retry_after_s=900)

    g.trip(resets_at=None)
    clock.now = 1899
    assert g.blocked()
    clock.now = 1900
    assert g.may_probe()


def test_an_already_passed_reset_time_is_not_trusted():
    # 否則每次呼叫都會重試一次
    clock = Clock(1000)
    g = gate(clock, retry_after_s=900)

    g.trip(resets_at=999)

    assert g.blocked()
    clock.now = 1900
    assert g.may_probe()


def test_admit_refuses_while_blocked_and_lets_the_first_caller_through_afterwards():
    clock = Clock(1000)
    g = gate(clock)
    assert g.admit()  # 沒事的時候一律放行

    g.trip(resets_at=1500)
    assert not g.admit()
    clock.now = 1500
    assert g.admit()  # 這一次呼叫就是探測
    assert not g.tripped  # 探測期間閘門已打開，其他呼叫也放行
    assert g.admit()


def test_tripping_again_pushes_the_probe_time_out():
    clock = Clock(1000)
    g = gate(clock)
    g.trip(resets_at=1100)
    clock.now = 1100

    g.trip(resets_at=2000)  # 探測又被拒絕

    assert g.blocked()
