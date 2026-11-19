"""Parakeet TDT on MLX (the parakeet-mlx package), in this process, chunked and cache-capped."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from any_speech.adapters._mlx import CACHE_MB, Memory, MlxMemory
from any_speech.ports import Heard, Identity
from any_speech.words import Piece, words_from_pieces

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

MODEL = "mlx-community/parakeet-tdt-0.6b-v3"


def _load(model: str) -> Any:
    from parakeet_mlx import from_pretrained  # noqa: PLC0415  the engine is optional

    return from_pretrained(model)


class ParakeetMlx:
    """Unchunked, an 8.7 minute file peaked at 14.5 GB; chunking at 120 s with 15 s overlap holds about 3.3 GB."""

    def __init__(
        self,
        model: str = MODEL,
        *,
        runtime: str,
        chunk_seconds: float = 120.0,
        overlap_seconds: float = 15.0,
        loader: Callable[[str], Any] = _load,
        memory: Callable[[], Memory] = MlxMemory,
    ) -> None:
        self.identity = Identity("parakeet-mlx", model, runtime, {"chunk_seconds": chunk_seconds, "overlap_seconds": overlap_seconds})
        self._model_id, self._chunk, self._overlap = model, chunk_seconds, overlap_seconds
        self._loader, self._memory_factory = loader, memory
        self._model: Any = None
        self._memory: Memory | None = None

    def transcribe(self, audio: Path) -> Heard:
        if self._model is None:
            self._memory = self._memory_factory()
            self._memory.cap(CACHE_MB)
            self._model = self._loader(self._model_id)
        assert self._memory is not None  # noqa: S101  set with the model
        self._memory.reset_peak()
        started = time.monotonic()
        result = self._model.transcribe(str(audio), chunk_duration=self._chunk, overlap_duration=self._overlap)
        pieces = [Piece(t.text, t.start, t.end) for s in result.sentences for t in s.tokens]
        seconds, peak = time.monotonic() - started, self._memory.peak_gb()
        self._memory.clear()
        return Heard(words_from_pieces(pieces), seconds, peak)
