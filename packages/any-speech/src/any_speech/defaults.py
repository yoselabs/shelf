"""The simple path: `transcribe(path)` with the default models, and every part replaceable by name."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Final

import app_dirs

from any_speech.adapters import FluidAudioCli, FluidAudioDiarizer
from any_speech.pipeline import Pipeline
from any_speech.speech import Slots, Speech

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from any_speech.format import Transcript
    from any_speech.ports import Diarizer, Transcriber

FLUIDAUDIO_ENV = "ANY_SPEECH_FLUIDAUDIO_BIN"
APP = "any-speech"


class EngineMissingError(RuntimeError):
    """The default engine is not installed; the message says how to install it. Nothing else is used instead."""


class _NoDiarizer:
    """Say it out loud: this run needs words only."""


NO_DIARIZER: Final = _NoDiarizer()


def find_fluidaudio(env: Mapping[str, str], home: Path, which: Callable[[str], str | None]) -> Path:
    named = env.get(FLUIDAUDIO_ENV)
    candidates = [Path(named)] if named else []
    candidates += [Path(found) for found in [which("fluidaudiocli")] if found]
    candidates.append(home / ".local" / "bin" / "fluidaudiocli")
    for path in candidates:
        if path.is_file():
            return path
    message = (
        "the default engine, FluidAudio's `fluidaudiocli`, was not found. Build it in a FluidAudio checkout with "
        "`swift build -c release --product fluidaudiocli` and either put it on PATH, in ~/.local/bin, or set "
        f"{FLUIDAUDIO_ENV} to its path. To use another engine, pass it by name (for example "
        "any_speech.adapters.ParakeetMlx) as `transcriber=`: nothing falls back to it on its own."
    )
    raise EngineMissingError(message)


def _runtime(binary: Path) -> str:
    """The binary has no version flag; its content hash says which build produced a transcript."""
    return "fluidaudiocli-" + hashlib.sha256(binary.read_bytes()).hexdigest()[:8]


def _binary(env: Mapping[str, str] | None, home: Path | None, which: Callable[[str], str | None]) -> Path:
    return find_fluidaudio(os.environ if env is None else env, Path.home() if home is None else home, which)


def default_transcriber(
    *, env: Mapping[str, str] | None = None, home: Path | None = None, which: Callable[[str], str | None] = shutil.which
) -> Transcriber:
    binary = _binary(env, home, which)
    return FluidAudioCli(binary, runtime=_runtime(binary))


def default_diarizer(
    *, env: Mapping[str, str] | None = None, home: Path | None = None, which: Callable[[str], str | None] = shutil.which
) -> Diarizer:
    binary = _binary(env, home, which)
    return FluidAudioDiarizer(binary, runtime=_runtime(binary))


def default_speech(
    *,
    transcriber: Transcriber | None = None,
    diarizer: Diarizer | _NoDiarizer | None = None,
    slots: Slots | None = None,
    leases_root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Speech:
    """The default models and slots; each argument replaces one part. `diarizer=NO_DIARIZER` skips diarisation."""
    chosen = transcriber if transcriber is not None else default_transcriber(env=env)
    if isinstance(diarizer, _NoDiarizer):
        voices: Diarizer | None = None
    elif diarizer is None:
        voices = default_diarizer(env=env)
    else:
        voices = diarizer
    root = leases_root if leases_root is not None else app_dirs.state_dir(APP, env=env) / "leases"
    root.mkdir(parents=True, exist_ok=True)
    return Speech(Pipeline(chosen, voices), root, slots if slots is not None else Slots())


def transcribe(
    audio: Path,
    out: Path | None = None,
    *,
    transcriber: Transcriber | None = None,
    diarizer: Diarizer | _NoDiarizer | None = None,
    slots: Slots | None = None,
    leases_root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Transcript:
    """A path in, a Transcript out (stored at `out` when given). With no other argument: the default models and slots."""
    speech = default_speech(transcriber=transcriber, diarizer=diarizer, slots=slots, leases_root=leases_root, env=env)
    return speech.transcribe(audio, out)
