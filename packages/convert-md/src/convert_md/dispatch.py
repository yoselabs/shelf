"""Opinionated per-format conversion dispatch (ADR 0021 / R142).

Engine choice is encoded here, not configured. Each format has a primary engine
and a fallback chain; the runner walks the chain on failure and only declares
``failed`` when every engine in the chain gives up. Legacy binary Office formats
are normalized through LibreOffice headless, then re-dispatched.

There is deliberately no ``conversion.yml`` and no ``entity.reconvert`` verb —
reconversion is a future migration script, not a runtime knob.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from convert_md.base import ConversionError, ConversionResult
from convert_md.engines import (
    DoclingEngine,
    Html2TextEngine,
    MarkitdownEngine,
    OpenpyxlEngine,
    PandocEngine,
    TrafilaturaEngine,
)

# Primary → fallback, per extension (R142 verdict table).
_CHAINS: dict[str, list[type]] = {
    ".pdf": [DoclingEngine],
    ".docx": [PandocEngine, MarkitdownEngine],
    ".pptx": [MarkitdownEngine],
    ".xlsx": [MarkitdownEngine, OpenpyxlEngine],
    ".html": [TrafilaturaEngine, Html2TextEngine],
    ".htm": [TrafilaturaEngine, Html2TextEngine],
    ".xls": [MarkitdownEngine, OpenpyxlEngine],
}

_LEGACY = {".doc", ".ppt", ".xls"}  # LibreOffice-normalized then re-dispatched
_LEGACY_TARGET = {".doc": ".docx", ".ppt": ".pptx", ".xls": ".xlsx"}


def fallback_chain_for(path: Path) -> list[type]:
    """Return the engine classes to try for ``path``, in order."""
    return _CHAINS.get(path.suffix.lower(), [])


def select_engine(path: Path) -> type | None:
    """The primary engine class for ``path`` (None if the format is unsupported)."""
    chain = fallback_chain_for(path)
    return chain[0] if chain else None


def convert(path: Path) -> ConversionResult:
    """Convert ``path`` to Markdown, walking the format's fallback chain.

    Legacy ``.doc/.ppt/.xls`` are first normalized via LibreOffice headless and
    re-dispatched through the modern chain. If every engine fails, a ``failed``
    result is returned (never an exception) so the attachment pipeline can still
    write a stub.
    """
    suffix = path.suffix.lower()
    if suffix in _LEGACY and suffix not in _CHAINS:
        return _convert_legacy(path)

    chain = fallback_chain_for(path)
    if not chain:
        return ConversionResult(
            body_markdown="",
            engine="none",
            fidelity="failed",
            lost=["all"],
            warnings=[f"unsupported_format:{suffix or 'none'}"],
        )

    errors: list[str] = []
    for engine_cls in chain:
        engine = engine_cls()
        try:
            return engine.convert(path)
        except ConversionError as exc:
            errors.append(str(exc))
            continue
    return ConversionResult(
        body_markdown="",
        engine=chain[-1]().name,
        fidelity="failed",
        lost=["all"],
        warnings=errors or ["conversion_failed"],
    )


def _convert_legacy(path: Path) -> ConversionResult:
    """Normalize a legacy binary via LibreOffice, then re-dispatch."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is None:
        return ConversionResult(
            body_markdown="",
            engine="libreoffice@unknown",
            fidelity="failed",
            lost=["all"],
            warnings=["libreoffice_not_installed"],
        )
    target_suffix = _LEGACY_TARGET[path.suffix.lower()]
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", target_suffix.lstrip("."), "--outdir", tmp, str(path)],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            return ConversionResult(
                body_markdown="",
                engine="libreoffice@unknown",
                fidelity="failed",
                lost=["all"],
                warnings=[f"libreoffice_normalize_failed:{exc}"],
            )
        normalized = Path(tmp) / (path.stem + target_suffix)
        if not normalized.exists():
            return ConversionResult(
                body_markdown="",
                engine="libreoffice@unknown",
                fidelity="failed",
                lost=["all"],
                warnings=["normalize_no_output"],
            )
        return convert(normalized)


__all__ = ["convert", "fallback_chain_for", "select_engine"]
