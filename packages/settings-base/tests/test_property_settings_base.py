"""Property-based tests, additive on top of test_settings_base.py.

See docs/runbooks/property-based-testing.md for the convention this follows and why.
Covers the two invariant-bearing functions: ${VAR} interpolation (including a
security-relevant property no example test names — no recursive re-expansion) and
the secret-stripping YAML source's core guarantee (an excluded field never leaks).
"""

from __future__ import annotations

import string
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic_settings import BaseSettings
from settings_base import SecretStrippingYamlSource, resolve_env_refs

_VAR_NAME = st.text(alphabet=string.ascii_uppercase + "_", min_size=1, max_size=8).filter(lambda s: s[0] != "_" or len(s) > 1)
_PLAIN_TEXT = st.text(alphabet=string.printable, max_size=40)


# ── resolve_env_refs ────────────────────────────────────────────────────────


@given(name=_VAR_NAME, value=_PLAIN_TEXT)
@settings(max_examples=200)
def test_property_set_var_never_survives_literally(name: str, value: str) -> None:
    """Invariant: a ${VAR} reference for a var that IS set is always fully expanded."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv(name, value)
        out = resolve_env_refs(f"prefix-${{{name}}}-suffix")
    assert f"${{{name}}}" not in out
    assert out == f"prefix-{value}-suffix"


@given(name=_VAR_NAME)
@settings(max_examples=200)
def test_property_unset_var_left_literal(name: str) -> None:
    """Invariant: a ${VAR} reference for a var that is NOT set is left verbatim."""
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv(name, raising=False)
        template = f"prefix-${{{name}}}-suffix"
        assert resolve_env_refs(template) == template


@given(text=_PLAIN_TEXT)
@settings(max_examples=200)
def test_property_no_refs_is_identity(text: str) -> None:
    """Invariant: a string with no ${...} pattern passes through unchanged."""
    from settings_base import _ENV_REF_RE  # noqa: PLC0415

    if not _ENV_REF_RE.search(text):
        assert resolve_env_refs(text) == text


@given(name=_VAR_NAME, inner=_VAR_NAME)
@settings(max_examples=200)
def test_property_no_recursive_expansion(name: str, inner: str) -> None:
    """Security-relevant invariant, undocumented in the docstring: if VAR's own value
    contains another ${OTHER} reference, that inner reference is NOT recursively
    expanded — resolve_env_refs is single-pass. An attacker-influenced env value
    should not be able to chain-expand a second variable.
    """
    if name == inner:
        return
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv(inner, "leaked")
        mp.setenv(name, f"${{{inner}}}")
        out = resolve_env_refs(f"${{{name}}}")
    assert out == f"${{{inner}}}"
    assert "leaked" not in out


# ── SecretStrippingYamlSource ───────────────────────────────────────────────


_FIELD_NAME = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8)
_FIELD_VALUE = st.text(alphabet=string.ascii_letters + string.digits, min_size=0, max_size=20)


@given(
    fields=st.dictionaries(_FIELD_NAME, _FIELD_VALUE, min_size=1, max_size=6),
    exclude_fraction=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_property_excluded_fields_never_leak(fields: dict[str, str], exclude_fraction: float) -> None:
    """The core security invariant: no excluded (secret) field name ever appears
    in the dict SecretStrippingYamlSource returns, regardless of which subset of
    fields is excluded — and every kept field survives with its original value.
    """
    keys = list(fields)
    cut = int(len(keys) * exclude_fraction)
    excluded = set(keys[:cut])
    kept = set(keys[cut:])

    class _Model(BaseSettings):
        model_config = {"extra": "allow"}

    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "config.yaml"
        cfg.write_text(
            "\n".join(f'"{k}": "{v}"' for k, v in fields.items()) + "\n",
            encoding="utf-8",
        )
        source = SecretStrippingYamlSource(_Model, exclude=excluded, yaml_file=cfg)
        data = source()

    for name in excluded:
        assert name not in data, f"excluded field {name!r} leaked into the loaded settings"
    for name in kept:
        assert data.get(name) == fields[name]
