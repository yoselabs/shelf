"""One file in, one Transcript out: transcribe, label voices, segment, record provenance."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from any_clock import utc_stamp
from any_pipeline import Limit, Stage, blocking, gather, run_one
from content_digest import digest_file
from stream_proc import capture

from any_speech.format import Provenance, Transcript, job_key, speakers_of
from any_speech.guard import DEFAULT_BUDGET_GB, check_peak
from any_speech.words import assign_speakers, segments_from_words

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager
    from pathlib import Path

    from any_pipeline import Flow

    from any_speech.format import Word
    from any_speech.ports import Diarizer, Heard, Transcriber
    from any_speech.words import Turn

_PROBE_TIMEOUT = 120.0
ENGINE_LIMIT = Limit(calls=4, seconds=3600.0, tries=1)  # the machine-wide cap is the leases'; this one only bounds a single run
ASSEMBLE_LIMIT = Limit(calls=4, seconds=600.0, tries=1)


@dataclass(frozen=True, slots=True)
class Hearing:
    """The path travels with what was heard: assembly needs the audio's hash and length."""

    audio: Path
    heard: Heard


@dataclass(frozen=True, slots=True)
class Voices:
    """Turns, or the reason there are none: a diarizer failure is a value here, never an exception."""

    turns: tuple[Turn, ...]
    error: str | None


def _no_slot(kind: str) -> AbstractContextManager[object]:  # noqa: ARG001  every kind is free
    return contextlib.nullcontext()


def audio_sha256(audio: Path) -> str:
    return digest_file(audio, length=64)


def probe_seconds(audio: Path) -> float:
    out = capture(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio)], timeout=_PROBE_TIMEOUT)
    if out.exit != 0:
        message = f"ffprobe failed on {audio} (exit {out.exit}): {out.err.strip()[-300:]}"
        raise RuntimeError(message)
    return float(out.out.strip())


def _utc_now() -> str:
    return utc_stamp(datetime.now(UTC))


class AudioHasher:
    """The audio's digest, remembered by (path, size, modified time): a drain scans the same files many times."""

    def __init__(self, hash_file: Callable[[Path], str] = audio_sha256) -> None:
        self._hash_file = hash_file
        self._seen: dict[tuple[str, int, int], str] = {}

    def __call__(self, audio: Path) -> str:
        stat = audio.stat()
        key = (str(audio.resolve()), stat.st_size, stat.st_mtime_ns)
        if key not in self._seen:
            self._seen[key] = self._hash_file(audio)
        return self._seen[key]


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
        hasher: Callable[[Path], str] | None = None,
    ) -> None:
        self.transcriber = transcriber
        self.diarizer = diarizer
        self.budget_gb = budget_gb
        self._probe = probe
        self._now = now
        self._slot = slot
        self._hash = AudioHasher() if hasher is None else hasher
        self._flow = self._build()

    def gated(self, slot: Callable[[str], AbstractContextManager[object]]) -> Pipeline:
        """The same engines, each model call run inside `slot(kind)` (kind: transcribe or diarize)."""
        engines = (self.transcriber, self.diarizer)
        return Pipeline(*engines, budget_gb=self.budget_gb, probe=self._probe, now=self._now, slot=slot, hasher=self._hash)

    def key_for(self, audio: Path) -> str:
        ident = self.transcriber.identity
        return job_key(self._hash(audio), ident.engine, ident.model, self._settings())

    async def run(self, audio: Path) -> Transcript:
        """Hear (and diarize, at the same time), then assemble. A failure is raised as the engine's own exception."""
        return await run_one(self._flow, audio, key=str(audio))

    def _build(self) -> Flow[Path, Transcript]:
        hear = Stage("hear", blocking(self._hear), ENGINE_LIMIT)
        if self.diarizer is None:
            return hear >> Stage("assemble", blocking(self._assemble_words), ASSEMBLE_LIMIT)
        # a diarizer failure becomes a Voices with no turns and the reason; it never fails the transcript
        diarize = Stage("diarize", blocking(self._diarize), ENGINE_LIMIT).otherwise(lambda why: Voices((), why))
        return gather(hear, diarize) >> Stage("assemble", blocking(self._assemble), ASSEMBLE_LIMIT)

    def _hear(self, audio: Path) -> Hearing:
        with self._slot("transcribe"):
            heard = self.transcriber.transcribe(audio)
        check_peak(heard.peak_memory_gb, self.budget_gb)
        return Hearing(audio, heard)

    def _diarize(self, audio: Path) -> Voices:
        assert self.diarizer is not None  # noqa: S101  only built with a diarizer
        with self._slot("diarize"):
            return Voices(self.diarizer.diarize(audio).turns, None)

    def _assemble_words(self, hearing: Hearing) -> Transcript:
        return self._transcript(hearing, hearing.heard.words, {"status": "not_run"})

    def _assemble(self, both: tuple[Hearing, Voices]) -> Transcript:
        hearing, voices = both
        assert self.diarizer is not None  # noqa: S101  only built with a diarizer
        model = self.diarizer.identity.model
        if voices.error is not None:
            return self._transcript(hearing, hearing.heard.words, {"model": model, "status": "failed", "detail": voices.error[:300]})
        words = assign_speakers(hearing.heard.words, voices.turns)
        return self._transcript(hearing, words, {"model": model, "status": "ok"})

    def _transcript(self, hearing: Hearing, words: tuple[Word, ...], diarizer: dict[str, str]) -> Transcript:
        ident, heard = self.transcriber.identity, hearing.heard
        provenance = Provenance(
            engine=ident.engine,
            model=ident.model,
            runtime=ident.runtime,
            settings=self._settings(),
            audio_sha256=self._hash(hearing.audio),
            audio_seconds=self._probe(hearing.audio),
            seconds=heard.seconds,
            peak_memory_gb=heard.peak_memory_gb,
            diarizer=diarizer,
            made_at=self._now(),
        )
        labels = sorted({w.speaker for w in words if w.speaker}, key=_first_seen(words))
        return Transcript(
            words=words,
            segments=segments_from_words(words),
            speakers=speakers_of(words, {label: f"voice {i}" for i, label in enumerate(labels, 1)}),
            provenance=provenance,
        )

    def _settings(self) -> dict[str, object]:
        settings = dict(self.transcriber.identity.settings)
        if self.diarizer is not None:
            settings["diarizer"] = self.diarizer.identity.model
        return settings


def _first_seen(words: tuple[Word, ...]) -> Callable[[str], float]:
    first: dict[str, float] = {}
    for w in words:
        if w.speaker and w.speaker not in first:
            first[w.speaker] = w.start
    return first.__getitem__
