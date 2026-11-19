"""Words from engine pieces, speakers onto words, segments out of words."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from any_speech.format import Segment, Word

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


@dataclass(frozen=True, slots=True)
class Turn:
    """One stretch of one voice; labels run S1, S2, ... by first appearance."""

    start: float
    end: float
    label: str


@dataclass(frozen=True, slots=True)
class Piece:
    """An engine's sub-word unit; a leading space starts a new word."""

    text: str
    start: float
    end: float
    probability: float | None = None


def words_from_pieces(pieces: Iterable[Piece]) -> tuple[Word, ...]:
    words: list[Word] = []
    for piece in pieces:
        if not piece.text.strip():
            continue
        if piece.text.startswith(" ") or not words:
            words.append(Word(piece.text.strip(), piece.start, piece.end, piece.probability))
            continue
        last = words[-1]
        weakest = _weakest(last.probability, piece.probability)
        words[-1] = Word(last.text + piece.text, last.start, piece.end, weakest)
    return tuple(words)


def _weakest(a: float | None, b: float | None) -> float | None:
    known = [p for p in (a, b) if p is not None]
    return min(known) if known else None


def assign_speakers(words: Sequence[Word], turns: Sequence[Turn]) -> tuple[Word, ...]:
    """Each word takes the label of the turn it overlaps most; a word in silence stays unlabelled."""
    out: list[Word] = []
    for word in words:
        best, label = 0.0, None
        for turn in turns:
            overlap = min(word.end, turn.end) - max(word.start, turn.start)
            if overlap > best:
                best, label = overlap, turn.label
        out.append(replace(word, speaker=label))
    return tuple(out)


def segments_from_words(words: Sequence[Word], *, pause: float = 0.5, cap: float = 15.0) -> tuple[Segment, ...]:
    """Cut where the speaker changes, at a pause of `pause` seconds, or when a segment passes `cap` seconds."""
    segments: list[Segment] = []
    run: list[Word] = []
    for word in words:
        if run and _breaks(run, word, pause, cap):
            segments.append(_segment(run))
            run = []
        run.append(word)
    if run:
        segments.append(_segment(run))
    return tuple(segments)


def _breaks(run: list[Word], word: Word, pause: float, cap: float) -> bool:
    return word.speaker != run[-1].speaker or word.start - run[-1].end >= pause or run[-1].end - run[0].start >= cap


def _segment(run: list[Word]) -> Segment:
    return Segment(run[0].start, run[-1].end, " ".join(w.text for w in run), run[0].speaker)
