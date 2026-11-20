from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from any_speech import (
    Pipeline,
    Provenance,
    Segment,
    Slots,
    Speaker,
    Speech,
    Transcript,
    Word,
    job_key,
)
from any_speech.speech import default_out, is_current
from any_speech.testing import FakeTranscriber
from any_versioned import UnknownVersionError


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
        speakers={"S1": Speaker("voice 1", 0.2, 1)},
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
    assert json.loads(raw)["version"] == 2
    assert "ну да" in raw


def test_a_reader_refuses_a_version_it_does_not_know(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    path.write_text(json.dumps({**_transcript().to_json(), "version": 3}), encoding="utf-8")
    with pytest.raises(UnknownVersionError):
        Transcript.load(path)


def test_a_v1_file_still_loads_with_talk_time_worked_out_from_its_words() -> None:
    raw = _transcript().to_json()
    raw["version"] = 1
    raw["speakers"] = {"S1": "voice 1"}
    loaded = Transcript.from_json(raw)
    assert loaded.speakers == {"S1": Speaker("voice 1", 0.2, 1)}


def test_the_contract_shows_each_voice_with_its_talk_time() -> None:
    assert _transcript().to_json()["speakers"] == {"S1": {"name": "voice 1", "seconds": 0.2, "words": 1}}
    assert _transcript().to_json()["version"] == 2


def test_captions_are_a_source_kind() -> None:
    caption = _transcript().to_json()
    caption["provenance"]["source"] = "captions"
    assert Transcript.from_json(caption).provenance.source == "captions"


def test_a_source_other_than_local_or_captions_is_refused() -> None:
    broken = _transcript().to_json()
    broken["provenance"]["source"] = "guess"
    with pytest.raises(ValueError, match="source"):
        Transcript.from_json(broken)


def test_to_text_is_one_readable_line_per_segment_with_clock_and_speaker() -> None:
    t = _transcript()
    assert t.to_text() == "[00:00] S1: ну да\n"
    late = Transcript(
        words=(Word("да", 3700.0, 3700.5, None, None),),
        segments=(Segment(3700.0, 3700.5, "да", None),),
        speakers={},
        provenance=_provenance(),
    )
    assert late.to_text() == "[01:01:40] да\n"


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


def test_default_out_is_the_stem_with_speech_json() -> None:
    assert default_out(Path("/x/talk.m4a")) == Path("/x/talk.speech.json")
    assert default_out(Path("/x/a.b.wav")) == Path("/x/a.b.speech.json")


async def test_is_current_works_for_the_stem_name(tmp_path: Path) -> None:
    audio = tmp_path / "talk.m4a"
    audio.write_bytes(b"x")
    pipeline = Pipeline(FakeTranscriber((Word("да", 0.0, 0.5),)), None, probe=lambda _p: 1.0)
    stored = await Speech(pipeline, tmp_path / "leases", Slots(1, 1, 1)).transcribe(audio)
    assert default_out(audio).exists()
    assert await is_current(default_out(audio), pipeline, audio)
    assert stored.provenance.key == Transcript.load(default_out(audio)).provenance.key


def _engine_like() -> Transcript:
    """Times as an engine hands them over: long binary floats, several speakers, a pause, a failed-free diarizer."""
    words = (
        Word("ну", 0.08000000000000002, 0.2399999999999993, 0.987654321, "S1"),
        Word("да", 0.30000000000000004, 0.5, 0.91, "S1"),
        Word("hello", 3700.1234567, 3700.9996, None, "S2"),
        Word("", 3701.0004999, 3701.5, None, None),
    )
    return Transcript(
        words=words,
        segments=(Segment(0.08000000000000002, 0.5, "ну да", "S1"), Segment(3700.1234567, 3701.5, "hello", "S2")),
        speakers={"S1": Speaker("voice 1", 0.36, 2), "S2": Speaker("voice 2", 0.876, 1)},
        provenance=_provenance(diarizer={"model": "d1", "status": "ok"}),
    )


def _to_ms(t: Transcript) -> Transcript:
    return replace(
        t,
        words=tuple(replace(w, start=round(w.start, 3), end=round(w.end, 3)) for w in t.words),
        segments=tuple(replace(s, start=round(s.start, 3), end=round(s.end, 3)) for s in t.segments),
    )


def test_the_stored_file_is_compact_and_loads_back_equal_up_to_millisecond_times(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    original = _engine_like()
    original.save(path)
    raw = path.read_text(encoding="utf-8")
    assert raw.count("\n") == 1  # one line: no indent
    assert '"start": 0.08,' in raw
    assert Transcript.load(path) == _to_ms(original)
    assert Transcript.load(path).provenance.key == original.provenance.key


def test_a_second_save_of_a_loaded_file_changes_nothing(tmp_path: Path) -> None:
    first, second = tmp_path / "1.json", tmp_path / "2.json"
    _engine_like().save(first)
    Transcript.load(first).save(second)
    assert first.read_bytes() == second.read_bytes()


def test_a_v2_file_written_before_compact_json_still_loads(tmp_path: Path) -> None:
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"version": 2, **asdict(_engine_like())}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    assert Transcript.load(path) == _engine_like()  # old files keep their full-precision times


def test_segments_stay_in_the_file_because_they_are_not_always_what_the_words_cut_to() -> None:
    odd = replace(_transcript(), segments=(Segment(0.0, 0.5, "ну", "S1"), Segment(0.3, 0.5, "да", None)))
    assert Transcript.from_json(odd.to_json()).segments == odd.segments


_HEADER = """---
transcript_version: 3
kind: speech
status: ok
audio:
  duration_sec: 12.5
speakers:
  S1: voice 1
diarizer: not_run
transcribed_at: '2026-11-19T10:00:00Z'
transcriber: m1
transcriber_runtime: r1
---
"""


def test_markdown_is_a_reco_header_then_the_turn_lines() -> None:
    assert _transcript().to_markdown() == _HEADER + "\n[00:00] S1: ну да\n"


def test_markdown_header_carries_each_voice_the_model_and_quotes_what_yaml_would_misread() -> None:
    head = _engine_like().to_markdown().split("---\n")[1]
    assert head == _HEADER.split("---\n")[1].replace("  S1: voice 1\n", "  S1: voice 1\n  S2: voice 2\n").replace(
        "diarizer: not_run", "diarizer: d1"
    )
    odd = replace(_transcript(), provenance=_provenance(model="v3", runtime="1.5", diarizer={"model": "a: b", "status": "ok"}))
    assert "transcriber: v3\n" in odd.to_markdown()
    assert "transcriber_runtime: '1.5'\n" in odd.to_markdown()
    assert "diarizer: 'a: b'\n" in odd.to_markdown()


def test_markdown_separates_turns_with_a_blank_line() -> None:
    body = _engine_like().to_markdown().split("---\n", 2)[2]
    assert body == "\n[00:00] S1: ну да\n\n[01:01:40] S2: hello\n"


def test_markdown_says_what_the_diarizer_did_when_words_have_no_speakers() -> None:
    words_only = Transcript(words=(Word("да", 0.0, 0.5),), segments=(Segment(0.0, 0.5, "да", None),), speakers={}, provenance=_provenance())
    md = words_only.to_markdown()
    assert "speakers: {}\n" in md
    assert "diarizer: not_run\n" in md
    assert md.endswith("\n[00:00] да\n")
    failed = replace(words_only, provenance=_provenance(diarizer={"model": "d1", "status": "failed", "detail": "boom"}))
    assert "diarizer: failed\n" in failed.to_markdown()
    assert "status: ok\n" in failed.to_markdown()  # the words are fine; only the voices are missing
