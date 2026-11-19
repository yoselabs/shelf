from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import override

import pytest
from any_lease import Leases
from any_speech import AudioHasher, Diarized, Drain, DrainReport, Heard, Identity, Job, Pipeline, Slots, Speech, Transcript, Turn, Word
from any_speech.pipeline import audio_sha256
from any_speech.speech import claim_path
from any_speech.testing import FakeDiarizer, FakeTranscriber
from process_lock import ProcessLock

_NOW = "2026-11-19T10:00:00Z"


def _pipeline(transcriber: object | None = None, **kw: object) -> Pipeline:
    return Pipeline(transcriber or FakeTranscriber((Word("да", 0.0, 0.5),), **kw), None, probe=lambda _p: 1.0, now=lambda: _NOW)  # type: ignore[arg-type]  # fakes


def _speech(tmp_path: Path, pipeline: Pipeline | None = None, slots: Slots = Slots(2, 1, 3)) -> Speech:  # noqa: B008
    return Speech(pipeline or _pipeline(), tmp_path / "leases", slots)


def _job(tmp_path: Path, name: str, body: bytes = b"audio") -> Job:
    audio = tmp_path / f"{name}.m4a"
    audio.write_bytes(body)
    return Job(audio, tmp_path / f"{name}.speech.json")


async def _drain(jobs: list[Job], speech: Speech, workers: int = 1) -> DrainReport:
    return await Drain(scan=lambda: jobs, speech=speech, workers=workers).run()


async def test_transcribe_a_path_returns_the_transcript(tmp_path: Path) -> None:
    audio = _job(tmp_path, "a").audio
    assert (await _speech(tmp_path).transcribe(audio)).text == "да"


async def test_transcribe_with_out_stores_it_and_reuses_it(tmp_path: Path) -> None:
    job = _job(tmp_path, "a")
    speech = _speech(tmp_path)
    first = await speech.transcribe(job.audio, job.out)
    assert Transcript.load(job.out) == first
    calls: list[int] = []

    class Counting(FakeTranscriber):
        @override
        def transcribe(self, audio: Path) -> Heard:
            calls.append(1)
            return super().transcribe(audio)

    again = _speech(tmp_path, _pipeline(Counting((Word("да", 0.0, 0.5),))))
    assert await again.transcribe(job.audio, job.out) == first
    assert calls == []


async def test_each_audio_file_is_hashed_once_over_scans_and_runs(tmp_path: Path) -> None:
    hashed: list[Path] = []

    def count(audio: Path) -> str:
        hashed.append(audio)
        return audio_sha256(audio)

    pipeline = Pipeline(FakeTranscriber((Word("да", 0.0, 0.5),)), None, probe=lambda _p: 1.0, now=lambda: _NOW, hasher=AudioHasher(count))
    jobs = [_job(tmp_path, n) for n in "abc"]
    await _drain(jobs, _speech(tmp_path, pipeline), workers=2)
    await _drain(jobs, _speech(tmp_path, pipeline))
    assert sorted(p.name for p in hashed) == ["a.m4a", "b.m4a", "c.m4a"]


def test_a_changed_file_is_hashed_again(tmp_path: Path) -> None:
    hashed: list[Path] = []
    hasher = AudioHasher(lambda p: hashed.append(p) or "x")
    audio = _job(tmp_path, "a").audio
    hasher(audio)
    hasher(audio)
    audio.write_bytes(b"different and longer")
    hasher(audio)
    assert len(hashed) == 2


async def test_drain_writes_every_pending_transcript(tmp_path: Path) -> None:
    jobs = [_job(tmp_path, "a"), _job(tmp_path, "b")]
    report = await _drain(jobs, _speech(tmp_path), workers=2)
    assert sorted(p.name for p in report.done) == ["a.speech.json", "b.speech.json"]
    assert (await _drain(jobs, _speech(tmp_path))).done == []


async def test_a_job_whose_audio_or_model_changed_runs_again(tmp_path: Path) -> None:
    job = _job(tmp_path, "a")
    await _drain([job], _speech(tmp_path))
    job.audio.write_bytes(b"other audio")
    assert (await _drain([job], _speech(tmp_path))).done == [job.out]
    other = _pipeline(FakeTranscriber((Word("x", 0, 1),), model="m2"))
    assert (await _drain([job], _speech(tmp_path, other))).done == [job.out]


