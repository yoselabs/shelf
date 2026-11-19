"""MLX's buffer cache grows without bound unless capped; this owns the cap and the peak figure."""

from __future__ import annotations

from typing import Protocol

CACHE_MB = 512
_GB = 1e9


class Memory(Protocol):
    def cap(self, megabytes: int) -> None: ...
    def reset_peak(self) -> None: ...
    def peak_gb(self) -> float: ...
    def clear(self) -> None: ...


class MlxMemory:
    """The real thing: `mlx.core`, imported only when the first model is used."""

    def __init__(self) -> None:
        import mlx.core as mx  # noqa: PLC0415  the engine is optional

        self._mx = mx

    def cap(self, megabytes: int) -> None:
        self._mx.set_cache_limit(megabytes * 2**20)

    def reset_peak(self) -> None:
        self._mx.reset_peak_memory()

    def peak_gb(self) -> float:
        return float(self._mx.get_peak_memory()) / _GB

    def clear(self) -> None:
        self._mx.clear_cache()
