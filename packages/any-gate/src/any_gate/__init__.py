"""any-gate: remember what already passed, under a key of exactly what it ran on; run tests sized to their work, guarded against hangs."""

from __future__ import annotations

from any_gate.plan import Resources, detect, too_wide, workers
from any_gate.receipts import Receipts, key
from any_gate.run import Outcome, Stage, run_tests

__all__ = ["Outcome", "Receipts", "Resources", "Stage", "detect", "key", "run_tests", "too_wide", "workers"]