async def test_a_bad_file_does_not_stall_the_queue_and_is_skipped_until_it_changes(tmp_path: Path) -> None:
    bad, good = _job(tmp_path, "a", b"bad"), _job(tmp_path, "b", b"good")
    speech = _speech(tmp_path, _pipeline(fail_on=b"bad"))
    report = await _drain([bad, good], speech)
    assert (report.done, report.failed, bad.out.exists()) == ([good.out], [bad.out], False)
    assert (await _drain([bad], speech)).skipped == [bad.out]
    bad.audio.write_bytes(b"bad but longer")
    assert (await _drain([bad], _speech(tmp_path, _pipeline()))).done == [bad.out]


async def test_deleting_the_failure_record_retries(tmp_path: Path) -> None:
    bad = _job(tmp_path, "a", b"bad")
    speech = _speech(tmp_path, _pipeline(fail_on=b"bad"))
    await _drain([bad], speech)
    Path(f"{bad.out}.failed.json").unlink()
    assert (await _drain([bad], speech)).failed == [bad.out]


async def test_the_failure_record_names_the_error_and_the_file(tmp_path: Path) -> None:
    bad = _job(tmp_path, "a")
    await _drain([bad], _speech(tmp_path, _pipeline(error=RuntimeError("boom"))))
    text = Path(f"{bad.out}.failed.json").read_text(encoding="utf-8")
    assert "boom" in text
    assert str(bad.audio.stat().st_size) in text


class _Probe:
    """Counts how many transcribe calls are inside the engine at once; blocks each briefly so they overlap."""

    def __init__(self) -> None:
        self.identity = Identity("probe", "m", "r")
        self.active = 0
        self.peak = 0
        self._lock = threading.Lock()

    def transcribe(self, audio: Path) -> Heard:
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        threading.Event().wait(0.15)
        with self._lock:
            self.active -= 1
        return Heard((Word("да", 0.0, 0.5),), 0.1, 0.1)


@pytest.mark.parametrize(("slots", "workers", "expected_peak"), [(1, 4, 1), (2, 4, 2), (3, 3, 3)])
async def test_the_slot_count_is_the_most_transcriptions_running_at_once(
    tmp_path: Path, slots: int, workers: int, expected_peak: int
) -> None:
    probe = _Probe()
    jobs = [_job(tmp_path, f"f{i}", f"audio {i}".encode()) for i in range(6)]
    speech = _speech(tmp_path, _pipeline(probe), Slots(slots, 1, 4))
    report = await _drain(jobs, speech, workers=workers)
    assert len(report.done) == 6
    assert probe.peak == expected_peak


async def test_a_caller_waits_for_a_busy_slot_and_gets_in_when_it_frees(tmp_path: Path) -> None:
    leases = Leases(tmp_path / "leases")
    speech = _speech(tmp_path, slots=Slots(1, 1, 2))
    held = leases.acquire("any-speech-transcribe", 1, timeout=0)
    call = asyncio.ensure_future(speech.transcribe(_job(tmp_path, "a").audio))
    done, _ = await asyncio.wait({call}, timeout=0.3)
    assert not done, "the call waits while the slot is taken"
    held.release()
    assert (await asyncio.wait_for(call, 5)).text == "да"


async def test_two_callers_for_one_output_run_it_once(tmp_path: Path) -> None:
    probe = _Probe()
    job = _job(tmp_path, "a")
    speech = _speech(tmp_path, _pipeline(probe), Slots(2, 1, 3))
    await asyncio.gather(speech.transcribe(job.audio, job.out), speech.transcribe(job.audio, job.out))
    assert probe.peak == 1
    assert Transcript.load(job.out).text == "да"


class _Busy:
    """One counter shared by a transcriber and a diarizer, to see how many model calls overlap."""

    def __init__(self) -> None:
        self.active = 0
        self.peak = 0
        self.kinds_together: set[frozenset[str]] = set()
        self._now: list[str] = []
        self._lock = threading.Lock()

    def hold(self, kind: str) -> None:
        with self._lock:
            self._now.append(kind)
            self.peak = max(self.peak, len(self._now))
            self.kinds_together.add(frozenset(self._now))
        threading.Event().wait(0.15)
        with self._lock:
            self._now.remove(kind)


