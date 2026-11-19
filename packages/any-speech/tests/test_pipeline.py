from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from any_speech import MemoryBudgetError, Pipeline, Turn, Word
from any_speech.testing import FakeDiarizer, FakeTranscriber

if TYPE_CHECKING:
    from pathlib import Path

_WORDS = (Word("ну", 0.0, 0.5), Word("да", 0.6, 1.0), Word("нет", 6.0, 6.5))


def _audio(tmp_path: Path, body: bytes = b"audio") -> Path:
    audio = tmp_path / "a.m4a"
    audio.write_bytes(body)
    return audio


def _pipeline(*, diarizer: FakeDiarizer | None = None, peak: float = 1.0, budget: float = 4.0) -> Pipeline:
    return Pipeline(
        FakeTranscriber(_WORDS, peak_memory_gb=peak),
        diarizer,
        budget_gb=budget,
        probe=lambda _p: 7.0,
        now=lambda: "2026-11-19T10:00:00Z",
    )


def test_run_records_provenance_and_segments(tmp_path: Path) -> None:
    t = _pipeline().run(_audio(tmp_path))
    assert t.text == "ну да нет"
    assert [s.text for s in t.segments] == ["ну да", "нет"]
    p = t.provenance
    assert (p.engine, p.audio_seconds, p.peak_memory_gb, p.source) == ("fake", 7.0, 1.0, "local")
    assert p.diarizer == {"status": "not_run"}
    assert len(p.audio_sha256) == 64


def test_diarizer_labels_words_and_lists_speakers(tmp_path: Path) -> None:
    diarizer = FakeDiarizer([Turn(0.0, 2.0, "S1"), Turn(5.0, 8.0, "S2")])
    t = _pipeline(diarizer=diarizer).run(_audio(tmp_path))
    assert [w.speaker for w in t.words] == ["S1", "S1", "S2"]
    assert set(t.speakers) == {"S1", "S2"}
    assert t.provenance.diarizer == {"model": "fake-diarizer", "status": "ok"}


def test_a_diarizer_failure_never_fails_the_transcript(tmp_path: Path) -> None:
    t = _pipeline(diarizer=FakeDiarizer(error=RuntimeError("model missing"))).run(_audio(tmp_path))
    assert t.text == "ну да нет"
    assert [w.speaker for w in t.words] == [None, None, None]
    assert t.provenance.diarizer == {"model": "fake-diarizer", "status": "failed", "detail": "model missing"}


def test_a_peak_over_the_budget_is_a_failure(tmp_path: Path) -> None:
    with pytest.raises(MemoryBudgetError, match=r"5\.2"):
        _pipeline(peak=5.2, budget=4.0).run(_audio(tmp_path))


def test_the_key_before_running_matches_the_one_recorded(tmp_path: Path) -> None:
    audio = _audio(tmp_path)
    pipeline = _pipeline()
    assert pipeline.key_for(audio) == pipeline.run(audio).provenance.key


def test_a_different_audio_gets_a_different_key(tmp_path: Path) -> None:
    pipeline = _pipeline()
    assert pipeline.key_for(_audio(tmp_path, b"one")) != pipeline.key_for(_audio(tmp_path, b"two"))
