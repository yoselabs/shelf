"""Speech in, a Transcript out: words with times, speakers and provenance, from swappable engines.

- :class:`Transcript` (and :class:`Word`, :class:`Segment`, :class:`Provenance`): the versioned JSON format.
- :class:`Pipeline`: one file through a :class:`Transcriber` and an optional :class:`Diarizer`; a peak over the
  memory budget raises :class:`MemoryBudgetError`; a diarizer failure never fails the transcript.
- :class:`Speech`: ``Speech(pipeline, leases_root).transcribe(path)``. Model calls wait for a free slot from a counted
  pool (:class:`Slots`: how many transcribe and diarize calls run at once, machine-wide).
- :class:`Drain`: runs every pending :class:`Job` with N workers, rescanning until none is left; a failed file is
  recorded and skipped until it changes.
- :class:`Voice`: a speaker embedding for matching a voice across files.
- ``any_speech.adapters``: the engines; ``any_speech.testing``: scripted fakes.
"""

from any_speech.drain import Drain, DrainReport, Job
from any_speech.format import FORMAT_VERSION, Provenance, Segment, Transcript, UnknownVersionError, Word, job_key
from any_speech.guard import DEFAULT_BUDGET_GB, MemoryBudgetError
from any_speech.pipeline import Pipeline
from any_speech.ports import Diarized, Diarizer, Embedder, Heard, Identity, Transcriber, Voice
from any_speech.speech import Slots, Speech
from any_speech.words import Piece, Turn, assign_speakers, segments_from_words, words_from_pieces

__all__ = [
    "DEFAULT_BUDGET_GB",
    "FORMAT_VERSION",
    "Diarized",
    "Diarizer",
    "Drain",
    "DrainReport",
    "Embedder",
    "Heard",
    "Identity",
    "Job",
    "MemoryBudgetError",
    "Piece",
    "Pipeline",
    "Provenance",
    "Segment",
    "Slots",
    "Speech",
    "Transcriber",
    "Transcript",
    "Turn",
    "UnknownVersionError",
    "Voice",
    "Word",
    "assign_speakers",
    "job_key",
    "segments_from_words",
    "words_from_pieces",
]
