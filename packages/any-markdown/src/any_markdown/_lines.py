"""Line arithmetic shared by the document type and its chunker."""

from __future__ import annotations


def line_starts(text: str) -> list[int]:
    """Offset of each line's first character, ascending — the index a bisect reads."""
    starts = [0]
    idx = text.find("\n")
    while idx != -1:
        starts.append(idx + 1)
        idx = text.find("\n", idx + 1)
    return starts
