from __future__ import annotations

import os
import wave
from typing import TYPE_CHECKING

import pytest
from any_speech import NO_DIARIZER, EngineMissingError, Slots, Turn, Word, default_speech, default_transcriber, transcribe
from any_speech.testing import FakeDiarizer, FakeTranscriber

if TYPE_CHECKING:
    from pathlib import Path

_WORDS = (Word("да", 0.0, 0.5),)


def _wav(path: Path) -> Path:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"\x00\x00" * 16000)
    return path


def _fake_binary(tmp_path: Path) -> Path:
    binary = tmp_path / "bin" / "fluidaudiocli"
    binary.parent.mkdir()
    binary.write_bytes(b"#!/bin/sh\n")
    binary.chmod(0o755)
    return binary


def test_the_default_transcriber_finds_the_binary_named_in_the_environment(tmp_path: Path) -> None:
    binary = _fake_binary(tmp_path)
    t = default_transcriber(env={"ANY_SPEECH_FLUIDAUDIO_BIN": str(binary)}, home=tmp_path)
    assert t.identity.model == "parakeet-tdt-0.6b-v3"
    assert t.identity.runtime.startswith("fluidaudiocli-")


def test_the_default_transcriber_finds_the_binary_in_the_standard_place(tmp_path: Path) -> None:
    binary = _fake_binary(tmp_path)
    standard = tmp_path / ".local" / "bin"
    standard.mkdir(parents=True)
    (standard / "fluidaudiocli").write_bytes(binary.read_bytes())
    assert default_transcriber(env={}, home=tmp_path, which=lambda _n: None).identity.engine == "fluidaudio"


def test_a_missing_binary_says_how_to_build_it_and_names_the_explicit_alternative(tmp_path: Path) -> None:
    with pytest.raises(EngineMissingError) as caught:
        default_transcriber(env={}, home=tmp_path, which=lambda _n: None)
    text = str(caught.value)
    assert "swift build -c release --product fluidaudiocli" in text
    assert "ANY_SPEECH_FLUIDAUDIO_BIN" in text
    assert "ParakeetMlx" in text  # named, never used on its own


def test_transcribe_with_overrides_needs_no_binary_and_no_setup(tmp_path: Path) -> None:
    audio = _wav(tmp_path / "a.wav")
    result = transcribe(
        audio,
        transcriber=FakeTranscriber(_WORDS),
        diarizer=FakeDiarizer([Turn(0.0, 1.0, "S1")]),
        leases_root=tmp_path / "leases",
    )
    assert [(w.text, w.speaker) for w in result.words] == [("да", "S1")]


def test_no_diarizer_is_a_named_choice(tmp_path: Path) -> None:
    audio = _wav(tmp_path / "a.wav")
    result = transcribe(audio, transcriber=FakeTranscriber(_WORDS), diarizer=NO_DIARIZER, leases_root=tmp_path / "leases")
    assert result.provenance.diarizer == {"status": "not_run"}


def test_transcribe_with_out_stores_the_transcript(tmp_path: Path) -> None:
    audio, out = _wav(tmp_path / "a.wav"), tmp_path / "a.json"
    transcribe(audio, out, transcriber=FakeTranscriber(_WORDS), diarizer=NO_DIARIZER, leases_root=tmp_path / "leases")
    assert out.exists()


def test_slots_are_overridable_and_default_to_two_one_three(tmp_path: Path) -> None:
    speech = default_speech(transcriber=FakeTranscriber(_WORDS), diarizer=NO_DIARIZER, leases_root=tmp_path / "l", slots=Slots(4, 2, 6))
    assert speech is not None
    assert Slots() == Slots(2, 1, 3)


def test_the_leases_folder_defaults_under_the_state_dir(tmp_path: Path) -> None:
    env = {"XDG_STATE_HOME": str(tmp_path / "state")}
    default_speech(transcriber=FakeTranscriber(_WORDS), diarizer=NO_DIARIZER, env=env)
    assert (tmp_path / "state" / "any-speech" / "leases").is_dir()
    assert os.environ.get("XDG_STATE_HOME") != str(tmp_path / "state")
