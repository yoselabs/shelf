"""Finding a symbol's span, the functions of a module, the function around a line, and the symbol hash."""

from py_symbols import Span, find, functions, innermost, symbol_hash

CODE = """FEE = 3
RATE: float = 0.5
type Money = int


def late_fee(days):
    return days * FEE


class Loan:
    limit = 2

    @property
    def renew(self):
        def inner():
            return 1
        return inner

    class Nested:
        def deep(self):
            return 2
"""


def test_find_returns_the_span_of_a_module_level_symbol() -> None:
    assert find(CODE, "late_fee") == Span("late_fee", 6, 7, "def late_fee(days):\n    return days * FEE", 7)
    for name in ("FEE", "RATE", "Money", "Loan"):
        assert find(CODE, name) is not None
    rate = find(CODE, "RATE")
    assert rate is not None and rate.text == "RATE: float = 0.5"


def test_find_reaches_a_member_and_includes_its_decorators() -> None:
    renew = find(CODE, "Loan.renew")
    assert renew is not None
    assert (renew.start, renew.end, renew.body) == (13, 17, 15)
    assert renew.text.startswith("@property\ndef renew(self):")
    assert find(CODE, "Loan.limit") is not None
    assert find(CODE, "Loan.Nested.deep") is not None


def test_find_is_none_for_what_is_not_there() -> None:
    assert find(CODE, "nope") is None
    assert find(CODE, "Loan.nope") is None
    assert find(CODE, "late_fee.inner") is None  # only classes are entered
    assert find("def broken(:", "broken") is None


def test_functions_are_qualified_outer_first_and_skip_classes() -> None:
    assert [span.name for span in functions(CODE)] == ["late_fee", "Loan.renew", "Loan.renew.inner", "Loan.Nested.deep"]
    assert functions("def broken(:") == []


def test_innermost_names_the_deepest_function_holding_the_line() -> None:
    spans = functions(CODE)
    assert innermost(spans, 7) == "late_fee"
    assert innermost(spans, 16) == "Loan.renew.inner"
    assert innermost(spans, 17) == "Loan.renew"
    assert innermost(spans, 1) is None
    assert innermost(spans, 14) is None  # the decorator and the def line run when the class body does


def test_symbol_hash_follows_the_symbol_alone() -> None:
    before = symbol_hash(CODE, "late_fee")
    assert before is not None and len(before) == 12
    assert symbol_hash(CODE.replace("days * FEE", "days"), "late_fee") != before
    assert symbol_hash(CODE.replace("FEE = 3", "FEE = 4"), "late_fee") == before
    assert symbol_hash(CODE, "late_fee", length=8) == before[:8]
    assert symbol_hash(CODE, "nope") is None
