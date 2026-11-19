"""The stored UTC stamp: one shape for a moment written into a file, `2026-11-20T07:05:09Z` (whole seconds, always UTC)."""

from __future__ import annotations

from datetime import UTC, datetime

_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utc_stamp(now: datetime) -> str:
    """`now` as a stored stamp; a datetime without a zone is refused, never guessed."""
    if now.tzinfo is None:
        message = "utc_stamp needs an aware datetime, got a naive one"
        raise ValueError(message)
    return now.astimezone(UTC).strftime(_FORMAT)


def parse_stamp(text: str) -> datetime:
    """The aware UTC datetime a stored stamp names; anything but the stored shape is refused."""
    message = f"not a stored stamp (want YYYY-MM-DDTHH:MM:SSZ): {text!r}"
    try:
        parsed = datetime.strptime(text, _FORMAT).replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError(message) from exc
    if utc_stamp(parsed) != text:  # strptime accepts unpadded fields; the stored shape is padded
        raise ValueError(message)
    return parsed
