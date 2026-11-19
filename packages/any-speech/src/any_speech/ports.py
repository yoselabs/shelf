"""What an engine owes: the ports, and the identity every adapter states."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path

    from any_speech.format import Word
    from any_speech.words import Turn


@dataclass(frozen=True, slots=True)
class Identity:
    """Which engine and model ran, in which runtime, with which settings."""

    engine: str
    model: str
    runtime: str
    settings: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Heard:
    """What a Transcriber returns; the pipeline adds provenance and segments."""

    words: tuple[Word, ...]
    seconds: float
    peak_memory_gb: float | None


@dataclass(frozen=True, slots=True)
class Diarized:
    turns: tuple[Turn, ...]


@dataclass(frozen=True, slots=True)
class Voice:
    """A unit vector from one embedding model."""

    model: str
    vector: tuple[float, ...]

    def similarity(self, other: Voice) -> float:
        if other.model != self.model:
            message = f"voices from different models: {self.model} and {other.model}"
            raise ValueError(message)
        return sum(a * b for a, b in zip(self.vector, other.vector, strict=True))


class Transcriber(Protocol):
    identity: Identity

    def transcribe(self, audio: Path) -> Heard: ...


class Diarizer(Protocol):
    identity: Identity

    def diarize(self, audio: Path) -> Diarized: ...


class Embedder(Protocol):
    identity: Identity

    def embed(self, audio: Path, *, start: float | None = None, end: float | None = None) -> Voice: ...
