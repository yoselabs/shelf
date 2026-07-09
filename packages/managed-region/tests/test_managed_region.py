"""managed_region — marker-agnostic idempotent managed block."""

from __future__ import annotations

from managed_region import replace_region

S = "<<S>>"
E = "<<E>>"


def test_appends_region_when_absent_preserving_prose() -> None:
    body = "human notes above\n"
    out = replace_region(body, "MACHINE", start_marker=S, end_marker=E)
    assert S in out and E in out
    assert "MACHINE" in out
    assert out.index("human notes above") < out.index(S)


def test_replaces_in_place_preserving_outside() -> None:
    body = "top prose\n"
    first = replace_region(body, "OLD", start_marker=S, end_marker=E)
    first = first + "bottom prose added by a human\n"
    second = replace_region(first, "NEW", start_marker=S, end_marker=E)
    assert "NEW" in second
    assert "OLD" not in second
    assert "top prose" in second
    assert "bottom prose added by a human" in second
    assert second.count(S) == 1
    assert second.count(E) == 1


def test_idempotent_same_content() -> None:
    body = "prose\n"
    once = replace_region(body, "V1", start_marker=S, end_marker=E)
    twice = replace_region(once, "V1", start_marker=S, end_marker=E)
    assert once == twice
    assert twice.count(S) == 1
    assert twice.count(E) == 1


def test_empty_body_yields_bare_region() -> None:
    out = replace_region("", "X", start_marker=S, end_marker=E)
    assert out == f"{S}\nX\n{E}\n"


def test_embedded_marker_neutralized_via_escape() -> None:
    # A realistic escape breaks the marker INTERNALLY so the raw substring no longer
    # appears (mirrors a2kay inserting "(escaped)" inside its HTML-comment sentinels).
    def escape(content: str) -> str:
        return content.replace(S, "<<S_>>").replace(E, "<<E_>>")

    body = "prose\n"
    poison = f"real\n{E}\ninjected\n{S}\nmore"
    out = replace_region(body, poison, start_marker=S, end_marker=E, escape=escape)
    # Exactly one real pair — the embedded markers were neutralized (raw S/E gone from content).
    assert out.count(S) == 1
    assert out.count(E) == 1
    assert "<<S_>>" in out and "<<E_>>" in out

    # Idempotent even with poison: re-running yields identical output.
    again = replace_region(out, poison, start_marker=S, end_marker=E, escape=escape)
    assert again == out


def test_without_escape_content_written_verbatim() -> None:
    out = replace_region("", "plain content", start_marker=S, end_marker=E)
    assert "plain content" in out
