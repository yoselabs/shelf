"""Conversion contract — ``ConversionResult`` + the ``ConversionEngine`` seam.

Engines convert one binary to Markdown and self-report fidelity. The result is
what the attachment pipeline writes into a stub's ``conversion`` frontmatter
block (ADR 0021). Engines keep their heavy imports (docling/torch, pandoc,
markitdown) inside ``convert`` so importing this package stays cheap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

Fidelity = Literal["high", "partial", "failed"]


@dataclass
class ConversionResult:
    """Outcome of converting one binary to Markdown."""

    body_markdown: str
    engine: str  # "<name>@<version>"
    fidelity: Fidelity = "high"
    lost: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class ConversionEngine(Protocol):
    """A single-format converter. ``name`` is ``<engine>@<version>``."""

    name: str

    def convert(self, path: Path) -> ConversionResult:
        """Convert the file at ``path`` to Markdown and return the graded result."""
        ...


class ConversionError(RuntimeError):
    """An engine failed to convert — the dispatcher walks to the next in chain."""


__all__ = ["ConversionEngine", "ConversionError", "ConversionResult", "Fidelity"]
