"""lean-wire contract tests — golden wire bytes + the line-oriented invariant."""

from __future__ import annotations

from decimal import Decimal

from lean_wire import PruneEmpty, derive_columns, dump_model_for_wire, encode_tsv, prune_dict
from pydantic import BaseModel, Field


class Row(BaseModel):
    id: int
    title: str
    done: bool


# --- encode_tsv golden bytes -------------------------------------------------


def test_golden_header_and_rows() -> None:
    rows = [Row(id=1, title="alpha", done=True), Row(id=2, title="beta", done=False)]
    out = encode_tsv(rows, columns=["id", "title", "done"])
    assert out == "id\ttitle\tdone\n1\talpha\tTrue\n2\tbeta\tFalse\n"


def test_header_only_when_no_rows() -> None:
    assert encode_tsv([], columns=["id", "title"]) == "id\ttitle\n"


def test_none_cell_is_empty_string() -> None:
    assert encode_tsv([{"a": None, "b": "x"}], columns=["a", "b"]) == "a\tb\n\tx\n"


def test_missing_column_is_empty() -> None:
    # column declared but absent from the row dict → empty cell (csv-restval parity)
    assert encode_tsv([{"a": "x"}], columns=["a", "b"]) == "a\tb\nx\t\n"


def test_list_and_dict_cells_are_json_blobbed() -> None:
    out = encode_tsv([{"tags": ["x", "y"], "meta": {"k": 1}}], columns=["tags", "meta"])
    assert out == 'tags\tmeta\n["x","y"]\t{"k":1}\n'


def test_columns_follow_declared_order_not_alphabetical() -> None:
    out = encode_tsv([Row(id=1, title="a", done=True)], columns=list(Row.model_fields.keys()))
    assert out.splitlines()[0] == "id\ttitle\tdone"


# --- the line-oriented invariant (the newline bug fix) -----------------------


def test_embedded_newline_and_tab_are_escaped_not_raw() -> None:
    # THE fix: a stdlib csv writer would wrap this cell in quotes but keep the raw
    # \n inside; lean-wire escapes it so the record stays exactly one physical line.
    out = encode_tsv([{"note": "line1\nline2\tcol"}], columns=["note"])
    assert out == "note\nline1\\nline2\\tcol\n"


def test_one_record_is_exactly_one_line_even_with_multiline_cells() -> None:
    rows = [{"v": "a\nb\nc"}, {"v": "d\te"}, {"v": "plain"}]
    out = encode_tsv(rows, columns=["v"])
    # header + 3 rows = 4 physical lines; no cell tears a record apart.
    assert out.count("\n") == 4
    assert len(out.rstrip("\n").split("\n")) == 4


def test_backslash_is_escaped_reversibly() -> None:
    assert encode_tsv([{"p": "a\\b"}], columns=["p"]) == "p\na\\\\b\n"


def test_carriage_return_is_escaped() -> None:
    assert encode_tsv([{"p": "a\rb"}], columns=["p"]) == "p\na\\rb\n"


def test_basemodel_json_scalars() -> None:
    class Money(BaseModel):
        amount: Decimal

    out = encode_tsv([Money(amount=Decimal(0))], columns=["amount"])
    # Decimal(0) is informative, not empty — kept, JSON-dumped as a string scalar.
    assert out == "amount\n0\n"


# --- PruneEmpty / prune_dict -------------------------------------------------


def test_prune_empty_drops_empty_keeps_falsy() -> None:
    class M(PruneEmpty):
        count: int
        flag: bool
        name: str | None = None
        tags: list[str] = Field(default_factory=list)
        extra: dict = Field(default_factory=dict)

    dumped = M(count=0, flag=False).model_dump()
    # 0 and False are informative → kept; None/[]/{} → dropped.
    assert dumped == {"count": 0, "flag": False}


def test_prune_empty_cascades_through_nested_non_pruning_parent() -> None:
    class Inner(PruneEmpty):
        a: str | None = None
        b: int = 1

    class Outer(BaseModel):
        inner: Inner

    assert Outer(inner=Inner()).model_dump() == {"inner": {"b": 1}}


def test_prune_dict_is_top_level_only() -> None:
    payload = {"a": None, "b": "", "c": [], "d": {}, "keep": 0, "nested": {"x": None}}
    # top-level empties dropped; nested dict is non-empty so it stays as-is.
    assert prune_dict(payload) == {"keep": 0, "nested": {"x": None}}


def test_dump_model_for_wire_is_json_mode() -> None:
    class M(BaseModel):
        amount: Decimal

    assert dump_model_for_wire(M(amount=Decimal("1.5"))) == {"amount": "1.5"}


# --- derive_columns: the header is the union, never one row -------------------


def test_derive_columns_unions_every_rows_keys() -> None:
    """THE defect this function exists to remove.

    Rows are heterogeneous by construction whenever a producer prunes empties,
    so `rows[0]` is not the schema. Three separate callers hand-rolled this and
    all three read the first row, silently deleting every key it lacked — no
    error, no short row, nothing about the output looking wrong.
    """
    rows = [{"code": "quiet"}, {"code": "loud", "severity": "critical"}]

    assert derive_columns(rows) == ["code", "severity"]


def test_derive_columns_is_first_seen_order_not_sorted() -> None:
    """Declared field order is the contract; a later row's new key appends."""
    assert derive_columns([{"b": 1, "a": 2}, {"c": 3, "b": 4}]) == ["b", "a", "c"]


def test_derive_columns_of_a_model_row_is_its_declared_order() -> None:
    """The all-models case is unchanged — a dump preserves declared order, and
    the union across rows of one type IS that order."""

    class Row(BaseModel):
        id: int
        title: str

    assert derive_columns([Row(id=1, title="a"), Row(id=2, title="b")]) == ["id", "title"]


def test_derive_columns_of_no_rows_is_empty() -> None:
    assert derive_columns([]) == []


def test_omitting_columns_derives_them_and_widens_sparse_rows() -> None:
    """A column no row carries renders empty, so widening never shifts values."""
    rows = [{"code": "quiet"}, {"code": "loud", "severity": "critical"}]

    assert encode_tsv(rows) == "code\tseverity\nquiet\t\nloud\tcritical\n"


def test_explicit_columns_still_win_over_the_derived_union() -> None:
    """The type-driven caller keeps its declared order, including a field every
    row elided — that is what `columns=` is for and it stays authoritative."""
    rows = [{"title": "a"}]

    assert encode_tsv(rows, columns=["id", "title"]) == "id\ttitle\n\ta\n"
