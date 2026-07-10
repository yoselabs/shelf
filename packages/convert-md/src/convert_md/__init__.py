"""Opinionated document→Markdown conversion (ADR 0021 / R142).

``convert(path)`` runs the per-format dispatch table + fallback chain and always
returns a :class:`ConversionResult` (never raises). Engine choice is a code-level
default, not a config file. The result carries a model-free fidelity grade.

This is the conversion *mechanism*; a consumer keeps its own presentation policy
(e.g. how a low-fidelity result is surfaced to a reader). No a2kay dependency.
"""

from __future__ import annotations

from convert_md.base import ConversionEngine, ConversionError, ConversionResult, Fidelity
from convert_md.dispatch import convert, fallback_chain_for, select_engine
from convert_md.engines import (
    Html2TextEngine,
    MammothEngine,
    MarkitdownEngine,
    OpenpyxlEngine,
    PymupdfLlmEngine,
    TrafilaturaEngine,
)
from convert_md.fidelity import grade
from convert_md.html import SourceKind, convert_html

__all__ = [
    "ConversionEngine",
    "ConversionError",
    "ConversionResult",
    "Fidelity",
    "Html2TextEngine",
    "MammothEngine",
    "MarkitdownEngine",
    "OpenpyxlEngine",
    "PymupdfLlmEngine",
    "SourceKind",
    "TrafilaturaEngine",
    "convert",
    "convert_html",
    "fallback_chain_for",
    "grade",
    "select_engine",
]
