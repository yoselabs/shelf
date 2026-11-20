"""A voice embedding from sherpa-onnx's speaker models, on the CPU."""

from __future__ import annotations

import math
from array import array
from typing import TYPE_CHECKING, Any

from stream_proc import capture_bytes

from any_speech.ports import Identity, Voice

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_RATE = 16000
_DECODE_TIMEOUT = 3600.0


def decode_f32(audio: Path, start: float | None, end: float | None) -> list[float]:
    """The span of `audio` as 16 kHz mono float samples, through ffmpeg."""
    span = [] if start is None else ["-ss", str(start)]
    if end is not None:
        span += ["-t", str(end - (start or 0.0))]
    done = capture_bytes(
        ["ffmpeg", "-v", "error", *span, "-i", str(audio), "-f", "f32le", "-ac", "1", "-ar", str(_RATE), "-"], timeout=_DECODE_TIMEOUT
    )
    if done.exit != 0:
        # lossy-ok: display: a child's stderr tail goes into an error message
        message = f"ffmpeg failed on {audio} (exit {done.exit}): {done.err.decode('utf-8', 'replace').strip()[-300:]}"
        raise RuntimeError(message)
    samples = array("f")
    samples.frombytes(done.out)
    return list(samples)


def _extractor(model: Path) -> Any:
    import sherpa_onnx  # noqa: PLC0415  the engine is optional

    config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(model), num_threads=2)
    return sherpa_onnx.SpeakerEmbeddingExtractor(config)


class SherpaEmbedder:
    def __init__(
        self,
        model: Path,
        *,
        runtime: str,
        extractor: Callable[[Path], Any] = _extractor,  # Any: sherpa_onnx's untyped extractor, injected by tests
        decode: Callable[[Path, float | None, float | None], list[float]] = decode_f32,
    ) -> None:
        self.identity = Identity("sherpa-onnx", model.stem, runtime)
        self._model = model
        self._extractor_factory, self._decode = extractor, decode
        self._extractor: Any = None

    def embed(self, audio: Path, *, start: float | None = None, end: float | None = None) -> Voice:
        if self._extractor is None:
            self._extractor = self._extractor_factory(self._model)
        stream = self._extractor.create_stream()
        stream.accept_waveform(_RATE, self._decode(audio, start, end))
        stream.input_finished()
        vector = [float(x) for x in self._extractor.compute(stream)]
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return Voice(self.identity.model, tuple(x / norm for x in vector))
