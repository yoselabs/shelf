"""Default a2effect enricher: translates pydantic ValidationError to InputError."""

import pytest
from a2effect.enrichers import pydantic_validation_error_enricher
from a2effect.errors import AppError, InputError
from pydantic import BaseModel, Field, ValidationError


class _UserPayload(BaseModel):
    id: str = Field(min_length=1)
    age: int = Field(ge=0)


def _translate_a_rejected_payload() -> AppError | None:
    """Run the enricher over a payload the model must reject.

    `pytest.raises` makes the rejection part of the assertion. Written as a bare
    `try`/`except`, a model that stopped validating would leave the result unbound and
    the test would die on a `NameError` — a crash where it should have been a failure
    naming the constraint that went missing.
    """
    with pytest.raises(ValidationError) as excinfo:
        _UserPayload(id="", age=-3)  # pyrefly: ignore[bad-argument-type] — invalid on purpose; that is the test
    return pydantic_validation_error_enricher(excinfo.value)


def test_enricher_returns_none_for_unrelated_exception() -> None:
    assert pydantic_validation_error_enricher(KeyError("x")) is None


def test_enricher_returns_none_for_app_error_subclasses() -> None:
    assert pydantic_validation_error_enricher(InputError("x")) is None


def test_enricher_translates_validation_error_to_input_error() -> None:
    translated = _translate_a_rejected_payload()
    assert isinstance(translated, InputError)


def test_translated_error_carries_field_path_details() -> None:
    translated = _translate_a_rejected_payload()
    assert translated is not None
    assert "fields" in translated.details
    fields = translated.details["fields"]
    assert isinstance(fields, list)
    assert len(fields) == 2
    paths = {tuple(f["loc"]) for f in fields}
    assert ("id",) in paths
    assert ("age",) in paths


def test_translated_error_kind_is_input() -> None:
    translated = _translate_a_rejected_payload()
    assert translated is not None
    assert translated.kind == "input"


def test_input_error_is_app_error_subclass_with_kind_input() -> None:
    assert InputError.kind == "input"
    err = InputError("bad")
    assert err.base_kind == "input"


def test_translated_error_envelope_round_trips() -> None:
    translated = _translate_a_rejected_payload()
    assert translated is not None
    env = translated.to_envelope()
    assert env.type == "InputError"
    assert env.kind == "input"
    assert "fields" in env.details
