from __future__ import annotations

import wave
from typing import TYPE_CHECKING

import pytest
from any_speech import (
    EngineMissingError,
    Slots,
    Speaker,
    Transcript,
    Turn,
    Word,
    default_speech,
    default_transcriber,
    transcribe,
    transcribe_with_speakers,
)
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
    assert t.identity.runtime.startswith("fluidaudio-unknown+")


def test_the_default_transcriber_finds_the_binary_in_the_standard_place(tmp_path: Path) -> None:
    binary = _fake_binary(tmp_path)
    standard = tmp_path / ".local" / "bin"
    standard.mkdir(parents=True)
    (standard / "fluidaudiocli").write_bytes(binary.read_bytes())
    assert (
        default_transcriber(
            env={},
            home=tmp_path,
        ).identity.engine
        == "fluidaudio"
    )


def test_a_missing_binary_says_how_to_build_it_and_names_the_explicit_alternative(tmp_path: Path) -> None:
    with pytest.raises(EngineMissingError) as caught:
        default_transcriber(env={}, home=tmp_path)
    text = str(caught.value)
    assert "any-speech setup fluidaudio" in text
    assert "ANY_SPEECH_FLUIDAUDIO_BIN" in text
    assert "ParakeetMlx" in text  # named, never used on its own


async def test_transcribe_is_words_only_and_stores_one_file_beside_the_audio(tmp_path: Path) -> None:
    audio = _wav(tmp_path / "talk.wav")
    result = await transcribe(audio, transcriber=FakeTranscriber(_WORDS), leases_root=tmp_path / "leases")
    stored = tmp_path / "talk.wav.speech.json"
    assert Transcript.load(stored) == result
    assert (result.provenance.diarizer, [w.speaker for w in result.words]) == ({"status": "not_run"}, [None])


async def test_transcribe_with_speakers_labels_the_words(tmp_path: Path) -> None:
    audio = _wav(tmp_path / "talk.wav")
    result = await transcribe_with_speakers(
        audio, transcriber=FakeTranscriber(_WORDS), diarizer=FakeDiarizer([Turn(0.0, 1.0, "S1")]), leases_root=tmp_path / "l"
    )
    assert [w.speaker for w in result.words] == ["S1"]
    assert Transcript.load(tmp_path / "talk.wav.speech.json").speakers == {"S1": Speaker("voice 1", 0.5, 1)}


async def test_transcribe_with_speakers_needs_the_default_diarizer_and_says_how_to_get_it(tmp_path: Path) -> None:
    audio = _wav(tmp_path / "a.wav")
    with pytest.raises(EngineMissingError, match="fluidaudiocli"):
        await transcribe_with_speakers(audio, transcriber=FakeTranscriber(_WORDS), leases_root=tmp_path / "l", env={}, home=tmp_path)


async def test_a_words_only_file_is_not_reused_for_a_speakers_request(tmp_path: Path) -> None:
    audio = _wav(tmp_path / "a.wav")
    await transcribe(audio, transcriber=FakeTranscriber(_WORDS), leases_root=tmp_path / "l")
    again = await transcribe_with_speakers(
        audio, transcriber=FakeTranscriber(_WORDS), diarizer=FakeDiarizer([Turn(0.0, 1.0, "S1")]), leases_root=tmp_path / "l"
    )
    assert [w.speaker for w in again.words] == ["S1"]


async def test_out_moves_the_stored_file(tmp_path: Path) -> None:
    audio, out = _wav(tmp_path / "a.wav"), tmp_path / "elsewhere" / "t.json"
    await transcribe(audio, out, transcriber=FakeTranscriber(_WORDS), leases_root=tmp_path / "l")
    assert out.exists()
    assert not (tmp_path / "a.wav.speech.json").exists()


@pytest.mark.parametrize(
    ("ram_gb", "expected"),
    [(8, Slots(1, 1, 1)), (16, Slots(1, 1, 1)), (36, Slots(3, 1, 3)), (64, Slots(4, 2, 4)), (512, Slots(4, 2, 4))],
)
def test_auto_slots_follow_the_machines_memory(ram_gb: int, expected: Slots) -> None:
    assert Slots.auto(ram_bytes=ram_gb * 2**30) == expected


def test_default_slots_are_the_auto_slots(tmp_path: Path) -> None:
    speech = default_speech(transcriber=FakeTranscriber(_WORDS), leases_root=tmp_path / "l")
    assert speech.slots == Slots.auto()


def test_the_leases_folder_defaults_under_the_state_dir(tmp_path: Path) -> None:
    env = {"XDG_STATE_HOME": str(tmp_path / "state")}
    default_speech(transcriber=FakeTranscriber(_WORDS), env=env)
    assert (tmp_path / "state" / "any-speech" / "leases").is_dir()
