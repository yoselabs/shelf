"""Property-based tests, additive on top of the BDD-scenario example suite.

See docs/runbooks/property-based-testing.md. Targets the kind-taxonomy state
machine (`register_error_kind` / `_resolve_base_kind`) — the package's own "invalid
states unrepresentable" claim (a subclass MUST declare a valid kind, an extension
MUST resolve to a core base) is exactly the kind of validation-boundary logic a
handful of examples under-samples.

Caveat, stated up front: `_KIND_EXTENSIONS` is genuinely module-level, process-wide,
never-reset state (confirmed: no fixture resets it anywhere in this package's test
suite, and `register_error_kind` silently overwrites on a repeat name rather than
raising). Every generated extension name below is `pbt_`-prefixed so it can never
collide with the five real core kinds or the hand-written fixture names
(`token_bucket`, `rate_limit`) elsewhere in this package's suite; the "registers a
name" test and the "asserts a name was never registered" test additionally use two
DISJOINT sub-prefixes (`pbt_reg_` / `pbt_unreg_`) so a rare Hypothesis collision
between the two can't make either test's premise false. This suite deliberately
leaves junk registrations behind in the process, by design, rather than pretending
isolation exists where it doesn't.
"""

from __future__ import annotations

import pytest
from a2effect import AppError, register_error_kind
from a2effect.errors import _CORE_KINDS, _resolve_base_kind
from hypothesis import given, settings
from hypothesis import strategies as st

_CORE = sorted(_CORE_KINDS)
_NON_CORE_BASE = st.text(alphabet=st.characters(categories=["L"]), min_size=1, max_size=10).filter(lambda s: s not in _CORE_KINDS)
# Two disjoint prefixes: one test registers names, the other asserts a name was
# NEVER registered — sharing a prefix would let a rare Hypothesis-generated
# collision between the two tests make the second test's premise false.
_REGISTERED_EXT_NAME = st.text(alphabet=st.characters(categories=["L", "N"]), min_size=1, max_size=12).map(lambda s: f"pbt_reg_{s}")
_UNREGISTERED_EXT_NAME = st.text(alphabet=st.characters(categories=["L", "N"]), min_size=1, max_size=12).map(lambda s: f"pbt_unreg_{s}")


@given(name=st.sampled_from(_CORE))
@settings(max_examples=10)
def test_property_registering_any_core_kind_name_always_raises(name: str) -> None:
    """For every one of the five core kinds, not just one hand-picked example,
    attempting to redefine it as an extension raises.
    """
    with pytest.raises(ValueError, match="cannot redefine core kind"):
        register_error_kind(name, base="infra")


@given(bad_base=_NON_CORE_BASE)
@settings(max_examples=100)
def test_property_registering_with_a_non_core_base_always_raises(bad_base: str) -> None:
    """For any string that is provably not one of the five core kinds, using it
    as an extension's base raises — not just the one hand-picked bad value.
    """
    with pytest.raises(ValueError, match="extension base must be a core kind"):
        register_error_kind("pbt_probe_target", base=bad_base)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]


@given(ext_name=_REGISTERED_EXT_NAME, base=st.sampled_from(_CORE), retryable=st.booleans())
@settings(max_examples=100)
def test_property_a_valid_extension_resolves_to_its_declared_base(ext_name: str, base: str, retryable: bool) -> None:
    """For any valid (unique, prefixed) extension name and any core base, an
    AppError subclass declaring that kind resolves base_kind to exactly the
    base it was registered with, and inherits the extension's retryable default
    when the subclass doesn't override it.
    """
    register_error_kind(ext_name, base=base, retryable=retryable)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
    assert _resolve_base_kind(ext_name) == base

    error_cls = type(f"Err_{ext_name}", (AppError,), {"kind": ext_name})
    err = error_cls("boom")
    assert err.base_kind == base
    assert err.retryable is retryable


@given(ext_name=_UNREGISTERED_EXT_NAME)
@settings(max_examples=50)
def test_property_unregistered_kind_always_raises_type_error(ext_name: str) -> None:
    """For any generated `pbt_`-prefixed name that was NOT registered this run,
    declaring an AppError subclass with it raises — the taxonomy really is
    closed to declared kinds, not permissive of typos.
    """
    error_cls_name = f"Err_unreg_{ext_name}"
    with pytest.raises(TypeError, match="unknown kind"):
        type(error_cls_name, (AppError,), {"kind": ext_name})
