"""Conversion engines (ADR 0021 / R142).

Each engine wraps one library, normalizes the output to Markdown, and grades
fidelity via :mod:`convert_md.fidelity`. Heavy imports (docling/torch,
pandoc, markitdown) live inside ``convert`` so importing this module is cheap —
only the engine actually selected pays the import cost.

Engines raise :class:`ConversionError` on failure so the dispatcher can walk
the format's fallback chain.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import TYPE_CHECKING

from convert_md.base import ConversionError, ConversionResult
from convert_md.fidelity import grade

if TYPE_CHECKING:
    from pathlib import Path


def _ver(pkg: str) -> str:
    try:
        return _pkg_version(pkg)
    except PackageNotFoundError:
        return "unknown"


def _result(markdown: str, engine: str, source_size: int, *, check_yield: bool = True) -> ConversionResult:
    fidelity, lost, warnings = grade(markdown=markdown, source_size=source_size, check_yield=check_yield)
    return ConversionResult(body_markdown=markdown, engine=engine, fidelity=fidelity, lost=lost, warnings=warnings)


class DoclingEngine:
    """PDF → Markdown via docling 2.x (MIT, local, best-in-class tables).

    docling 2.x's typer cap is overridden in pyproject (uv ``override-dependencies``)
    so it coexists with a2kit's CLI on typer 0.26 — we use only the library API.
    """

    name = f"docling@{_ver('docling')}"

    def convert(self, path: Path) -> ConversionResult:
        """Convert a PDF to Markdown via docling, forcing CPU inference."""
        try:
            from docling.datamodel.base_models import InputFormat  # noqa: PLC0415 — lazy heavy import
            from docling.datamodel.pipeline_options import (  # noqa: PLC0415
                AcceleratorDevice,
                AcceleratorOptions,
                PdfPipelineOptions,
            )
            from docling.document_converter import DocumentConverter, PdfFormatOption  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - dep is a hard dep
            msg = f"docling unavailable: {exc}"
            raise ConversionError(msg) from exc
        # Force CPU: the default MPS (Apple Metal) device crashes the rt_detr_v2
        # layout model on float64, and headless/CPU is the typical deploy target anyway.
        opts = PdfPipelineOptions()
        opts.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CPU)
        converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})
        try:
            result = converter.convert(str(path))
            markdown = result.document.export_to_markdown()
        except Exception as exc:  # docling raises a variety of errors on bad PDFs
            msg = f"docling failed on {path.name}: {exc}"
            raise ConversionError(msg) from exc
        return _result(markdown, self.name, path.stat().st_size, check_yield=False)


class PandocEngine:
    """DOCX → Markdown via pandoc, preserving tracked changes."""

    name = f"pandoc@{_ver('pypandoc-binary')}"

    def convert(self, path: Path) -> ConversionResult:
        """Convert a DOCX to GitHub-flavored Markdown via pandoc, keeping tracked changes."""
        try:
            import pypandoc  # noqa: PLC0415 — lazy heavy import
        except ImportError as exc:  # pragma: no cover
            msg = f"pypandoc unavailable: {exc}"
            raise ConversionError(msg) from exc
        try:
            engine = f"pandoc@{pypandoc.get_pandoc_version()}"
            markdown = pypandoc.convert_file(
                str(path),
                "gfm",
                extra_args=["--track-changes=all", "--wrap=none"],
            )
        except Exception as exc:
            msg = f"pandoc failed on {path.name}: {exc}"
            raise ConversionError(msg) from exc
        return _result(markdown, engine, path.stat().st_size, check_yield=False)


class MarkitdownEngine:
    """PPTX/XLSX/generic → Markdown via markitdown."""

    name = f"markitdown@{_ver('markitdown')}"

    def convert(self, path: Path) -> ConversionResult:
        """Convert a PPTX/XLSX/generic file to Markdown via markitdown, appending PPTX speaker notes."""
        try:
            from markitdown import MarkItDown  # noqa: PLC0415 — lazy heavy import
        except ImportError as exc:  # pragma: no cover
            msg = f"markitdown unavailable: {exc}"
            raise ConversionError(msg) from exc
        try:
            markdown = MarkItDown().convert(str(path)).text_content
        except Exception as exc:
            msg = f"markitdown failed on {path.name}: {exc}"
            raise ConversionError(msg) from exc
        if path.suffix.lower() == ".pptx":
            notes = _pptx_notes(path)
            if notes:
                markdown = f"{markdown}\n\n## Speaker notes\n\n{notes}"
        return _result(markdown, self.name, path.stat().st_size, check_yield=False)


class OpenpyxlEngine:
    """XLSX → Markdown tables via openpyxl (per-sheet, fallback for markitdown)."""

    name = f"openpyxl@{_ver('openpyxl')}"

    def convert(self, path: Path) -> ConversionResult:
        """Convert an XLSX to Markdown tables via openpyxl, one section per worksheet."""
        try:
            from openpyxl import load_workbook  # noqa: PLC0415 — lazy import
        except ImportError as exc:  # pragma: no cover
            msg = f"openpyxl unavailable: {exc}"
            raise ConversionError(msg) from exc
        try:
            wb = load_workbook(path, read_only=True, data_only=True)
            parts: list[str] = []
            for ws in wb.worksheets:
                parts.append(f"## {ws.title}\n")
                rows = list(ws.iter_rows(values_only=True))
                parts.extend(_rows_to_markdown(rows))
            markdown = "\n".join(parts)
        except Exception as exc:
            msg = f"openpyxl failed on {path.name}: {exc}"
            raise ConversionError(msg) from exc
        return _result(markdown, self.name, path.stat().st_size, check_yield=False)


class TrafilaturaEngine:
    """HTML → Markdown via trafilatura (best boilerplate removal)."""

    name = f"trafilatura@{_ver('trafilatura')}"

    def convert(self, path: Path) -> ConversionResult:
        """Convert an HTML file to Markdown via trafilatura, stripping boilerplate."""
        try:
            import trafilatura  # noqa: PLC0415 — lazy import
        except ImportError as exc:  # pragma: no cover
            msg = f"trafilatura unavailable: {exc}"
            raise ConversionError(msg) from exc
        html = path.read_text(encoding="utf-8", errors="replace")
        markdown = trafilatura.extract(html, output_format="markdown", include_tables=True)
        if not markdown:
            msg = f"trafilatura extracted nothing from {path.name}"
            raise ConversionError(msg)
        return _result(markdown, self.name, path.stat().st_size)


class Html2TextEngine:
    """HTML → Markdown via html2text (fallback)."""

    name = f"html2text@{_ver('html2text')}"

    def convert(self, path: Path) -> ConversionResult:
        """Convert an HTML file to Markdown via html2text (unbounded line width)."""
        try:
            import html2text  # noqa: PLC0415 — lazy import
        except ImportError as exc:  # pragma: no cover
            msg = f"html2text unavailable: {exc}"
            raise ConversionError(msg) from exc
        html = path.read_text(encoding="utf-8", errors="replace")
        converter = html2text.HTML2Text()
        converter.body_width = 0
        markdown = converter.handle(html)
        return _result(markdown, self.name, path.stat().st_size)


# --- helpers -----------------------------------------------------------------


def _pptx_notes(path: Path) -> str:
    """Recover speaker notes markitdown drops (R142 pptx note pass)."""
    try:
        from pptx import Presentation  # noqa: PLC0415 — lazy import
    except ImportError:  # pragma: no cover
        return ""
    try:
        prs = Presentation(str(path))
    except Exception:  # noqa: BLE001  -- fallback chain: any engine failure falls through to the next engine
        return ""
    chunks: list[str] = []
    for i, slide in enumerate(prs.slides, start=1):
        if slide.has_notes_slide:
            text = slide.notes_slide.notes_text_frame.text.strip()
            if text:
                chunks.append(f"**Slide {i}:** {text}")
    return "\n\n".join(chunks)


def _rows_to_markdown(rows: list[tuple]) -> list[str]:
    if not rows:
        return [""]
    out: list[str] = []
    header = rows[0]
    out.append("| " + " | ".join(_cell(c) for c in header) + " |")
    out.append("| " + " | ".join("---" for _ in header) + " |")
    out.extend("| " + " | ".join(_cell(c) for c in row) + " |" for row in rows[1:])
    out.append("")
    return out


def _cell(value: object) -> str:
    return "" if value is None else str(value).replace("|", "\\|").replace("\n", " ")


__all__ = [
    "DoclingEngine",
    "Html2TextEngine",
    "MarkitdownEngine",
    "OpenpyxlEngine",
    "PandocEngine",
    "TrafilaturaEngine",
]
