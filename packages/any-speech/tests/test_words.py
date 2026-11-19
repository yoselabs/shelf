from __future__ import annotations

import pytest
from any_speech import Turn, Word, assign_speakers, segments_from_words, words_from_pieces
from any_speech.words import Piece


def test_pieces_without_a_leading_space_join_the_previous_word() -> None:
    pieces = [Piece(" Про", 1.0, 1.2, 0.9), Piece("сто", 1.2, 1.5, 0.5), Piece(".", 1.5, 1.6, 0.8), Piece(" Да", 1.7, 1.9, 1.0)]
    words = words_from_pieces(pieces)
    assert [(w.text, w.start, w.end) for w in words] == [("Просто.", 1.0, 1.6), ("Да", 1.7, 1.9)]
    assert words[0].probability == pytest.approx(0.5)  # the weakest piece: one bad piece makes a doubtful word


def test_a_piece_with_only_spaces_is_dropped() -> None:
    assert words_from_pieces([Piece(" ", 0.0, 0.1, 1.0)]) == ()


@pytest.mark.parametrize(
    ("word", "label"),
    [
        (Word("a", 0.0, 1.0), "S1"),
        (Word("b", 4.5, 6.5), "S2"),  # 0.5 s in S1's turn, 1.5 s in S2's
        (Word("c", 9.0, 9.5), None),  # silence after the last turn
    ],
)
def test_word_takes_the_turn_it_overlaps_most(word: Word, label: str | None) -> None:
    turns = [Turn(0.0, 5.0, "S1"), Turn(5.0, 8.0, "S2")]
    assert assign_speakers((word,), turns)[0].speaker == label


def test_no_turns_leaves_speakers_unset() -> None:
    assert assign_speakers((Word("a", 0.0, 1.0),), [])[0].speaker is None


def test_segments_break_on_a_pause_a_speaker_change_and_the_length_cap() -> None:
    words = (
        Word("раз", 0.0, 0.4, speaker="S1"),
        Word("два", 0.5, 0.9, speaker="S1"),
        Word("три", 2.0, 2.4, speaker="S1"),  # pause 1.1 s
        Word("четыре", 2.5, 2.9, speaker="S2"),  # speaker change
        Word("пять", 3.0, 20.0, speaker="S2"),  # runs past the cap
        Word("шесть", 20.1, 20.4, speaker="S2"),
    )
    segs = segments_from_words(words, pause=0.5, cap=15.0)
    assert [(s.text, s.speaker) for s in segs] == [
        ("раз два", "S1"),
        ("три", "S1"),
        ("четыре пять", "S2"),
        ("шесть", "S2"),
    ]
    assert (segs[0].start, segs[0].end) == (0.0, 0.9)
