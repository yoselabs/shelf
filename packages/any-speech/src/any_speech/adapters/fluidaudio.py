"""FluidAudio's command line (Swift, CoreML on the Neural Engine): Parakeet ASR and Nemotron 3 diarisation.

The binary is built from FluidAudio (`swift build -c release --product fluidaudiocli`) and its path is injected.
Memory is the child's resident peak; weights run on the Neural Engine and are not counted there.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Literal

from any_speech.adapters._child import ChildResult, Runner, run_child
from any_speech.format import Word
from any_speech.guard import DEFAULT_BUDGET_GB
from any_speech.ports import Diarized, Heard, Identity
from any_speech.words import Turn

ModelVersion = Literal["v3", "ultra"]
_UNK = "<unk>"
_TIMEOUT = 3600.0
_DIARIZER_MODEL = "nemotron-3-diarization"


class FluidAudioError(RuntimeError):
    """The binary exited non-zero."""


def _check(result: ChildResult, what: str) -> None:
    if result.returncode != 0:
        message = f"fluidaudiocli {what} exited {result.returncode}: {result.stderr_tail.strip()}"
        raise FluidAudioError(message)


class FluidAudioCli:
    def __init__(
        self,
        binary: Path,
        *,
        runtime: str,
        model_version: ModelVersion = "v3",
        budget_gb: float | None = DEFAULT_BUDGET_GB,
        run: Runner = run_child,
    ) -> None:
        self.identity = Identity("fluidaudio", f"parakeet-tdt-0.6b-{model_version}", runtime, {"model_version": model_version})
        self._binary = binary
        self._version = model_version
        self._budget = budget_gb
        self._run = run

    def transcribe(self, audio: Path) -> Heard:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            args = [self._binary, "transcribe", audio, "--model-version", self._version, "--word-timestamps", "--output-json", out]
            result = self._run(args, timeout=_TIMEOUT, budget_gb=self._budget)
            _check(result, "transcribe")
            words = parse_words(json.loads(out.read_text(encoding="utf-8")))
        return Heard(words, result.seconds, result.peak_gb)


def parse_words(raw: dict[str, object]) -> tuple[Word, ...]:
    """FluidAudio's `wordTimings`; the model's `<unk>` placeholder is cut out of a word and an empty word dropped."""
    words = []
    for item in raw["wordTimings"]:  # type: ignore[attr-defined]  # shape fixed by the recorded-output test
        text = str(item["word"]).replace(_UNK, "").strip()
        if text:
            words.append(Word(text, float(item["startTime"]), float(item["endTime"]), float(item["confidence"])))
    return tuple(words)


class FluidAudioDiarizer:
    def __init__(self, binary: Path, *, runtime: str, budget_gb: float | None = DEFAULT_BUDGET_GB, run: Runner = run_child) -> None:
        self.identity = Identity("fluidaudio", _DIARIZER_MODEL, runtime, {"compute_units": "gpu"})
        self._binary = binary
        self._budget = budget_gb
        self._run = run

    def diarize(self, audio: Path) -> Diarized:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.rttm"
            args = [self._binary, "nemotron3-diarize", audio, "--output", out, "--compute-units", "gpu"]
            result = self._run(args, timeout=_TIMEOUT, budget_gb=self._budget)
            _check(result, "nemotron3-diarize")
            return Diarized(parse_rttm(out.read_text(encoding="utf-8")))


_RTTM = re.compile(r"^SPEAKER \S+ \d+ (?P<start>[\d.]+) (?P<dur>[\d.]+) \S+ \S+ (?P<who>\S+)", re.MULTILINE)


def parse_rttm(text: str) -> tuple[Turn, ...]:
    """RTTM lines to turns, relabelled S1, S2, ... by first appearance."""
    rows = sorted((float(m["start"]), float(m["dur"]), m["who"]) for m in _RTTM.finditer(text))
    labels: dict[str, str] = {}
    return tuple(Turn(s, s + d, labels.setdefault(who, f"S{len(labels) + 1}")) for s, d, who in rows)
