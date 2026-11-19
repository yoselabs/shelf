"""Why each model is or is not the choice: the verdict, the reason, the evidence, and what would reopen it.

This is the trace of model selection. Reco 2's decisions are carried in as cited evidence (its OpenSpec changes
`embed-transcription` and `diarize-speakers`, K Research [181]); the numbers marked measured come from
openspec/changes/any-speech/measurement.md (2026-11-19, M3 Max). When a model is upgraded or replaced, change its
card in the same commit: a card that disagrees with the code is a defect (tests check the identities).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Role = Literal["transcribe", "diarize", "embed"]
Status = Literal["default", "available", "refused", "untested"]
_MEASURED = "openspec/changes/any-speech/measurement.md"
_RECO_ASR = "reco: openspec/changes/embed-transcription (K Research [181])"
_RECO_DIAR = "reco: openspec/changes/diarize-speakers"


@dataclass(frozen=True, slots=True)
class ModelCard:
    key: str
    role: Role
    engine: str
    model: str
    status: Status
    why: str
    evidence: str
    revisit: str = ""


CARDS: tuple[ModelCard, ...] = (
    ModelCard(
        "fluidaudio-parakeet-v3",
        "transcribe",
        "fluidaudio",
        "parakeet-tdt-0.6b-v3",
        "default",
        "Never flipped language and lost no content where Whisper latched a wrong language and destroyed whole tracks "
        "(11 of 549 Reco transcripts); keeps more fillers than Whisper; word times and confidence; 0.2-0.7 GB, 57 min in 12 s.",
        f"{_RECO_ASR}; measured: {_MEASURED}",
    ),
    ModelCard(
        "fluidaudio-parakeet-ultra",
        "transcribe",
        "fluidaudio",
        "parakeet-tdt-0.6b-ultra",
        "available",
        "Reco's chosen upgrade (FLEURS 24-language WER 14.81 % to 11.67 %, cited), but measured here it emits `<unk>` "
        "(31 in 57 min against 1 for v3), so it is not the default; the adapter cuts `<unk>` out.",
        f"{_RECO_DIAR}; measured: {_MEASURED}",
        revisit="a reference text to score both, or an Ultra release that stops emitting `<unk>`",
    ),
    ModelCard(
        "parakeet-mlx-v3",
        "transcribe",
        "parakeet-mlx",
        "mlx-community/parakeet-tdt-0.6b-v3",
        "available",
        "The same model in pure Python, for a machine without the FluidAudio binary. Chunked it peaks at 3.3-3.4 GB "
        "(4.09 GB process footprint at 57 min, over the 4 GB budget); unchunked 14.5 GB.",
        f"measured: {_MEASURED}",
    ),
    ModelCard(
        "mlx-whisper-large-v3-turbo",
        "transcribe",
        "mlx-whisper",
        "mlx-community/whisper-large-v3-turbo",
        "refused",
        "4.16 GB at 57 min (over budget), 13x slower than FluidAudio, fewer fillers kept (20 against 31 «ну»), a "
        "hallucinated credit line twice; its language latch is Reco's cited failure, not reproduced here.",
        f"{_RECO_ASR}; measured: {_MEASURED}",
        revisit="a language Parakeet does not cover, or a measured Whisper setting that fits the budget and keeps fillers",
    ),
    ModelCard(
        "sherpa-parakeet-v3-int8",
        "transcribe",
        "sherpa-onnx",
        "parakeet-tdt-0.6b-v3-int8",
        "refused",
        "The same model as FluidAudio, 9x slower on the CPU and 2.6-3.2 GB.",
        f"measured: {_MEASURED}",
        revisit="a machine without Apple Silicon (untested there)",
    ),
    ModelCard(
        "faster-whisper-tiny",
        "transcribe",
        "faster-whisper",
        "tiny",
        "untested",
        "personal-brand's wave3 fallback; its own label is 'imperfect machine evidence'. Not run.",
        "personal-brand: codex/wave3/transcribe_missing.py",
        revisit="run it on the Solek clips against Parakeet",
    ),
    ModelCard(
        "fluidaudio-nemotron3-diarization",
        "diarize",
        "fluidaudio",
        "nemotron-3-diarization",
        "default",
        "Up to 8 voices; Reco measured 4 voices in a 17 min call in 44 s; 26-28x real time and 0.4-0.5 GB here. "
        "Accuracy against ground truth is not verified here.",
        f"{_RECO_DIAR}; measured: {_MEASURED}",
    ),
    ModelCard(
        "sherpa-pyannote-3dspeaker",
        "diarize",
        "sherpa-onnx",
        "pyannote-segmentation-3.0+3dspeaker",
        "refused",
        "8 voices where Nemotron found 2 on the same 5 minutes, and 4x slower; the clustering threshold was not tuned.",
        f"measured: {_MEASURED}",
        revisit="a tuned threshold, or a machine without CoreML",
    ),
    ModelCard(
        "pyannote-torch",
        "diarize",
        "pyannote",
        "pyannote/speaker-diarization",
        "untested",
        "Needs a Hugging Face token and torch; not run.",
        "not run",
        revisit="a token and a reason to carry torch",
    ),
    ModelCard(
        "sherpa-3dspeaker-eres2net",
        "embed",
        "sherpa-onnx",
        "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k",
        "default",
        "The widest gap on the Solek clips: host 0.64-0.88 against another voice 0.09-0.19; 39 MB. Five clips are not a "
        "calibration: the consumer sets its own threshold.",
        f"measured: {_MEASURED}",
    ),
    ModelCard(
        "sherpa-wespeaker-resnet34",
        "embed",
        "sherpa-onnx",
        "wespeaker_en_voxceleb_resnet34_LM",
        "available",
        "Smaller (26 MB) but a narrower gap: host 0.82-0.97 against another voice 0.60-0.66.",
        f"measured: {_MEASURED}",
    ),
)


def default_card(role: Role) -> ModelCard:
    return next(c for c in CARDS if c.role == role and c.status == "default")


def card_for(engine: str, model: str) -> ModelCard:
    """The card of the model an adapter reports in its identity; KeyError when the model has no card."""
    for c in CARDS:
        if (c.engine, c.model) == (engine, model):
            return c
    raise KeyError((engine, model))
