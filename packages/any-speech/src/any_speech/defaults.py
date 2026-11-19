"""The simple path: `transcribe(path)` with the default models, and every part replaceable by name."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import app_dirs

from any_speech.adapters import FluidAudioCli, FluidAudioDiarizer
from any_speech.pipeline import Pipeline
from any_speech.setup import BINARY, COMMIT_SUFFIX, installed_binary
from any_speech.speech import Slots, Speech

if TYPE_CHECKING:
    from collections.abc import Mapping

    from any_speech.format import Transcript
    from any_speech.ports import Diarizer, Transcriber

FLUIDAUDIO_ENV = "ANY_SPEECH_FLUIDAUDIO_BIN"
APP = "any-speech"


class EngineMissingError(RuntimeError):
    """The default engine is not installed; the message says how to install it. Nothing else is used instead."""


def find_fluidaudio(env: Mapping[str, str], home: Path) -> Path:
    named = env.get(FLUIDAUDIO_ENV)
    candidates = [Path(named)] if named else []
    candidates.append(installed_binary(env, home))
    on_path = shutil.which(BINARY, path=env.get("PATH", ""))
    candidates += [Path(on_path)] if on_path else []
    candidates.append(home / ".local" / "bin" / BINARY)
    for path in candidates:
        if path.is_file():
            return path
    message = (
        "the default engine, FluidAudio's `fluidaudiocli`, was not found. Run `any-speech setup fluidaudio` (it builds "
        "`swift build -c release --product fluidaudiocli` at the pinned commit and needs Xcode's Swift), or build it yourself "
        f"and put it on PATH, in ~/.local/bin, or set {FLUIDAUDIO_ENV} to its path. To use another engine, pass it by name (for example "
        "any_speech.adapters.ParakeetMlx) as `transcriber=`: nothing falls back to it on its own."
    )
    raise EngineMissingError(message)


def runtime_of(binary: Path) -> str:
    """The binary has no version flag. Its content hash says which build made a transcript; the commit is added only
    when `setup` wrote it beside the binary, because a binary from anywhere else could be any commit."""
    marker = binary.with_name(binary.name + COMMIT_SUFFIX)
    commit = marker.read_text(encoding="utf-8").strip()[:8] if marker.is_file() else "unknown"
    return f"fluidaudio-{commit}+{hashlib.sha256(binary.read_bytes()).hexdigest()[:12]}"


def _binary(env: Mapping[str, str] | None, home: Path | None) -> Path:
    return find_fluidaudio(os.environ if env is None else env, Path.home() if home is None else home)


def default_transcriber(*, env: Mapping[str, str] | None = None, home: Path | None = None) -> Transcriber:
    binary = _binary(env, home)
    return FluidAudioCli(binary, runtime=runtime_of(binary))


def default_diarizer(*, env: Mapping[str, str] | None = None, home: Path | None = None) -> Diarizer:
    binary = _binary(env, home)
    return FluidAudioDiarizer(binary, runtime=runtime_of(binary))


def default_speech(
    *,
    transcriber: Transcriber | None = None,
    diarizer: Diarizer | None = None,
    slots: Slots | None = None,
    leases_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Speech:
    """The default model and slots (sized from the machine); each argument replaces one part. No diarizer unless given."""
    chosen = transcriber if transcriber is not None else default_transcriber(env=env, home=home)
    root = leases_root if leases_root is not None else app_dirs.state_dir(APP, env=env) / "leases"
    root.mkdir(parents=True, exist_ok=True)
    return Speech(Pipeline(chosen, diarizer), root, slots if slots is not None else Slots.auto())


def transcribe(
    audio: Path,
    out: Path | None = None,
    *,
    transcriber: Transcriber | None = None,
    slots: Slots | None = None,
    leases_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Transcript:
    """The words of `audio`, stored in one file beside it (`<name>.speech.json`, or `out`) and returned.

    No speakers: most uses do not need them, and they cost a second model. See :func:`transcribe_with_speakers`.
    """
    speech = default_speech(transcriber=transcriber, slots=slots, leases_root=leases_root, env=env, home=home)
    return speech.transcribe(audio, out)


def transcribe_with_speakers(
    audio: Path,
    out: Path | None = None,
    *,
    transcriber: Transcriber | None = None,
    diarizer: Diarizer | None = None,
    slots: Slots | None = None,
    leases_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Transcript:
    """As :func:`transcribe`, with each word labelled S1, S2, ... by the voice that said it."""
    voices = diarizer if diarizer is not None else default_diarizer(env=env, home=home)
    speech = default_speech(transcriber=transcriber, diarizer=voices, slots=slots, leases_root=leases_root, env=env, home=home)
    return speech.transcribe(audio, out)
