"""page-tsv contract tests — type routing + the consumer-aware render seam."""

from __future__ import annotations

import json

import pytest
from page_tsv import (
    EncodingPlan,
    Page,
    Response,
    build_encoding_plan,
    encode_envelope,
    encode_page_tsv,
    encode_page_tsv_dict,
    format_response,
    infer_format_hint,
    is_basemodel,
    render,
    render_plain,
)
from pydantic import BaseModel


class Row(BaseModel):
    id: int
    title: str


class Nested(BaseModel):
    id: int
    tags: list[str]  # non-scalar → not TSV-able


# --- type-driven inference ---------------------------------------------------


def test_page_of_scalar_rows_infers_page_tsv() -> None:
    assert infer_format_hint(Page[Row]) == "page-tsv"


def test_list_of_scalar_rows_infers_tsv() -> None:
    assert infer_format_hint(list[Row]) == "tsv"


def test_page_of_nonscalar_rows_falls_back_to_json() -> None:
    assert infer_format_hint(Page[Nested]) == "json"


def test_single_model_and_dict_and_any_are_json() -> None:
    assert infer_format_hint(Row) == "json"
    assert infer_format_hint(dict) == "json"
    assert infer_format_hint(None) == "json"


def test_build_encoding_plan_envelope_for_flat_array_field() -> None:
    class Envelope(BaseModel):
        summary: str
        rows: list[Row]  # a flat-array field → envelope plan

    plan = build_encoding_plan(Envelope)
    assert plan.kind == "envelope"
    assert plan.tsv_fields == ("rows",)


def test_is_basemodel_unwraps_optional_and_annotated() -> None:
    assert is_basemodel(Row) is Row
    assert is_basemodel(Row | None) is Row
    assert is_basemodel(int) is None


# --- encode_page_tsv ---------------------------------------------------------


def test_encode_page_tsv_embeds_tsv_string_with_discriminator() -> None:
    page = Page[Row](items=[Row(id=1, title="a"), Row(id=2, title="b")])
    envelope = json.loads(encode_page_tsv(page))
    assert envelope["_items_format"] == "tsv"
    assert envelope["items"] == "id\ttitle\n1\ta\n2\tb\n"
    assert envelope["next_cursor"] is None


def test_encode_page_tsv_dict_matches_the_page_path() -> None:
    payload = {"items": [{"id": 1, "title": "a"}], "next_cursor": "c1"}
    envelope = json.loads(encode_page_tsv_dict(payload))
    assert envelope["items"] == "id\ttitle\n1\ta\n"
    assert envelope["next_cursor"] == "c1"
    assert envelope["_items_format"] == "tsv"


# --- render: consumer is a parameter, never sniffed --------------------------


def test_render_llm_compresses_page_to_tsv() -> None:
    page = Page[Row](items=[Row(id=1, title="a")])
    rendered = render(page, "llm")
    assert rendered.format == "json"  # outer envelope is JSON
    assert json.loads(rendered.text)["_items_format"] == "tsv"


def test_render_code_and_machine_never_compress() -> None:
    page = Page[Row](items=[Row(id=1, title="a")])
    for consumer in ("code", "machine"):
        rendered = render(page, consumer)  # type: ignore[arg-type]
        body = json.loads(rendered.text)
        # plain JSON: items is a list of objects, no TSV blob, no discriminator
        assert isinstance(body["items"], list)
        assert "_items_format" not in body


def test_render_llm_flat_list_is_tsv() -> None:
    rendered = render([Row(id=1, title="a"), Row(id=2, title="b")], "llm", plan=EncodingPlan("tsv"))
    assert rendered.format == "tsv"
    assert rendered.text == "id\ttitle\n1\ta\n2\tb\n"


def test_render_structured_payload_is_lazy_plain() -> None:
    rendered = render(Row(id=1, title="a"), "code")
    assert rendered.structured == {"id": 1, "title": "a"}


# --- encode_envelope / render_plain -----------------------------------------


def test_encode_envelope_tsv_fields_become_blobs() -> None:
    class Env(BaseModel):
        summary: str
        rows: list[Row]

    out = json.loads(encode_envelope(Env(summary="s", rows=[Row(id=1, title="a")]), ("rows",)))
    assert out["summary"] == "s"
    assert out["rows"] == "id\ttitle\n1\ta\n"
    assert out["_rows_format"] == "tsv"


def test_render_plain_reproduces_from_already_plain_payload() -> None:
    # a middleware that runs after the result is plain JSON re-derives the wire text
    text = render_plain([{"id": 1, "title": "a"}], EncodingPlan("tsv"))
    assert text == "id\ttitle\n1\ta\n"


# --- format_response legacy adapter -----------------------------------------


def test_format_response_page_tsv_requires_page() -> None:
    resp = format_response(Page[Row](items=[Row(id=1, title="a")]), format_hint="page-tsv")
    assert isinstance(resp, Response)
    assert json.loads(resp.data)["_items_format"] == "tsv"


def test_format_response_rejects_page_tsv_on_nonpage() -> None:
    with pytest.raises(TypeError):
        format_response({"x": 1}, format_hint="page-tsv")
