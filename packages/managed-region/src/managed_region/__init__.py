"""Managed region — an idempotent, prose-preserving machine-owned block between markers.

The direnv/terraform/`~/.*rc` "managed block" pattern, marker-agnostic. Given a
document, a start marker, and an end marker, write machine-owned content between the
markers and leave the human prose outside them untouched. Re-running with the same
content is idempotent (the region is replaced, never stacked) and the document always
holds exactly one marker pair.

Structure only — the caller owns the *markers* and the *escape format*. When markers
can appear inside the content (converted/untrusted input), pass an ``escape`` callback
that neutralizes them so embedded text cannot introduce a corrupting second pair; how
to neutralize a given marker is caller policy, not the primitive's business.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_NL = "\n"


def replace_region(
    body: str,
    region_content: str,
    *,
    start_marker: str,
    end_marker: str,
    escape: Callable[[str], str] | None = None,
) -> str:
    """Write ``region_content`` between the markers in ``body``, preserving outside prose.

    - An existing ``start_marker … end_marker`` pair has its *contents* replaced in place;
      text before the start and after the end is left byte-for-byte intact.
    - With no pair yet, one region is appended after the existing prose (or returned bare
      for an empty body).
    - If ``escape`` is given, markers embedded in ``region_content`` are neutralized first,
      so the result always has exactly one real pair.
    """
    content = escape(region_content) if escape else region_content
    block = f"{start_marker}{_NL}{content.rstrip(_NL)}{_NL}{end_marker}"
    start = body.find(start_marker)
    end = body.find(end_marker)
    if start != -1 and end != -1 and end > start:
        before = body[:start]
        after = body[end + len(end_marker) :]
        return f"{before}{block}{after}"
    if body == "":
        return f"{block}{_NL}"
    return f"{body.rstrip(_NL)}{_NL}{_NL}{block}{_NL}"


__all__ = ["replace_region"]
