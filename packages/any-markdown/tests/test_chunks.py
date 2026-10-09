"""Retrieval windows that know their line, their headings and the section that opens them.

Moved from a2kay's search chunker tests with the code they cover.
"""

from __future__ import annotations

import json

from any_markdown import Chunk, Markdown

_SIZE = 1100


def _wire(text: str) -> int:
    return len(json.dumps(text, ensure_ascii=False).encode()) - 2


def _chunks(text: str) -> list[Chunk]:
    return Markdown(text).chunks(size=_SIZE, overlap=150, part=11_000, measure=_wire)


def test_empty_text_yields_no_chunks() -> None:
    assert _chunks("") == []
    assert _chunks("   \n  ") == []


def test_short_doc_is_one_chunk_at_line_1() -> None:
    chunks = _chunks("# Title\nA short body.\n")
    assert len(chunks) == 1
    assert chunks[0].line == 1
    assert "short body" in chunks[0].text


def test_heading_sections_split() -> None:
    chunks = _chunks("# A\nalpha content\n\n## B\nbravo content\n\n## C\ncharlie content\n")
    assert len(chunks) >= 3
    joined = " ".join(c.text for c in chunks)
    assert "alpha" in joined and "bravo" in joined and "charlie" in joined


def test_long_section_produces_overlapping_windows_with_growing_lines() -> None:
    chunks = _chunks("# Big\n" + ("word " * 1000))
    assert len(chunks) >= 2
    assert all(len(c.text) <= _SIZE for c in chunks)
    assert [c.line for c in chunks] == sorted(c.line for c in chunks)


def test_every_chunk_reports_the_line_its_text_starts_on() -> None:
    sections = [f"## Section {i}\n" + "\n".join(f"body line {i}.{j}" for j in range(120)) for i in range(6)]
    text = "\n\n".join(sections) + "\n"
    lines = text.split("\n")
    chunks = _chunks(text)
    assert len(chunks) > 6, "sections long enough to window, or this proves nothing"
    for chunk in chunks:
        first = chunk.text.split("\n", 1)[0]
        assert lines[chunk.line - 1].endswith(first) or lines[chunk.line - 1] == first


def test_a_document_with_no_newlines_is_all_line_1() -> None:
    assert {c.line for c in _chunks("x" * (_SIZE * 3))} == {1}


def test_a_chunk_names_the_section_that_opens_it_and_the_headings_above_it() -> None:
    text = "Lead text.\n\n# Harbor\n\n## Sync\n\nMerge with CRDTs.\n\n```\n# not a heading\n```\n\n## Sync\n\nAgain.\n"
    chunks = _chunks(text)

    def holding(words: str) -> Chunk:
        return next(c for c in chunks if words in c.text)

    assert holding("Lead text.").section == "lines:1-1"
    assert holding("Merge with CRDTs.").section == "sync"
    assert holding("Merge with CRDTs.").headings == ("Harbor", "Sync")
    assert holding("not a heading").section == "sync"  # a fenced `#` line opens no section
    assert holding("Again.").section == "sync-2"  # deduped as `.sections` dedupes it


def test_a_chunk_inside_a_long_line_names_the_characters_it_holds() -> None:
    text = "## Transcript\n\n" + "слово " * 6000 + "больше 20 штук " + "слово " * 4000 + "\n"
    doc = Markdown(text)
    hit = next(c for c in _chunks(text) if "больше 20 штук" in c.text)
    assert hit.section is not None and hit.section.startswith("lines:3:")
    found = doc.section(hit.section)
    assert found is not None
    assert "больше 20 штук" in text[found.start : found.end]


def test_without_a_part_no_line_is_long() -> None:
    text = "## T\n\n" + "word " * 5000 + "\n"
    assert all(not (c.section or "").startswith("lines:3:") for c in Markdown(text).chunks())
