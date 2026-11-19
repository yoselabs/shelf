"""Scripted engines for a consumer's own tests; no model, no process."""

from __future__ import annotations

from typing import TYPE_CHECKING

from any_speech.ports import Diarized, Heard, Identity, Voice

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from any_speech.format import Word
    from any_speech.words import Turn


class FakeTranscriber:
    """Returns the scripted words; raises `error`, or when the audio holds `fail_on`."""

    def __init__(
        self,
        words: Sequence[Word],
        *,
        model: str = "m1",
        peak_memory_gb: float | None = 0.1,
        error: Exception | None = None,
        fail_on: bytes | None = None,
    ) -> None:
        self.identity = Identity("fake", model, "fake-runtime", {"language": "ru"})
        self._words = tuple(words)
        self._peak = peak_memory_gb
        self._error = error
        self._fail_on = fail_on

    def transcribe(self, audio: Path) -> Heard:
        if self._error is not None:
            raise self._error
        if self._fail_on is not None and self._fail_on in audio.read_bytes():
            message = "scripted failure"
            raise RuntimeError(message)
        return Heard(self._words, 0.01, self._peak)


class FakeDiarizer:
    def __init__(self, turns: Sequence[Turn] = (), *, error: Exception | None = None) -> None:
        self.identity = Identity("fake", "fake-diarizer", "fake-runtime")
        self._turns = tuple(turns)
        self._error = error

    def diarize(self, audio: Path) -> Diarized:  # noqa: ARG002  scripted, ignores the audio
        if self._error is not None:
            raise self._error
        return Diarized(self._turns)


class FakeEmbedder:
    """Embeds to the scripted vector for each audio file name."""

    def __init__(self, vectors: dict[str, tuple[float, ...]]) -> None:
        self.identity = Identity("fake", "fake-embedder", "fake-runtime")
        self._vectors = vectors

    def embed(self, audio: Path, *, start: float | None = None, end: float | None = None) -> Voice:  # noqa: ARG002
        return Voice("fake-embedder", self._vectors[audio.name])
