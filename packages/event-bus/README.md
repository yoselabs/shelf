# event-bus

**Stop rewriting the in-process publish/subscribe.** One typed event, synchronous delivery,
subscribers held strongly, and a release you cannot lose track of.

```python
from event_bus import EventBus

bus: EventBus[Change] = EventBus()
release = bus.subscribe(on_change)        # keep the handle: it is the contract
with bus.subscribed(lambda e: log(e)):    # or scope it; released on any exit
    bus.publish(Change(...))              # every subscriber, in order, now
release()                                  # idempotent
```

## What it knows

- **Strong references, on purpose.** blinker, the obvious library, holds receivers weakly by
  default: `subscribe(lambda e: ...)` or a bound method of an object nobody else keeps is
  collected at once and stops receiving, with no error. Missed events are the failure a
  caller cannot see; a held reference is one it can release.
- **The release is part of the API.** A dropped handle leaves the callback attached for the
  process lifetime, and a second start on the same bus delivers every event twice.
  `subscribed()` is the spelling that cannot forget.
- **Delivery iterates a snapshot**, so a subscriber may release itself mid-delivery.
- **A raising subscriber reaches the publisher** and stops delivery. Isolating failures is a
  subscriber's decision, not the bus's.

Not blinker: blinker is keyed by signal name and sender, carries an untyped `**kwargs`
payload and is weak by default. This is one event type, typed, strong. No async, no
persistence, no topics. Stdlib only.

## Surface

| | |
|---|---|
| `EventBus[E]()` | an empty bus |
| `.subscribe(fn) -> release` | attach; `release()` is idempotent |
| `.subscribed(fn)` | context manager: attached for the block |
| `.publish(event)` | call every subscriber, in subscribe order, over a snapshot |
| `len(bus)` | live subscriptions |
