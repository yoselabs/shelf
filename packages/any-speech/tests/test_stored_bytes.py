"""What is already stored on disk must keep its bytes: the audio digest and the runtime string, against plain hashlib."""

from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING

from any_speech import Provenance, Segment, Speaker, Transcript, Word
from any_speech.defaults import runtime_of
from any_speech.failures import record, record_path
from any_speech.pipeline import audio_sha256

if TYPE_CHECKING:
    from pathlib import Path


def test_audio_sha256_is_the_plain_sha256_hex_of_the_file(tmp_path: Path) -> None:
    audio = tmp_path / "a.wav"
    audio.write_bytes(bytes(range(256)) * 10_000 + b"tail")  # larger than one read chunk would be at 1 KiB, odd length
    assert audio_sha256(audio) == hashlib.sha256(audio.read_bytes()).hexdigest()
    assert len(audio_sha256(audio)) == 64


def test_audio_sha256_of_a_file_over_one_mebibyte_is_the_plain_sha256(tmp_path: Path) -> None:
    audio = tmp_path / "big.wav"
    audio.write_bytes(b"x" * ((1 << 20) * 2 + 17))
    assert audio_sha256(audio) == hashlib.sha256(audio.read_bytes()).hexdigest()


def test_runtime_is_the_commit_and_the_first_twelve_hex_of_the_binary_sha256(tmp_path: Path) -> None:
    binary = tmp_path / "fluidaudiocli"
    binary.write_bytes(b"build-one" * 50_000)
    binary.with_name("fluidaudiocli.commit").write_text("0b1f46289fe27d95", encoding="utf-8")
    assert runtime_of(binary) == f"fluidaudio-0b1f4628+{hashlib.sha256(binary.read_bytes()).hexdigest()[:12]}"
    other = tmp_path / "x" / "fluidaudiocli"
    other.parent.mkdir()
    other.write_bytes(b"y")
    assert runtime_of(other) == f"fluidaudio-unknown+{hashlib.sha256(b'y').hexdigest()[:12]}"


def test_failure_record_at_stays_a_whole_second_utc_stamp(tmp_path: Path) -> None:
    audio = tmp_path / "talk.m4a"
    audio.write_bytes(b"x")
    out = tmp_path / "talk.speech.json"
    record(out, audio, RuntimeError("boom"))
    at = json.loads(record_path(out).read_text(encoding="utf-8"))["at"]
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", at)


_V2_FILE = (
    '{"version": 2, "words": [{"text": "ну", "start": 0.0, "end": 0.2, "probability": 0.9, '
    '"speaker": "S1"}, {"text": "да", "start": 0.3, "end": 0.5, "probability": null, "speaker": null}], '
    '"segments": [{"start": 0.0, "end": 0.5, "text": "ну да", "speaker": "S1"}], '
    '"speakers": {"S1": {"name": "voice 1", "seconds": 0.2, "words": 1}}, '
    '"provenance": {"engine": "fake", "model": "m1", "runtime": "r1", "settings": {"language": "ru"}, '
    '"audio_sha256": "abababababababababababababababababababababababababababababababab", '
    '"audio_seconds": 12.5, "seconds": 1.5, "peak_memory_gb": 0.5, "diarizer": {"status": "not_run"}, '
    '"made_at": "2026-11-19T10:00:00Z", "source": "local", "key": "fb39b2f971ebc58d"}}'
    "\n"
)


def _golden_transcript() -> Transcript:
    provenance = Provenance(
        engine="fake",
        model="m1",
        runtime="r1",
        settings={"language": "ru"},
        audio_sha256="ab" * 32,
        audio_seconds=12.5,
        seconds=1.5,
        peak_memory_gb=0.5,
        diarizer={"status": "not_run"},
        made_at="2026-11-19T10:00:00Z",
    )
    return Transcript(
        words=(Word("ну", 0.0, 0.2, 0.9, "S1"), Word("да", 0.3, 0.5, None, None)),
        segments=(Segment(0.0, 0.5, "ну да", "S1"),),
        speakers={"S1": Speaker("voice 1", 0.2, 1)},
        provenance=provenance,
    )


def test_a_v2_transcript_is_stored_byte_for_byte_as_it_was(tmp_path: Path) -> None:
    path = tmp_path / "t.speech.json"
    _golden_transcript().save(path)
    assert path.read_bytes() == _V2_FILE.encode("utf-8")


def test_a_stored_v2_file_reads_back_and_a_v1_file_still_reads(tmp_path: Path) -> None:
    path = tmp_path / "t.speech.json"
    path.write_bytes(_V2_FILE.encode("utf-8"))
    assert Transcript.load(path) == _golden_transcript()
    v1 = json.loads(_V2_FILE)
    v1["version"], v1["speakers"] = 1, {"S1": "voice 1"}
    path.write_text(json.dumps(v1, ensure_ascii=False), encoding="utf-8")
    assert Transcript.load(path) == _golden_transcript()
