"""Drain a folder of audio: every pending job runs, `workers` at a time, inside the machine's slots."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Lock
from typing import TYPE_CHECKING

from process_lock import LockHeldError, ProcessLock

from any_speech.failures import is_known_failure, record
from any_speech.speech import claim_path, is_current

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from any_speech.speech import Speech


@dataclass(frozen=True, slots=True)
class Job:
    audio: Path
    out: Path


@dataclass(slots=True)
class DrainReport:
    done: list[Path] = field(default_factory=list)
    failed: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)


class Drain:
    """`scan` lists the jobs that exist now. A worker claims one (a lock beside its output, so two workers or two
    processes never take the same file), runs it, and rescans until nothing is left to claim."""

    def __init__(self, *, scan: Callable[[], Sequence[Job]], speech: Speech, workers: int = 1) -> None:
        self._scan = scan
        self._speech = speech
        self._workers = workers
        self._report = DrainReport()
        self._report_lock = Lock()

    def run(self) -> DrainReport:
        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            for future in [pool.submit(self._work) for _ in range(self._workers)]:
                future.result()
        return self._report

    def _work(self) -> None:
        while (claimed := self._claim()) is not None:
            job, lock = claimed
            try:
                self._run_one(job)
            finally:
                lock.release()

    def _claim(self) -> tuple[Job, ProcessLock] | None:
        for job in self._scan():
            if is_known_failure(job.out, job.audio):
                self._note(self._report.skipped, job.out, unless=self._report.failed)
            elif not is_current(job.out, self._speech.pipeline, job.audio):
                try:
                    lock = ProcessLock.acquire(claim_path(job.out), timeout=0, reentrant=False)
                except LockHeldError:
                    continue  # another worker has it
                if is_current(job.out, self._speech.pipeline, job.audio):  # finished while we asked
                    lock.release()
                    continue
                return job, lock
        return None

    def _run_one(self, job: Job) -> None:
        try:
            self._speech.fulfil(job.audio, job.out)
        except Exception as error:  # noqa: BLE001  one bad file must not stop the queue for every run
            record(job.out, job.audio, error)
            self._note(self._report.failed, job.out)
        else:
            self._note(self._report.done, job.out)

    def _note(self, target: list[Path], path: Path, *, unless: list[Path] | None = None) -> None:
        with self._report_lock:
            if path not in target and path not in (unless or []):
                target.append(path)
