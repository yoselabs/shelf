"""Speech in, a Transcript out: words with times, speakers and provenance, from swappable engines.

- :func:`transcribe`: ``transcribe(path)``, the default model, words stored in one file beside the audio and returned;
  :func:`transcribe_with_speakers` adds the voices. Every part is replaceable by name (``transcriber=``, ``diarizer=``, ``slots=``).
  :data:`CARDS` says why each model is or is not the choice.
- :class:`Transcript` (and :class:`Word`, :class:`Segment`, :class:`Provenance`): the versioned JSON format.
- :class:`Pipeline`: one file through a :class:`Transcriber` and an optional :class:`Diarizer`; a peak over the
  memory budget raises :class:`MemoryBudgetError`; a diarizer failure never fails the transcript.
- :class:`Speech`: ``Speech(pipeline, leases_root, slots).transcribe(path)``. Model calls wait for a free slot from a counted
  pool (:class:`Slots`: how many transcribe and diarize calls run at once, machine-wide).
- :class:`Drain`: runs every pending :class:`Job` with N workers, rescanning until none is left; a failed file is
  recorded and skipped until it changes.
- :class:`Voice`: a speaker embedding for matching a voice across files.
- ``any_speech.adapters``: the engines; ``any_speech.testing``: scripted fakes.
"""

from any_speech.defaults import (
    EngineMissingError,
    default_diarizer,
    default_speech,
    default_transcriber,
    transcribe,
    transcribe_with_speakers,
)
from any_speech.drain import Drain, DrainReport, Job
from any_speech.format import Provenance, Segment, Speaker, Transcript, Word, job_key
from any_speech.guard import DEFAULT_BUDGET_GB, MemoryBudgetError
from any_speech.models import CARDS, ModelCard, card_for, default_card
from any_speech.pipeline import AudioHasher, Pipeline
from any_speech.ports import Diarized, Diarizer, Heard, Identity, Transcriber, Voice, VoiceEmbedder
from any_speech.speech import Slots, Speech
from any_speech.words import Piece, Turn, assign_speakers, segments_from_words, words_from_pieces

__all__ = [
    "CARDS",
    "DEFAULT_BUDGET_GB",
    "AudioHasher",
    "Diarized",
    "Diarizer",
    "Drain",
    "DrainReport",
    "EngineMissingError",
    "Heard",
    "Identity",
    "Job",
    "MemoryBudgetError",
    "ModelCard",
    "Piece",
    "Pipeline",
    "Provenance",
    "Segment",
    "Slots",
    "Speaker",
    "Speech",
    "Transcriber",
    "Transcript",
    "Turn",
    "Voice",
    "VoiceEmbedder",
    "Word",
    "assign_speakers",
    "card_for",
    "default_card",
    "default_diarizer",
    "default_speech",
    "default_transcriber",
    "job_key",
    "segments_from_words",
    "transcribe",
    "transcribe_with_speakers",
    "words_from_pieces",
]
