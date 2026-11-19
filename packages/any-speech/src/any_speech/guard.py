"""The memory budget: a run over it is a failure, not a quiet success."""

from __future__ import annotations

DEFAULT_BUDGET_GB = 4.0


class MemoryBudgetError(RuntimeError):
    """An engine's measured peak went past the budget."""


def check_peak(peak_gb: float | None, budget_gb: float) -> None:
    if peak_gb is not None and peak_gb > budget_gb:
        message = f"peak memory {peak_gb:.2f} GB is over the {budget_gb:.2f} GB budget"
        raise MemoryBudgetError(message)
