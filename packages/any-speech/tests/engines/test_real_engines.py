"""The real engines against a real clip. Off by default (`-m engines`); each test skips when its engine or input is missing.

Set ANY_SPEECH_CLIP to a 16 kHz mono wav of Russian speech, at least 10 minutes for the memory test;
ANY_SPEECH_FLUIDAUDIO_BIN to a built fluidaudiocli. Private audio never goes into the repo.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest
from any_speech import DEFAULT_BUDGET_GB, Pipeline

pytestmark = pytest.mark.engines

_CLIP = os.environ.get("ANY_SPEECH_CLIP")
_FLUID = os.environ.get("ANY_SPEECH_FLUIDAUDIO_BIN")


def _clip() -> Path:
    if not _CLIP:
        pytest.skip("ANY_SPEECH_CLIP is not set")
    return Path(_CLIP)


async def _ordered_and_sane(pipeline: Pipeline, clip: Path) -> None:
    transcript = await pipeline.run(clip)
    assert transcript.words
    starts = [w.start for w in transcript.words]
    assert starts == sorted(starts)
    assert all(w.end >= w.start for w in transcript.words)
    assert transcript.provenance.audio_seconds > 0


async def test_fluidaudio_transcribes_and_diarizes_a_real_clip() -> None:
    if not _FLUID:
        pytest.skip("ANY_SPEECH_FLUIDAUDIO_BIN is not set")
    from any_speech.adapters import FluidAudioCli, FluidAudioDiarizer

    binary = Path(_FLUID)
    pipeline = Pipeline(FluidAudioCli(binary, runtime="fluidaudiocli"), FluidAudioDiarizer(binary, runtime="fluidaudiocli"))
    await _ordered_and_sane(pipeline, _clip())


@pytest.mark.skipif(importlib.util.find_spec("parakeet_mlx") is None, reason="parakeet-mlx is not installed")
async def test_parakeet_mlx_stays_inside_the_memory_budget_on_long_audio() -> None:
    from any_speech.adapters import ParakeetMlx

    pipeline = Pipeline(ParakeetMlx(runtime="parakeet-mlx"), budget_gb=DEFAULT_BUDGET_GB)
    await _ordered_and_sane(pipeline, _clip())  # the guard raises MemoryBudgetError over 4 GB
