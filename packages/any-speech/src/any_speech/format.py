"""The transcript format: words with times, speakers and the provenance of how they were made."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Literal

from atomic_io import atomic_write_json
from content_digest import digest

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

FORMAT_VERSION = 2
_READABLE = (1, 2)  # v1 had `speakers` as label to name only; its talk time is worked out from the words
Source = Literal["local", "captions"]
_SOURCES = ("local", "captions")


class UnknownVersionError(ValueError):
    """The file's format version is not one this reader knows."""


@dataclass(frozen=True, slots=True)
class Word:
    text: str
    start: float
    end: float
    probability: float | None = None
    speaker: str | None = None


@dataclass(frozen=True, slots=True)
class Speaker:
    """One voice: its name, the seconds it spoke (its words' durations summed, pauses excluded) and its word count."""

    name: str
    seconds: float
    words: int


def speakers_of(words: tuple[Word, ...], names: Mapping[str, str]) -> dict[str, Speaker]:
    spoken: dict[str, list[Word]] = {label: [] for label in names}
    for word in words:
        if word.speaker in spoken:
            spoken[word.speaker].append(word)
    return {
        label: Speaker(name, round(sum(w.end - w.start for w in spoken[label]), 3), len(spoken[label])) for label, name in names.items()
    }


@dataclass(frozen=True, slots=True)
class Segment:
    start: float
    end: float
    text: str
    speaker: str | None = None


def job_key(audio_sha256: str, engine: str, model: str, settings: Mapping[str, object]) -> str:
    """What makes two runs the same work: the audio, the engine, the model and its settings."""
    return digest({"audio": audio_sha256, "engine": engine, "model": model, "settings": dict(settings)}, length=16)


@dataclass(frozen=True, slots=True)
class Provenance:
    engine: str
    model: str
    runtime: str
    settings: dict[str, object]
    audio_sha256: str
    audio_seconds: float
    seconds: float
    peak_memory_gb: float | None
    diarizer: dict[str, str]
    made_at: str
    source: Source = "local"

    @property
    def key(self) -> str:
        return job_key(self.audio_sha256, self.engine, self.model, self.settings)


@dataclass(frozen=True, slots=True)
class Transcript:
    words: tuple[Word, ...]
    segments: tuple[Segment, ...]
    speakers: dict[str, Speaker]
    provenance: Provenance

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    def to_text(self) -> str:
        """One line per segment, `[MM:SS] S1: text` (`[HH:MM:SS]` past an hour; no label when the speaker is unknown)."""
        lines = []
        for seg in self.segments:
            seconds = int(seg.start)
            clock = (
                f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
                if seconds >= 3600
                else f"{seconds // 60:02d}:{seconds % 60:02d}"
            )
            who = f"{seg.speaker}: " if seg.speaker else ""
            lines.append(f"[{clock}] {who}{seg.text}\n")
        return "".join(lines)

    def to_markdown(self) -> str:
        """The readable view: a YAML header (Reco's transcript v3 field names), then one `[MM:SS] S1: text` turn per paragraph.

        `status` is `ok` whenever there is a transcript; `diarizer` is the model that labelled the voices, or `not_run` / `failed`
        when no word has a speaker (the stored JSON keeps the model and the reason).
        """
        p, d = self.provenance, self.provenance.diarizer
        voices = "".join(f"  {_scalar(label)}: {_scalar(v.name)}\n" for label, v in self.speakers.items())
        header = (
            "---\n"
            "transcript_version: 3\n"
            "kind: speech\n"
            "status: ok\n"
            f"audio:\n  duration_sec: {_scalar(round(p.audio_seconds, 1))}\n"
            f"speakers:{chr(10) + voices if voices else ' {}' + chr(10)}"
            f"diarizer: {_scalar(d['model'] if d.get('status') == 'ok' else d.get('status', 'not_run'))}\n"
            f"transcribed_at: {_scalar(p.made_at)}\n"
            f"transcriber: {_scalar(p.model)}\n"
            f"transcriber_runtime: {_scalar(p.runtime)}\n"
            "---\n"
        )
        return header + "".join(f"\n{line}\n" for line in self.to_text().splitlines())

    def to_json(self) -> dict[str, Any]:  # Any: the JSON document as stored
        """The one complete value. Word and segment times are rounded to milliseconds (`round(t, 3)`); nothing else is lossy."""
        body = asdict(self)
        for item in (*body["words"], *body["segments"]):
            item["start"], item["end"] = round(item["start"], 3), round(item["end"], 3)
        body["provenance"]["key"] = self.provenance.key
        return {"version": FORMAT_VERSION, **body}

    @classmethod
    def from_json(cls, raw: Mapping[str, Any]) -> Transcript:  # Any: parsed JSON, checked field by field below
        if raw.get("version") not in _READABLE:
            message = f"transcript format {raw.get('version')!r}; this reader knows {_READABLE}"
            raise UnknownVersionError(message)
        p = raw["provenance"]
        if p["source"] not in _SOURCES:
            message = f"source {p['source']!r} is not one of {_SOURCES}"
            raise ValueError(message)
        provenance = Provenance(
            engine=p["engine"],
            model=p["model"],
            runtime=p["runtime"],
            settings=dict(p["settings"]),
            audio_sha256=p["audio_sha256"],
            audio_seconds=p["audio_seconds"],
            seconds=p["seconds"],
            peak_memory_gb=p["peak_memory_gb"],
            diarizer=dict(p["diarizer"]),
            made_at=p["made_at"],
            source=p["source"],
        )  # the file's own "key" is ignored: it is derived
        words = tuple(Word(w["text"], w["start"], w["end"], w["probability"], w["speaker"]) for w in raw["words"])
        return cls(
            words=words,
            segments=tuple(Segment(s["start"], s["end"], s["text"], s["speaker"]) for s in raw["segments"]),
            speakers=_read_speakers(raw, words),
            provenance=provenance,
        )

    def save(self, path: Path) -> None:
        atomic_write_json(path, self.to_json())

    @classmethod
    def load(cls, path: Path) -> Transcript:
        return cls.from_json(json.loads(path.read_text(encoding="utf-8")))


def _read_speakers(raw: Mapping[str, Any], words: tuple[Word, ...]) -> dict[str, Speaker]:  # Any: parsed JSON
    if raw["version"] == 1:
        return speakers_of(words, dict(raw["speakers"]))
    return {label: Speaker(v["name"], v["seconds"], v["words"]) for label, v in raw["speakers"].items()}


_PLAIN = re.compile(r"[A-Za-z][A-Za-z0-9._/+-]*(?: [A-Za-z0-9._/+-]+)*")
_RESERVED = {"true", "false", "null", "yes", "no", "on", "off", "y", "n", "~"}


def _scalar(value: object) -> str:
    """A YAML scalar: numbers and plain words as they are, any other text single-quoted (a double-quoted JSON string if it holds `'`)."""
    if not isinstance(value, str):
        return str(value)
    if _PLAIN.fullmatch(value) and value.lower() not in _RESERVED:
        return value
    return json.dumps(value, ensure_ascii=False) if "'" in value or "\n" in value else f"'{value}'"
