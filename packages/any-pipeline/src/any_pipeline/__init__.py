"""A pipeline is a typed value: async stages composed with ``>>`` and ``gather``, each bounded by a required Limit.

``await run(gather(hear, diar) >> label, items, key=..., workers=4)`` returns a Report: a value or a Failed per item and a
record per stage run. A stage fed the wrong shape, a stage with no limit, an unhandled failure case, and an edit of a frozen
item are rejected by the type checker; see the README for what is checked when and what no tool can guarantee.
"""

from __future__ import annotations

from any_pipeline.filestore import FileStore
from any_pipeline.outcome import Failed, Ok, Outcome, Report, StageFailed, StageRecord
from any_pipeline.run import run, run_one
from any_pipeline.stage import Flow, Limit, MemoryStore, Persistent, Stage, Store, blocking, gather, gather3, gather4

__all__ = [
    "Failed",
    "FileStore",
    "Flow",
    "Limit",
    "MemoryStore",
    "Ok",
    "Outcome",
    "Persistent",
    "Report",
    "Stage",
    "StageFailed",
    "StageRecord",
    "Store",
    "blocking",
    "gather",
    "gather3",
    "gather4",
    "run",
    "run_one",
]
