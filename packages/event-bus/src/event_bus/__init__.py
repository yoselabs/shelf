"""In-process synchronous publish/subscribe over one event type.

No async, no persistence, no topics: a fresh process starts empty and holds nothing but
its current subscribers. With none, :meth:`EventBus.publish` costs a loop over nothing.

**Subscribers are held by strong reference, deliberately.** A weak one (blinker's default)
makes the ordinary spelling — ``bus.subscribe(lambda e: ...)``, or a bound method of an
object nobody else keeps — collect at once and silently stop delivering. Missed events
with no error is worse than a held reference, and it is the one a caller cannot see. The
price is that a subscription pins what its callback closes over until it is released,
which is why :meth:`EventBus.subscribe` returns the release and :meth:`EventBus.subscribed`
exists to hold it for a block.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

_E = TypeVar("_E")


class EventBus(Generic[_E]):
    """Publish one event type to every current subscriber, synchronously, in subscribe order."""

    def __init__(self) -> None:
        self._subscribers: list[Callable[[_E], None]] = []

    def subscribe(self, callback: Callable[[_E], None]) -> Callable[[], None]:
        """Attach ``callback``; return the idempotent release.

        The returned handle is the contract, not a convenience: dropping it leaves the
        callback attached for the life of the process, and a second start on the same bus
        then delivers every event twice. Prefer :meth:`subscribed` when there is a scope.
        """
        self._subscribers.append(callback)

        def unsubscribe() -> None:
            with contextlib.suppress(ValueError):
                self._subscribers.remove(callback)

        return unsubscribe

    @contextlib.contextmanager
    def subscribed(self, callback: Callable[[_E], None]) -> Generator[None]:
        """:meth:`subscribe` for a ``with`` block, released on any exit."""
        unsubscribe = self.subscribe(callback)
        try:
            yield
        finally:
            unsubscribe()

    def publish(self, event: _E) -> None:
        """Call every current subscriber with ``event``.

        Over a snapshot, so a subscriber may release itself during delivery. A subscriber
        that raises stops delivery and the error reaches the publisher: isolating it is the
        subscriber's choice, not the bus's.
        """
        for callback in tuple(self._subscribers):
            callback(event)

    def __len__(self) -> int:
        """How many subscriptions are live."""
        return len(self._subscribers)


__all__ = ["EventBus"]
