"""The front door: give a path, get a Transcript. Concurrency is a counted pool of slots shared by the whole machine."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from any_lease import Leases
from process_lock import ProcessLock

from any_speech.format import Transcript

if TYPE_CHECKING:
    from contextlib import AbstractContextManager
    from pathlib import Path

    from any_speech.pipeline import Pipeline


_GB_PER_CALL = 12  # one model call per 12 GB of memory leaves room for the apps the machine also runs
_MAX_TOTAL = 4


@dataclass(frozen=True, slots=True)
class Slots:
    """How many model calls of each kind run at once on this machine, across every process."""

    transcribe: int
    diarize: int
    total: int
    """The shared bottleneck: every model call, of either kind, also takes one of these. Set it below
    transcribe + diarize when the machine cannot carry all of them at once."""

    @classmethod
    def auto(cls, *, ram_bytes: int | None = None) -> Slots:
        """Sized from the machine: one call per 12 GB of memory, at most 4 together, half as many diarizations."""
        ram = ram_bytes if ram_bytes is not None else os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        total = min(_MAX_TOTAL, max(1, ram // (_GB_PER_CALL * 2**30)))
        return cls(transcribe=total, diarize=max(1, total // 2), total=total)


def default_out(audio: Path) -> Path:
    return audio.with_name(audio.stem + ".speech.json")


async def _acquire_claim(target: Path) -> ProcessLock:
    """Take the claim on `target`. A waiter cancelled mid-wait still gets the thread's lock released once it lands."""
    acquiring = asyncio.ensure_future(asyncio.to_thread(ProcessLock.acquire, claim_path(target), timeout=None, reentrant=False))
    try:
        return await asyncio.shield(acquiring)
    except asyncio.CancelledError:
        acquiring.add_done_callback(lambda done: done.cancelled() or done.exception() or done.result().release())
        raise


def claim_path(out: Path) -> Path:
    return out.with_name(out.name + ".claim")


MAX_DIARIZER_TRIES = 3  # a transient diarizer failure is retried; a permanent one stops here and leaves speaker None


async def is_current(out: Path, pipeline: Pipeline, audio: Path) -> bool:
    try:
        stored = await asyncio.to_thread(Transcript.load, out)
        if stored.provenance.key != await asyncio.to_thread(pipeline.key_for, audio):
            return False
    except (OSError, ValueError, KeyError):
        return False
    return not (pipeline.diarizer is not None and _tries_left(stored))


def _failed_tries(transcript: Transcript) -> int:
    d = transcript.provenance.diarizer
    return int(d.get("tries", "1")) if d.get("status") == "failed" else 0


def _tries_left(transcript: Transcript) -> bool:
    return 0 < _failed_tries(transcript) < MAX_DIARIZER_TRIES


class Speech:
    """`Speech(pipeline, leases_root).transcribe(path)`: waits for a free slot, runs, optionally stores."""

    def __init__(self, pipeline: Pipeline, leases_root: Path, slots: Slots) -> None:
        self._leases = Leases(leases_root)
        self.slots = slots
        self.pipeline = pipeline.gated(self._slot)
        for name, limit in self._pools().items():
            self._leases.declare(name, limit)

    def _pools(self) -> dict[str, int]:
        s = self.slots
        return {"any-speech-transcribe": s.transcribe, "any-speech-diarize": s.diarize, "any-speech-total": s.total}

    def _slot(self, kind: str) -> AbstractContextManager[object]:
        pools = self._pools()
        wants = {f"any-speech-{kind}": pools[f"any-speech-{kind}"], "any-speech-total": pools["any-speech-total"]}
        return self._leases.acquire_all(wants, label=f"any-speech {kind}")

    async def run(self, audio: Path) -> Transcript:
        """The transcript of `audio` as a value, nothing stored."""
        return await self.pipeline.run(audio)

    async def transcribe(self, audio: Path, out: Path | None = None) -> Transcript:
        """The transcript of `audio`, stored in one file (default: beside the audio, `<stem>.speech.json`).

        A current file there is returned as is. Two callers for the same file run it once: the second waits, then finds it done.
        """
        target = out if out is not None else default_out(audio)
        lock = await _acquire_claim(target)
        try:
            return await self.fulfil(audio, target)
        finally:
            lock.release()

    async def fulfil(self, audio: Path, out: Path) -> Transcript:
        """As `transcribe(audio, out)` for a caller that already holds the claim on `out`."""
        if await is_current(out, self.pipeline, audio):
            return await asyncio.to_thread(Transcript.load, out)
        transcript = self._counted(await self.pipeline.run(audio), await self._tries_so_far(out, audio))
        await asyncio.to_thread(transcript.save, out)
        return transcript

    async def _tries_so_far(self, out: Path, audio: Path) -> int:
        try:
            stored = await asyncio.to_thread(Transcript.load, out)
            same = stored.provenance.key == await asyncio.to_thread(self.pipeline.key_for, audio)
        except (OSError, ValueError, KeyError):
            return 0
        return _failed_tries(stored) if same else 0

    @staticmethod
    def _counted(transcript: Transcript, before: int) -> Transcript:
        diarizer = transcript.provenance.diarizer
        if diarizer.get("status") != "failed":
            return transcript
        counted = {**diarizer, "tries": str(before + 1)}
        return replace(transcript, provenance=replace(transcript.provenance, diarizer=counted))
