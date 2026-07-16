"""`Raises(...)` — the `Annotated`-return marker declaring a function's error closure."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Any, get_args, get_origin, get_type_hints

from a2effect.errors import AppError

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class Raises:
    """A marker declaring a function's error closure.

    Placed in an `Annotated[...]` return type, it lists the `AppError` subclasses a
    function may raise — readable by lint and by :meth:`flatten_from_annotation`.
    """

    types: tuple[type, ...] = field(default=())

    def __init__(self, *types: type) -> None:
        object.__setattr__(self, "types", tuple(types))

    @staticmethod
    def flatten_from_annotation(fn: Callable[..., Any]) -> tuple[type[AppError], ...]:
        """Collect the `AppError` types declared in `fn`'s `Annotated` return `Raises`."""
        # Forward refs, unresolved typing, or NameError in annotations all
        # mean "no readable raises closure"; lint reports separately.
        try:
            hints = get_type_hints(fn, include_extras=True)
        except Exception:  # noqa: BLE001
            return ()
        annotation = hints.get("return")
        if annotation is None:
            return ()
        return Raises._flatten(annotation)

    @staticmethod
    def _flatten(annotation: Any) -> tuple[type[AppError], ...]:
        if get_origin(annotation) is not Annotated:
            return ()
        _, *metadata = get_args(annotation)
        collected: list[type] = []
        seen: set[type] = set()
        for meta in metadata:
            if isinstance(meta, Raises):
                for t in meta.types:
                    if t not in seen:
                        seen.add(t)
                        collected.append(t)
        for t in collected:
            if not (isinstance(t, type) and issubclass(t, AppError)):
                msg = (
                    f"Raises(...) member {t!r} is not an AppError subclass; "
                    f"subclass a2effect.AppError or translate via an enricher / raises_as"
                )
                raise TypeError(msg)
        return tuple(collected)  # ty: ignore[invalid-return-type] - each member is issubclass-checked AppError above
