"""BDD scenarios for the error `code` and envelope v2 (a2effect 0.2.0).

Every concrete error names what went wrong as a snake_case `code`, declared on the class
and checked when the class is defined. The wire envelope is `{code, message, hint,
retryable, details, envelope_version}`: the class name, the kind and the chained cause
stay on the server.
"""

import pytest
from a2effect import AppError, UnexpectedDefect, codes
from a2effect.errors import AuthError, InfrastructureError, InputError, PolicyError


def test_a_concrete_subclass_without_code_fails_at_definition() -> None:
    with pytest.raises(TypeError, match=r"NoCodeError.*code"):

        class NoCodeError(AppError):
            kind = "input"


def test_an_inherited_code_does_not_count() -> None:
    class ParentError(AppError):
        kind = "input"
        code = "parent"

    with pytest.raises(TypeError, match=r"ChildError.*code"):

        class ChildError(ParentError):
            kind = "input"


def test_an_abstract_base_may_omit_code_and_kind() -> None:
    class FamilyError(AppError, abstract=True):
        pass

    class MemberError(FamilyError):
        kind = "input"
        code = "member"

    assert MemberError("x").to_envelope().code == "member"


def test_an_abstract_base_cannot_be_raised() -> None:
    class FamilyError(AppError, abstract=True):
        kind = "input"

    with pytest.raises(TypeError, match="abstract"):
        FamilyError("x")


def test_an_abstract_base_still_checks_a_kind_it_declares() -> None:
    with pytest.raises(TypeError, match="weird"):

        class FamilyError(AppError, abstract=True):
            kind = "weird"


@pytest.mark.parametrize("bad", ["NotFound", "not-found", "1st", "", "not found", "_x"])
def test_a_code_that_is_not_snake_case_is_rejected(bad: str) -> None:
    with pytest.raises(TypeError, match="snake_case"):
        type("BadCodeError", (AppError,), {"kind": "input", "code": bad})


def test_the_four_kind_bases_are_abstract() -> None:
    for base in (InputError, AuthError, PolicyError, InfrastructureError):
        with pytest.raises(TypeError, match="abstract"):
            base("x")

    class NotFoundError(InputError):
        kind = "input"
        code = "not_found"

    assert NotFoundError("x").http_status == 400


def test_the_envelope_has_exactly_the_v2_keys() -> None:
    class NotFoundError(AppError):
        kind = "input"
        code = "not_found"
        hint = "check the id"

    env = NotFoundError("no such thing", details={"ref": "a/b"}).to_envelope_dict()
    assert set(env) == {"code", "message", "hint", "retryable", "details", "envelope_version"}
    assert env == {
        "code": "not_found",
        "message": "no such thing",
        "hint": "check the id",
        "retryable": False,
        "details": {"ref": "a/b"},
        "envelope_version": "2",
    }


def test_the_envelope_carries_no_cause() -> None:
    class WrapError(AppError):
        kind = "infra"
        code = "wrap"

    try:
        msg = "wrapped"
        raise WrapError(msg) from ValueError("secret detail")
    except WrapError as caught:
        env = caught.to_envelope_dict()
    assert "secret detail" not in str(env)


def test_unexpected_defect_is_internal_error() -> None:
    assert UnexpectedDefect.code == "internal_error"
    assert UnexpectedDefect("boom").to_envelope().code == "internal_error"


def test_codes_lists_every_concrete_code_under_a_root() -> None:
    class RootError(AppError, abstract=True):
        pass

    class AError(RootError):
        kind = "input"
        code = "a_thing"

    class MidError(RootError, abstract=True):
        kind = "policy"

    class BError(MidError):
        kind = "policy"
        code = "b_thing"

    assert codes(RootError) == {"a_thing": AError, "b_thing": BError}


def test_codes_raises_on_a_duplicate() -> None:
    class RootError(AppError, abstract=True):
        pass

    class OneError(RootError):
        kind = "input"
        code = "same"

    class TwoError(RootError):
        kind = "input"
        code = "same"

    with pytest.raises(ValueError, match=r"same.*(OneError.*TwoError|TwoError.*OneError)"):
        codes(RootError)
