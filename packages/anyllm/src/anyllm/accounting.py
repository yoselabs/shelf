"""Token accounting + Anthropic cache-tier cost — contract-neutral substrate.

Sits *below* the provider interface: any backend that speaks Anthropic-shaped
usage reuses :func:`extract_token_counts` and :func:`anthropic_cost_usd`. Kept
separate so it can be lifted into its own tiny package if a non-LLM holder ever
wants it (resolution 0007 reconcile-later note).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Per-1M-token pricing (USD), Anthropic public list. Update when the table moves.
_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-7": {"input": 15.00, "output": 75.00},
}


def extract_token_counts(usage: Mapping[str, Any] | Any) -> tuple[int, int, int, int]:
    """Pull ``(prompt_total, output, cache_creation, cache_read)`` from Anthropic usage.

    Anthropic splits the prompt across three counters: fresh ``input_tokens`` plus
    ``cache_creation_input_tokens`` (writes) and ``cache_read_input_tokens`` (reads).
    Reporting only ``input_tokens`` understates the prompt by 100-1000x on warm
    cache sessions. Returns the summed ``prompt_total`` plus the breakdown so a
    caller can price with cache tiers. Accepts a dict (claude-agent-sdk) or an
    attribute object (``anthropic.types.Usage``) transparently.
    """

    def _read(key: str) -> int:
        if isinstance(usage, Mapping):
            return int(usage.get(key) or 0)
        return int(getattr(usage, key, 0) or 0)

    fresh = _read("input_tokens")
    cache_creation = _read("cache_creation_input_tokens")
    cache_read = _read("cache_read_input_tokens")
    output = _read("output_tokens")
    prompt_total = fresh + cache_creation + cache_read
    return prompt_total, output, cache_creation, cache_read


def _price_for(model: str) -> tuple[float, float] | None:
    """Return ``(input_per_M, output_per_M)`` USD, or ``None`` if the model is unknown."""
    table = _PRICING.get(model)
    if table:
        return table["input"], table["output"]
    for known, prices in _PRICING.items():  # model ids sometimes carry a date suffix
        if model.startswith(known):
            return prices["input"], prices["output"]
    return None


def anthropic_cost_usd(model: str, *, prompt_tokens: int, completion_tokens: int, cache_creation: int, cache_read: int) -> float:
    """Compute USD cost from a token breakdown, or ``0.0`` when the model is unpriced.

    Anthropic cache tiers (public list): cache-read at 10% of fresh-input,
    cache-write at 125%; fresh-input is the remainder of the prompt.
    """
    prices = _price_for(model)
    if prices is None:
        return 0.0
    input_price, output_price = prices
    fresh_input = prompt_tokens - cache_creation - cache_read
    return (
        fresh_input / 1_000_000 * input_price
        + cache_creation / 1_000_000 * input_price * 1.25
        + cache_read / 1_000_000 * input_price * 0.10
        + completion_tokens / 1_000_000 * output_price
    )


__all__ = ["anthropic_cost_usd", "extract_token_counts"]
