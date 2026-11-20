"""The `any-speech` command: the composition root that turns flags into engines.

Verbs: ``transcribe`` one file, ``text`` print one as markdown, ``drain`` a folder (N workers, inside the machine slots),
``embed`` a voice, ``match`` a clip to it.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

import app_dirs
from verb_cli import POSITIONAL, VerbCli

from any_speech.defaults import find_fluidaudio, runtime_of
from any_speech.drain import Drain, Job
from any_speech.format import Transcript
from any_speech.guard import DEFAULT_BUDGET_GB
from any_speech.pipeline import Pipeline
from any_speech.ports import Voice
from any_speech.setup import SetupError, install_fluidaudio
from any_speech.speech import Slots, Speech, default_out

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from any_speech.ports import Diarizer, Transcriber, VoiceEmbedder

EngineName = Literal["fluidaudio", "parakeet-mlx"]
APP = "any-speech"


@dataclass(frozen=True)
class Settings:
    """Shared by every verb."""

    engine: EngineName = "fluidaudio"  # the default model; another engine is only used when named, never as a fallback
    diarize: bool = False
    model_version: Literal["v3", "ultra"] = "v3"
    fluidaudio_bin: Path | None = None
    voice_model: Path | None = None
    budget_gb: float = DEFAULT_BUDGET_GB
    transcribe_slots: int | None = None  # the slot counts are sized from the machine unless given
    diarize_slots: int | None = None
    total_slots: int | None = None
    workers: int = 2


def make_transcriber(s: Settings) -> Transcriber:
    if s.engine == "fluidaudio":
        from any_speech.adapters import FluidAudioCli  # noqa: PLC0415  only the chosen engine is imported

        binary = _fluidaudio_bin(s)
        return FluidAudioCli(binary, runtime=runtime_of(binary), model_version=s.model_version, budget_gb=s.budget_gb)
    from any_speech.adapters import ParakeetMlx  # noqa: PLC0415

    return ParakeetMlx(runtime=f"parakeet-mlx-{version('parakeet-mlx')}")


def make_diarizer(s: Settings) -> Diarizer | None:
    if not s.diarize:
        return None
    from any_speech.adapters import FluidAudioDiarizer  # noqa: PLC0415

    binary = _fluidaudio_bin(s)
    return FluidAudioDiarizer(binary, runtime=runtime_of(binary), budget_gb=s.budget_gb)


def make_embedder(s: Settings) -> VoiceEmbedder:
    from any_speech.adapters import SherpaEmbedder  # noqa: PLC0415

    if s.voice_model is None:
        message = "--voice-model is needed: the path of a sherpa-onnx speaker model (.onnx)"
        raise SystemExit(message)
    return SherpaEmbedder(s.voice_model, runtime=f"sherpa-onnx-{version('sherpa-onnx')}")


def _fluidaudio_bin(s: Settings) -> Path:
    return s.fluidaudio_bin or find_fluidaudio(os.environ, Path.home())


def make_pipeline(s: Settings) -> Pipeline:
    return Pipeline(make_transcriber(s), make_diarizer(s), budget_gb=s.budget_gb)


def _slots(s: Settings) -> Slots:
    auto = Slots.auto()
    return Slots(s.transcribe_slots or auto.transcribe, s.diarize_slots or auto.diarize, s.total_slots or auto.total)


def _speech(build: Callable[[Settings], Pipeline], leases_root: Callable[[], Path], s: Settings) -> Speech:
    return Speech(build(s), leases_root(), _slots(s))


def _verbs(
    build: Callable[[Settings], Pipeline], embedder: Callable[[Settings], VoiceEmbedder], leases_root: Callable[[], Path]
) -> dict[str, Callable[..., int]]:
    def transcribe(audio: Annotated[Path, POSITIONAL], settings: Settings, out: Path | None = None) -> int:
        """Transcribe one audio file into one JSON file (default: beside the audio, `<stem>.speech.json`); --diarize adds speakers."""
        asyncio.run(_speech(build, leases_root, settings).transcribe(audio, out))
        sys.stdout.write(f"{out or default_out(audio)}\n")
        return 0

    def drain(root: Annotated[Path, POSITIONAL], settings: Settings, pattern: str = "**/audio.*", out_name: str = "speech.json") -> int:
        """Transcribe every audio file under ROOT without a current transcript, one model per machine."""

        def scan() -> list[Job]:
            return [Job(a, a.with_name(out_name)) for a in sorted(root.glob(pattern)) if a.is_file()]

        report = asyncio.run(Drain(scan=scan, speech=_speech(build, leases_root, settings), workers=settings.workers).run())
        sys.stdout.write(json.dumps({"done": len(report.done), "failed": len(report.failed), "skipped": len(report.skipped)}) + "\n")
        return 1 if report.failed else 0

    def embed(
        audio: Annotated[Path, POSITIONAL], settings: Settings, out: Path, start: float | None = None, end: float | None = None
    ) -> int:
        """Embed a voice (a clip, or START to END seconds of it) and save it to OUT."""
        voice = embedder(settings).embed(audio, start=start, end=end)
        out.write_text(json.dumps({"model": voice.model, "vector": list(voice.vector)}), encoding="utf-8")
        return 0

    def match(
        audio: Annotated[Path, POSITIONAL], settings: Settings, voice: Path, start: float | None = None, end: float | None = None
    ) -> int:
        """Print how alike a clip's voice is to a saved voice (1 is identical); compare against a threshold you calibrated."""
        saved = json.loads(voice.read_text(encoding="utf-8"))
        known = Voice(saved["model"], tuple(saved["vector"]))
        sys.stdout.write(f"{embedder(settings).embed(audio, start=start, end=end).similarity(known):.4f}\n")
        return 0

    def text(file: Annotated[Path, POSITIONAL]) -> int:
        """Print a stored transcript as markdown: a header, then one `[MM:SS] S1: text` turn per paragraph."""
        sys.stdout.write(Transcript.load(file).to_markdown())
        return 0

    def setup(what: Annotated[Literal["fluidaudio"], POSITIONAL]) -> int:
        """Build FluidAudio's command line at the pinned commit and install it, so no path flag is ever needed."""
        try:
            target = install_fluidaudio(os.environ, Path.home())
        except SetupError as error:
            sys.stderr.write(f"{error}\n")
            return 1
        sys.stdout.write(f"{what}: {target}\n")
        return 0

    return {"setup": setup, "transcribe": transcribe, "text": text, "drain": drain, "embed": embed, "match": match}


def main(
    argv: Sequence[str] | None = None,
    *,
    build: Callable[[Settings], Pipeline] = make_pipeline,
    embedder: Callable[[Settings], VoiceEmbedder] = make_embedder,
    leases_root: Callable[[], Path] = lambda: app_dirs.state_dir(APP) / "leases",
) -> int:
    cli = VerbCli(_verbs(build, embedder, leases_root), shared=Settings)
    return int(cli.parse(argv, prog=APP).call())


def run() -> None:
    sys.exit(main())


__all__ = ["Settings", "main", "make_pipeline"]
