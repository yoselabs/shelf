"""EventBus — strong subscribers, a release that is real, a scope that always releases."""

from __future__ import annotations

import gc
import weakref

import pytest
from event_bus import EventBus


def test_publish_reaches_every_subscriber_in_order() -> None:
    bus: EventBus[int] = EventBus()
    seen: list[str] = []
    bus.subscribe(lambda e: seen.append(f"a{e}"))
    bus.subscribe(lambda e: seen.append(f"b{e}"))
    bus.publish(1)
    assert seen == ["a1", "b1"]


def test_publish_with_no_subscribers_is_a_noop() -> None:
    EventBus[str]().publish("x")


def test_a_lambda_keeps_receiving() -> None:
    """The weak-reference failure: a lambda nobody else holds must not be collected."""
    bus: EventBus[int] = EventBus()
    seen: list[int] = []
    bus.subscribe(lambda e: seen.append(e))  # noqa: PLW0108 — the lambda is the point
    gc.collect()
    bus.publish(7)
    assert seen == [7]


def test_unsubscribe_stops_delivery_and_is_idempotent() -> None:
    bus: EventBus[int] = EventBus()
    seen: list[int] = []
    release = bus.subscribe(seen.append)
    bus.publish(1)
    release()
    release()
    bus.publish(2)
    assert seen == [1]
    assert len(bus) == 0


def test_subscribed_releases_on_normal_exit_and_on_error() -> None:
    bus: EventBus[int] = EventBus()
    seen: list[int] = []
    with bus.subscribed(seen.append):
        bus.publish(1)
    with pytest.raises(RuntimeError), bus.subscribed(seen.append):
        raise RuntimeError
    bus.publish(2)
    assert seen == [1]


def test_a_subscriber_may_release_itself_during_delivery() -> None:
    bus: EventBus[int] = EventBus()
    seen: list[str] = []

    def once(_: int) -> None:
        seen.append("once")
        release()

    release = bus.subscribe(once)
    bus.subscribe(lambda _: seen.append("other"))
    bus.publish(1)
    bus.publish(2)
    assert seen == ["once", "other", "other"]


def test_a_raising_subscriber_reaches_the_publisher() -> None:
    bus: EventBus[int] = EventBus()

    def boom(_: int) -> None:
        msg = "subscriber failed"
        raise ValueError(msg)

    bus.subscribe(boom)
    with pytest.raises(ValueError, match="subscriber failed"):
        bus.publish(1)


def test_release_drops_the_reference() -> None:
    """Held strongly, so the release has to free what the callback closes over."""
    bus: EventBus[int] = EventBus()

    class Sink:
        def __call__(self, event: int) -> None: ...

    sink = Sink()
    ref = weakref.ref(sink)
    with bus.subscribed(sink):
        assert len(bus) == 1
    del sink
    gc.collect()
    assert ref() is None
