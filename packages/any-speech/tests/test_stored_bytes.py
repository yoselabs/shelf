"""What is already stored on disk must keep its bytes: the audio digest and the runtime string, against plain hashlib."""

from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING

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
