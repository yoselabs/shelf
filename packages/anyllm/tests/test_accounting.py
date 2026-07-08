"""Token accounting + Anthropic cache-tier cost — the contract-neutral substrate."""

from __future__ import annotations

from anyllm.accounting import anthropic_cost_usd, extract_token_counts


class _Usage:
    """Attribute-style usage object (mirrors anthropic.types.Usage)."""

    input_tokens = 100
    cache_creation_input_tokens = 20
    cache_read_input_tokens = 30
    output_tokens = 40


def test_extract_token_counts_from_mapping() -> None:
    usage = {
        "input_tokens": 100,
        "cache_creation_input_tokens": 20,
        "cache_read_input_tokens": 30,
        "output_tokens": 40,
    }
    prompt_total, output, cache_creation, cache_read = extract_token_counts(usage)
    assert prompt_total == 150  # 100 + 20 + 30 — cache tiers included, not just fresh input
    assert (output, cache_creation, cache_read) == (40, 20, 30)


def test_extract_token_counts_from_object() -> None:
    prompt_total, output, cache_creation, cache_read = extract_token_counts(_Usage())
    assert (prompt_total, output, cache_creation, cache_read) == (150, 40, 20, 30)


def test_extract_token_counts_tolerates_missing_keys() -> None:
    assert extract_token_counts({}) == (0, 0, 0, 0)
    assert extract_token_counts({"input_tokens": None}) == (0, 0, 0, 0)


def test_cost_unknown_model_is_zero() -> None:
    assert anthropic_cost_usd("some-local-model", prompt_tokens=1000, completion_tokens=1000, cache_creation=0, cache_read=0) == 0.0


def test_cost_prices_fresh_input_and_output() -> None:
    # haiku: input 1.00/M, output 5.00/M. 1M fresh in + 1M out = 1.00 + 5.00.
    cost = anthropic_cost_usd("claude-haiku-4-5", prompt_tokens=1_000_000, completion_tokens=1_000_000, cache_creation=0, cache_read=0)
    assert cost == 6.0


def test_cost_applies_cache_tiers() -> None:
    # cache-read at 10% of input price, cache-write at 125%.
    cost = anthropic_cost_usd(
        "claude-haiku-4-5",
        prompt_tokens=1_000_000,  # all served from cache-read
        completion_tokens=0,
        cache_creation=0,
        cache_read=1_000_000,
    )
    assert cost == 0.10  # 1M * 1.00/M * 0.10


def test_cost_matches_model_by_prefix() -> None:
    # a dated model id still resolves via prefix match.
    cost = anthropic_cost_usd("claude-sonnet-4-6-20260101", prompt_tokens=1_000_000, completion_tokens=0, cache_creation=0, cache_read=0)
    assert cost == 3.0
