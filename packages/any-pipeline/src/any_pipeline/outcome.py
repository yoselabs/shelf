"""What a run leaves behind: a value or a Failed per item, and a record per stage run."""

from __future__ import annotations

from dataclasses import dataclass, field


class StageFailed(Exception):  # noqa: N818  carries a recorded failure up to the runner; never reaches the caller
    def __init__(self, stage: str, why: str, cause: Exception) -> None:
        super().__init__(f"{stage}: {why}")
        self.stage, self.why, self.cause = stage, why, cause


@dataclass(frozen=True, slots=True)
class Ok[T]:
    key: str
    value: T


@dataclass(frozen=True, slots=True)
class Failed:
    key: str
    stage: str
    why: str
    cause: Exception | None = field(default=None, compare=False, repr=False)  # the original, for a caller that needs its type


type Outcome[T] = Ok[T] | Failed


@dataclass(frozen=True, slots=True)
class StageRecord:
    key: str
    stage: str
    seconds: float
    tries: int
    ok: bool
    skipped: bool


@dataclass(frozen=True, slots=True)
class Report[T]:
    outcomes: tuple[Outcome[T], ...]
    records: tuple[StageRecord, ...]

    @property
    def done(self) -> tuple[Ok[T], ...]:
        return tuple(o for o in self.outcomes if isinstance(o, Ok))

    @property
    def failed(self) -> tuple[Failed, ...]:
        return tuple(o for o in self.outcomes if isinstance(o, Failed))
