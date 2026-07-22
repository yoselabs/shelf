r"""lean-wire — token-lean agent-facing wire payloads.

Two mechanisms, one job (stop a model reading noise instead of data):

- ``encode_tsv(rows, *, columns)`` — a **truly line-oriented** TSV codec. Unlike a
  stdlib ``csv`` writer, a cell never contains a raw tab or newline, so an agent
  can split the payload on ``\\n`` without a multi-line value tearing one record
  into several (see ``_tsv`` for the escaping contract).
- ``PruneEmpty`` — a pydantic base that drops empty fields (``None`` / ``""`` /
  ``[]`` / ``{}``) on the wire while keeping informative falsy values (``0`` /
  ``False``). Plus ``prune_dict`` (the free-function form) and
  ``dump_model_for_wire`` (the one wire-dump seam).

Semver is the **wire-format version**: any change to the bytes ``encode_tsv``
emits is a breaking (major) change.
"""

from __future__ import annotations

from lean_wire._prune import PruneEmpty, dump_model_for_wire, prune_dict
from lean_wire._tsv import encode_tsv

__all__ = [
    "PruneEmpty",
    "dump_model_for_wire",
    "encode_tsv",
    "prune_dict",
]
