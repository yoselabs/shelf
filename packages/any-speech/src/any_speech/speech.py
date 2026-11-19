"""The front door: give a path, get a Transcript. Concurrency is a counted pool of slots shared by the whole machine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from any_lease import Leases
from process_lock import ProcessLock

from any_speech.format import Transcript

if TYPE_CHECKING:
    from contextlib import AbstractContextManager
    from pathlib import Path

    from any_speech.pipeline import Pipeline


@dataclass(frozen=True, slots=True)
class Slots:
    """How many model calls of each kind run at once on this machine, across every process."""

    transcribe: int = 2
    diarize: int = 1
    total: int = 3
    """The shared bottleneck: every model call, of either kind, also takes one of these. Set it below
    transcribe + diarize when the machine cannot carry all of them at once."""


def claim_path(out: Path) -> Path:
    return out.with_name(out.name + ".claim")


def is_current(out: Path, pipeline: Pipeline, audio: Path) -> bool:
    try:
        return Transcript.load(out).provenance.key == pipeline.key_for(audio)
    except (OSError, ValueError, KeyError):
        return False


class Speech:
    """`Speech(pipeline, leases_root).transcribe(path)`: waits for a free slot, runs, optionally stores."""

    def __init__(self, pipeline: Pipeline, leases_root: Path, slots: Slots = Slots()) -> None:  # noqa: B008  frozen value
        self._leases = Leases(leases_root)
        self._slots = slots
        self.pipeline = pipeline.gated(self._slot)
        for name, limit in self._pools().items():
            self._leases.declare(name, limit)

    def _pools(self) -> dict[str, int]:
        s = self._slots
        return {"any-speech-transcribe": s.transcribe, "any-speech-diarize": s.diarize, "any-speech-total": s.total}

    def _slot(self, kind: str) -> AbstractContextManager[object]:
        pools = self._pools()
        wants = {f"any-speech-{kind}": pools[f"any-speech-{kind}"], "any-speech-total": pools["any-speech-total"]}
        return self._leases.acquire_all(wants, label=f"any-speech {kind}")

    def transcribe(self, audio: Path, out: Path | None = None) -> Transcript:
        """The transcript of `audio`. With `out`: a current file there is returned as is, else the result is saved there.

        Two callers asking for the same `out` run it once: the second waits, then finds it done.
        """
        if out is None:
            return self.pipeline.run(audio)
        with ProcessLock.acquire(claim_path(out), timeout=None, reentrant=False):
            return self.fulfil(audio, out)

    def fulfil(self, audio: Path, out: Path) -> Transcript:
        """As `transcribe(audio, out)` for a caller that already holds the claim on `out`."""
        if is_current(out, self.pipeline, audio):
            return Transcript.load(out)
        transcript = self.pipeline.run(audio)
        transcript.save(out)
        return transcript
