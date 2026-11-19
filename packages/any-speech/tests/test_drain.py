from __future__ import annotations

import threading
from pathlib import Path
from typing import override

import pytest
from any_lease import Leases
from any_speech import Diarized, Drain, Heard, Identity, Job, Pipeline, Slots, Speech, Transcript, Turn, Word
from any_speech.testing import FakeDiarizer, FakeTranscriber

_NOW = "2026-11-19T10:00:00Z"


def _pipeline(transcriber: object | None = None, **kw: object) -> Pipeline:
    return Pipeline(transcriber or FakeTranscriber((Word("да", 0.0, 0.5),), **kw), None, probe=lambda _p: 1.0, now=lambda: _NOW)  # type: ignore[arg-type]  # fakes


def _speech(tmp_path: Path, pipeline: Pipeline | None = None, slots: Slots = Slots(2, 1)) -> Speech:  # noqa: B008
    return Speech(pipeline or _pipeline(), tmp_path / "leases", slots)


def _job(tmp_path: Path, name: str, body: bytes = b"audio") -> Job:
    audio = tmp_path / f"{name}.m4a"
    audio.write_bytes(body)
    return Job(audio, tmp_path / f"{name}.speech.json")


def _drain(jobs: list[Job], speech: Speech, workers: int = 1) -> Drain:
    return Drain(scan=lambda: jobs, speech=speech, workers=workers)


def test_transcribe_a_path_returns_the_transcript(tmp_path: Path) -> None:
    audio = _job(tmp_path, "a").audio
    assert _speech(tmp_path).transcribe(audio).text == "да"


def test_transcribe_with_out_stores_it_and_reuses_it(tmp_path: Path) -> None:
    job = _job(tmp_path, "a")
    speech = _speech(tmp_path)
    first = speech.transcribe(job.audio, job.out)
    assert Transcript.load(job.out) == first
    calls: list[int] = []

    class Counting(FakeTranscriber):
        @override
        def transcribe(self, audio: Path) -> Heard:
            calls.append(1)
            return super().transcribe(audio)

    again = _speech(tmp_path, _pipeline(Counting((Word("да", 0.0, 0.5),))))
    assert again.transcribe(job.audio, job.out) == first
    assert calls == []


def test_drain_writes_every_pending_transcript(tmp_path: Path) -> None:
    jobs = [_job(tmp_path, "a"), _job(tmp_path, "b")]
    report = _drain(jobs, _speech(tmp_path), workers=2).run()
    assert sorted(p.name for p in report.done) == ["a.speech.json", "b.speech.json"]
    assert _drain(jobs, _speech(tmp_path)).run().done == []


def test_a_job_whose_audio_or_model_changed_runs_again(tmp_path: Path) -> None:
    job = _job(tmp_path, "a")
    _drain([job], _speech(tmp_path)).run()
    job.audio.write_bytes(b"other audio")
    assert _drain([job], _speech(tmp_path)).run().done == [job.out]
    other = _pipeline(FakeTranscriber((Word("x", 0, 1),), model="m2"))
    assert _drain([job], _speech(tmp_path, other)).run().done == [job.out]


def test_a_bad_file_does_not_stall_the_queue_and_is_skipped_until_it_changes(tmp_path: Path) -> None:
    bad, good = _job(tmp_path, "a", b"bad"), _job(tmp_path, "b", b"good")
    speech = _speech(tmp_path, _pipeline(fail_on=b"bad"))
    report = _drain([bad, good], speech).run()
    assert (report.done, report.failed, bad.out.exists()) == ([good.out], [bad.out], False)
    assert _drain([bad], speech).run().skipped == [bad.out]
    bad.audio.write_bytes(b"bad but longer")
    assert _drain([bad], _speech(tmp_path, _pipeline())).run().done == [bad.out]


def test_deleting_the_failure_record_retries(tmp_path: Path) -> None:
    bad = _job(tmp_path, "a", b"bad")
    speech = _speech(tmp_path, _pipeline(fail_on=b"bad"))
    _drain([bad], speech).run()
    Path(f"{bad.out}.failed.json").unlink()
    assert _drain([bad], speech).run().failed == [bad.out]


def test_the_failure_record_names_the_error_and_the_file(tmp_path: Path) -> None:
    bad = _job(tmp_path, "a")
    _drain([bad], _speech(tmp_path, _pipeline(error=RuntimeError("boom")))).run()
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
def test_the_slot_count_is_the_most_transcriptions_running_at_once(tmp_path: Path, slots: int, workers: int, expected_peak: int) -> None:
    probe = _Probe()
    jobs = [_job(tmp_path, f"f{i}", f"audio {i}".encode()) for i in range(6)]
    speech = _speech(tmp_path, _pipeline(probe), Slots(slots, 1))
    report = _drain(jobs, speech, workers=workers).run()
    assert len(report.done) == 6
    assert probe.peak == expected_peak


def test_a_caller_waits_for_a_busy_slot_and_gets_in_when_it_frees(tmp_path: Path) -> None:
    leases = Leases(tmp_path / "leases")
    speech = _speech(tmp_path, slots=Slots(1, 1))
    held = leases.acquire("any-speech-transcribe", 1, timeout=0)
    result: list[Transcript] = []
    worker = threading.Thread(target=lambda: result.append(speech.transcribe(_job(tmp_path, "a").audio)))
    worker.start()
    worker.join(0.3)
    assert worker.is_alive(), "the call waits while the slot is taken"
    held.release()
    worker.join(5)
    assert [t.text for t in result] == ["да"]


def test_two_callers_for_one_output_run_it_once(tmp_path: Path) -> None:
    probe = _Probe()
    job = _job(tmp_path, "a")
    speech = _speech(tmp_path, _pipeline(probe), Slots(2, 1))
    threads = [threading.Thread(target=speech.transcribe, args=(job.audio, job.out)) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
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


def test_transcription_and_diarisation_overlap_on_separate_queues(tmp_path: Path) -> None:
    busy = _Busy()
    job = _job(tmp_path, "a")
    _two_queue_speech(tmp_path, busy, Slots(1, 1, 2)).transcribe(job.audio)
    assert frozenset({"transcribe", "diarize"}) in busy.kinds_together


def test_the_shared_bottleneck_caps_both_queues_together(tmp_path: Path) -> None:
    busy = _Busy()
    jobs = [_job(tmp_path, f"f{i}", f"audio {i}".encode()) for i in range(4)]
    _drain(jobs, _two_queue_speech(tmp_path, busy, Slots(2, 2, 1)), workers=4).run()
    assert busy.peak == 1