class _BusyTranscriber(FakeTranscriber):
    def __init__(self, busy: _Busy) -> None:
        super().__init__((Word("да", 0.0, 0.5),))
        self._busy = busy

    @override
    def transcribe(self, audio: Path) -> Heard:
        self._busy.hold("transcribe")
        return super().transcribe(audio)


class _BusyDiarizer(FakeDiarizer):
    def __init__(self, busy: _Busy) -> None:
        super().__init__([Turn(0.0, 1.0, "S1")])
        self._busy = busy

    @override
    def diarize(self, audio: Path) -> Diarized:
        self._busy.hold("diarize")
        return super().diarize(audio)


def _two_queue_speech(tmp_path: Path, busy: _Busy, slots: Slots) -> Speech:
    pipeline = Pipeline(_BusyTranscriber(busy), _BusyDiarizer(busy), probe=lambda _p: 1.0, now=lambda: _NOW)
    return Speech(pipeline, tmp_path / "leases", slots)


async def test_transcription_and_diarisation_overlap_on_separate_queues(tmp_path: Path) -> None:
    busy = _Busy()
    job = _job(tmp_path, "a")
    await _two_queue_speech(tmp_path, busy, Slots(1, 1, 2)).transcribe(job.audio)
    assert frozenset({"transcribe", "diarize"}) in busy.kinds_together


async def test_the_shared_bottleneck_caps_both_queues_together(tmp_path: Path) -> None:
    busy = _Busy()
    jobs = [_job(tmp_path, f"f{i}", f"audio {i}".encode()) for i in range(4)]
    await _drain(jobs, _two_queue_speech(tmp_path, busy, Slots(2, 2, 1)), workers=4)
    assert busy.peak == 1


class _Flaky(FakeDiarizer):
    """A diarizer that fails its first `failures` calls, then answers."""

    def __init__(self, failures: int) -> None:
        super().__init__([Turn(0.0, 1.0, "S1")])
        self.failures, self.calls = failures, 0

    @override
    def diarize(self, audio: Path) -> Diarized:
        self.calls += 1
        if self.calls <= self.failures:
            message = "model busy"
            raise RuntimeError(message)
        return super().diarize(audio)


def _with_diarizer(diarizer: FakeDiarizer) -> Pipeline:
    return Pipeline(FakeTranscriber((Word("да", 0.0, 0.5),)), diarizer, probe=lambda _p: 1.0, now=lambda: _NOW)


async def test_a_transcript_whose_diarizer_failed_is_redone_and_ends_ok(tmp_path: Path) -> None:
    job = _job(tmp_path, "a")
    diarizer = _Flaky(failures=1)
    speech = _speech(tmp_path, _with_diarizer(diarizer))
    assert (await _drain([job], speech)).done == [job.out]
    assert Transcript.load(job.out).provenance.diarizer["status"] == "failed"
    assert (await _drain([job], speech)).done == [job.out]
    stored = Transcript.load(job.out)
    assert (stored.provenance.diarizer["status"], stored.words[0].speaker) == ("ok", "S1")
    assert (await _drain([job], speech)).done == []


async def test_an_always_failing_diarizer_is_tried_three_times_then_left_with_no_speakers(tmp_path: Path) -> None:
    job = _job(tmp_path, "a")
    diarizer = _Flaky(failures=99)
    speech = _speech(tmp_path, _with_diarizer(diarizer))
    for _ in range(6):
        await _drain([job], speech)
    stored = Transcript.load(job.out)
    assert diarizer.calls == 3
    assert (stored.provenance.diarizer["status"], stored.provenance.diarizer["tries"], stored.words[0].speaker) == ("failed", "3", None)


async def test_a_cancelled_waiter_does_not_leave_the_claim_held(tmp_path: Path) -> None:
    speech = _speech(tmp_path)
    job = _job(tmp_path, "c")
    holder = ProcessLock.acquire(claim_path(job.out), timeout=None, reentrant=False)
    waiter = asyncio.create_task(speech.transcribe(job.audio, job.out))
    await asyncio.sleep(0.2)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    holder.release()
    await asyncio.sleep(0.5)
    again = await asyncio.wait_for(speech.transcribe(job.audio, job.out), timeout=5)
    assert again.text == "да"
