"""One file in, one Transcript out: transcribe, label voices, segment, record provenance."""

from __future__ import annotations

import contextlib
import hashlib
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from any_speech.format import Provenance, Transcript, job_key
from any_speech.guard import DEFAULT_BUDGET_GB, check_peak
from any_speech.words import assign_speakers, segments_from_words

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager
    from pathlib import Path

    from any_speech.format import Word
    from any_speech.ports import Diarized, Diarizer, Transcriber

_CHUNK = 1 << 20


def _no_slot(kind: str) -> AbstractContextManager[object]:  # noqa: ARG001  every kind is free
    return contextlib.nullcontext()


def audio_sha256(audio: Path) -> str:
    h = hashlib.sha256()
    with audio.open("rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def probe_seconds(audio: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Pipeline:
    """A transcriber, an optional diarizer, a memory budget; the injected edges are the probe and the clock."""

    def __init__(
        self,
        transcriber: Transcriber,
        diarizer: Diarizer | None = None,
        *,
        budget_gb: float = DEFAULT_BUDGET_GB,
        probe: Callable[[Path], float] = probe_seconds,
        now: Callable[[], str] = _utc_now,
        slot: Callable[[str], AbstractContextManager[object]] = _no_slot,
    ) -> None:
        self.transcriber = transcriber
        self.diarizer = diarizer
        self.budget_gb = budget_gb
        self._probe = probe
        self._now = now
        self._slot = slot

    def gated(self, slot: Callable[[str], AbstractContextManager[object]]) -> Pipeline:
        """The same engines, each model call run inside `slot(kind)` (kind: transcribe or diarize)."""
        return Pipeline(self.transcriber, self.diarizer, budget_gb=self.budget_gb, probe=self._probe, now=self._now, slot=slot)

    def key_for(self, audio: Path) -> str:
        ident = self.transcriber.identity
        return job_key(audio_sha256(audio), ident.engine, ident.model, self._settings())

    def run(self, audio: Path) -> Transcript:
        digest = audio_sha256(audio)
        with ThreadPoolExecutor(max_workers=1) as pool:
            diarizing = pool.submit(self._diarize, audio) if self.diarizer is not None else None  # overlaps the transcription
            with self._slot("transcribe"):
                heard = self.transcriber.transcribe(audio)
            check_peak(heard.peak_memory_gb, self.budget_gb)
            words, diarizer = heard.words, {"status": "not_run"}
            if diarizing is not None:
                words, diarizer = self._label(heard.words, diarizing.result())
        ident = self.transcriber.identity
        provenance = Provenance(
            engine=ident.engine,
            model=ident.model,
            runtime=ident.runtime,
            settings=self._settings(),
            audio_sha256=digest,
            audio_seconds=self._probe(audio),
            seconds=heard.seconds,
            peak_memory_gb=heard.peak_memory_gb,
            diarizer=diarizer,
            made_at=self._now(),
        )
        labels = sorted({w.speaker for w in words if w.speaker}, key=_first_seen(words))
        return Transcript(
            words=words,
            segments=segments_from_words(words),
            speakers={label: f"voice {i}" for i, label in enumerate(labels, 1)},
            provenance=provenance,
        )

    def _settings(self) -> dict[str, object]:
        settings = dict(self.transcriber.identity.settings)
        if self.diarizer is not None:
            settings["diarizer"] = self.diarizer.identity.model
        return settings

    def _diarize(self, audio: Path) -> Diarized | Exception:
        assert self.diarizer is not None  # noqa: S101  only submitted with a diarizer
        try:
            with self._slot("diarize"):
                return self.diarizer.diarize(audio)
        except Exception as error:  # noqa: BLE001  a diarizer failure must not fail the transcript
            return error

    def _label(self, words: tuple[Word, ...], result: Diarized | Exception) -> tuple[tuple[Word, ...], dict[str, str]]:
        assert self.diarizer is not None  # noqa: S101  narrowed by the caller
        model = self.diarizer.identity.model
        if isinstance(result, Exception):
            return words, {"model": model, "status": "failed", "detail": str(result)[:300]}
        return assign_speakers(words, result.turns), {"model": model, "status": "ok"}


def _first_seen(words: tuple[Word, ...]) -> Callable[[str], float]:
    first: dict[str, float] = {}
    for w in words:
        if w.speaker and w.speaker not in first:
            first[w.speaker] = w.start
    return first.__getitem__
