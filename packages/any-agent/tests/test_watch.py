"""The idle watchdog and the turn rules, on a clock the test drives."""

from any_agent import events as ev
from any_agent.watch import ANSWER_GRACE_S, LONG_GAP_S, SLEEP_GAP_S, STALL_S, Turn, Watchdog


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def walk(c, w, to, step=10.0):
    """Advance the clock to `to`, polling every `step` seconds (poll() reads a bigger jump as a suspended machine); -> the last poll."""
    got = w.poll()
    while c.t < to:
        c.t = min(to, c.t + step)
        got = w.poll()
    return got


def test_no_line_within_the_first_event_deadline_is_hung():
    c = Clock()
    w = Watchdog(10, 100, clock=c)
    assert walk(c, w, 5) is None
    assert walk(c, w, 11) == "first_event"
    assert w.describe() == "printed nothing within 10s"
    c.t = 12
    w.touch()
    assert w.poll() == "first_event"  # sticky


def test_silence_after_the_first_line_is_hung():
    c = Clock()
    w = Watchdog(10, 100, clock=c)
    w.touch()
    assert walk(c, w, 90) is None
    assert walk(c, w, 101) == "silence"
    assert w.describe() == "was silent for 100s"


def test_a_suspended_machine_is_not_silence():
    c = Clock()
    w = Watchdog(10, 100, clock=c)
    w.touch()
    c.t = 5
    w.poll()
    c.t = 5 + SLEEP_GAP_S + 1000  # the laptop slept
    assert w.poll() is None


def test_a_long_gap_is_kept_and_the_beat_is_at_most_every_30_s():
    c, beats = Clock(), []
    w = Watchdog(10, 10_000, clock=c, beat=beats.append, wall=lambda: 7.0)
    w.touch()
    c.t = 10
    w.touch()
    c.t = 10 + LONG_GAP_S + 1
    w.touch()
    assert w.gaps == [LONG_GAP_S + 1.0]
    assert beats == [7.0, 7.0]


def test_a_final_message_then_the_grace_is_an_answer():
    c = Clock()
    t = Turn(5, clock=c)
    t.apply([ev.Msg(text="done")])
    c.t = 4
    assert t.verdict(Watchdog(10, 100, clock=c)) is None
    c.t = 5
    assert t.verdict(Watchdog(10, 100, clock=c)) == "answer"


def test_a_later_event_reopens_the_turn():
    c = Clock()
    t = Turn(5, clock=c)
    t.apply([ev.TurnDone(usage=None)])
    t.apply([ev.Think(text="more")])
    c.t = 50
    assert t.verdict(Watchdog(10, 100, clock=c)) is None


def test_the_default_grace_is_two_minutes():
    assert Turn().grace_s == ANSWER_GRACE_S == 120


def test_a_model_owing_a_response_and_silent_is_a_stall_unless_a_tool_runs():
    c = Clock()
    w = Watchdog(10, 10_000, clock=c)
    t = Turn(5, clock=c)
    w.touch()
    t.apply([ev.Cmd(id="c1", text="sleep 99")])
    walk(c, w, STALL_S + 5)
    assert t.verdict(w) is None  # a tool is in flight: the long silence limit holds
    t.apply([ev.CmdEnd(id="c1", text="sleep 99", exit=0)])
    assert t.verdict(w) == "stall"
    assert "owed a model response" in t.stall_words()
