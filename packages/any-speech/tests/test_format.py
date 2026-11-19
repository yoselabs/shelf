from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from any_speech import (
    FORMAT_VERSION,
    Provenance,
    Segment,
    Transcript,
    UnknownVersionError,
    Word,
    job_key,
)

if TYPE_CHECKING:
    from pathlib import Path


def _provenance(**over: object) -> Provenance:
    base = {
        "engine": "fake",
        "model": "m1",
        "runtime": "r1",
        "settings": {"language": "ru"},
        "audio_sha256": "ab" * 32,
        "audio_seconds": 12.5,
        "seconds": 1.5,
        "peak_memory_gb": 0.5,
        "diarizer": {"status": "not_run"},
        "made_at": "2026-11-19T10:00:00Z",
        "source": "local",
    }
    return Provenance(**{**base, **over})  # type: ignore[arg-type]  # table of overrides, checked by the round trip


def _transcript() -> Transcript:
    return Transcript(
        words=(Word("ну", 0.0, 0.2, 0.9, "S1"), Word("да", 0.3, 0.5, None, None)),
        segments=(Segment(0.0, 0.5, "ну да", "S1"),),
        speakers={"S1": "voice 1"},
        provenance=_provenance(),
    )


def test_round_trip_through_a_file_keeps_every_field(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    original = _transcript()
    original.save(path)
    assert Transcript.load(path) == original


def test_json_names_the_version_and_keeps_russian_unescaped(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    _transcript().save(path)
    raw = path.read_text(encoding="utf-8")
    assert json.loads(raw)["version"] == FORMAT_VERSION
    assert "ну да" in raw


def test_a_reader_refuses_a_version_it_does_not_know(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    path.write_text(json.dumps({**_transcript().to_json(), "version": FORMAT_VERSION + 1}), encoding="utf-8")
    with pytest.raises(UnknownVersionError):
        Transcript.load(path)


def test_captions_are_a_source_kind() -> None:
    caption = _transcript().to_json()
    caption["provenance"]["source"] = "captions"
    assert Transcript.from_json(caption).provenance.source == "captions"


def test_a_source_other_than_local_or_captions_is_refused() -> None:
    broken = _transcript().to_json()
    broken["provenance"]["source"] = "guess"
    with pytest.raises(ValueError, match="source"):
        Transcript.from_json(broken)


def test_text_joins_the_words() -> None:
    assert _transcript().text == "ну да"


@pytest.mark.parametrize(
    ("change", "same"),
    [
        ({"audio_sha256": "cd" * 32}, False),
        ({"model": "m2"}, False),
        ({"settings": {"language": "en"}}, False),
        ({"seconds": 99.0}, True),
        ({"made_at": "2030-01-01T00:00:00Z"}, True),
    ],
)
def test_key_changes_with_audio_model_and_settings_only(change: dict[str, object], same: bool) -> None:
    assert (_provenance(**change).key == _provenance().key) is same


def test_job_key_is_the_provenance_key() -> None:
    p = _provenance()
    assert job_key(p.audio_sha256, p.engine, p.model, p.settings) == p.key
