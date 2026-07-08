"""json-in-html extractor — package-level unit tests.

Ported from a2web's json_in_script suite (script-tag detectors, whole-response
JSON, ranking, window-var scanning, microdata + OpenGraph).
"""

from __future__ import annotations

from pathlib import Path

from json_in_html import (
    JsonPayload,
    extract_json_payloads,
    is_answer_bearing,
    is_json_content_type,
    parse_json_response,
    rank_payloads,
    sniff_json_body,
)

_FIX = Path(__file__).parent / "fixtures"


# --------------------------------------------------------------------- #
# Whole-response JSON
# --------------------------------------------------------------------- #


class TestIsJsonContentType:
    def test_application_json(self) -> None:
        assert is_json_content_type("application/json")
        assert is_json_content_type("application/json; charset=utf-8")
        assert is_json_content_type("APPLICATION/JSON")

    def test_suffix_json_types(self) -> None:
        assert is_json_content_type("application/vnd.api+json")
        assert is_json_content_type("application/ld+json")
        assert is_json_content_type("text/json")

    def test_non_json_types(self) -> None:
        assert not is_json_content_type("text/html")
        assert not is_json_content_type("application/pdf")
        assert not is_json_content_type("text/plain")

    def test_empty_or_none(self) -> None:
        assert not is_json_content_type("")
        assert not is_json_content_type(None)


class TestParseJsonResponse:
    def test_object_response_is_generic_payload(self) -> None:
        p = parse_json_response('{"products": [{"name": "Widget", "price": "9.99"}]}')
        assert p is not None
        assert p.source == "generic"
        assert p.script_id is None
        assert isinstance(p.data, dict)
        assert p.data["products"][0]["name"] == "Widget"
        assert p.byte_size > 0

    def test_array_response_is_generic_payload(self) -> None:
        p = parse_json_response('[{"title": "A"}, {"title": "B"}]')
        assert p is not None
        assert p.source == "generic"
        assert isinstance(p.data, list)
        assert len(p.data) == 2

    def test_non_json_returns_none(self) -> None:
        assert parse_json_response("<html>not json</html>") is None

    def test_malformed_json_returns_none(self) -> None:
        assert parse_json_response('{"a": 1,') is None

    def test_empty_returns_none(self) -> None:
        assert parse_json_response("") is None
        assert parse_json_response("   ") is None

    def test_json_scalar_root_returns_none(self) -> None:
        # A bare scalar is valid JSON but not a document we synthesize.
        assert parse_json_response("42") is None
        assert parse_json_response('"just a string"') is None


class TestSniffJsonBody:
    def test_json_object_bytes(self) -> None:
        assert sniff_json_body(b'{"a": 1}')

    def test_json_array_bytes(self) -> None:
        assert sniff_json_body(b'[{"x": 1}]')

    def test_leading_whitespace_tolerated(self) -> None:
        assert sniff_json_body(b'  \n  {"a": 1}')

    def test_html_is_not_json(self) -> None:
        assert not sniff_json_body(b"<html><body>hi</body></html>")

    def test_binary_prefix_skipped(self) -> None:
        # A PDF/binary body never starts with { or [ -> never decoded/parsed.
        assert not sniff_json_body(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3")

    def test_plain_text_not_json(self) -> None:
        assert not sniff_json_body(b"just some text")

    def test_empty(self) -> None:
        assert not sniff_json_body(b"")


# --------------------------------------------------------------------- #
# Script-tag detectors
# --------------------------------------------------------------------- #


def test_next_data_detected_from_trendyol_fixture() -> None:
    html = (_FIX / "trendyol_search_next_data.html").read_text()
    payloads = extract_json_payloads(html)
    next_data = [p for p in payloads if p.source == "next_data"]
    assert len(next_data) == 1
    p = next_data[0]
    assert p.script_id == "__NEXT_DATA__"
    assert isinstance(p.data, dict)
    assert "props" in p.data
    assert p.data["props"]["pageProps"]["products"][0]["brand"] == "adidas"
    assert p.byte_size > 0


def test_ld_json_product_detected() -> None:
    html = (_FIX / "ld_json_product.html").read_text()
    payloads = extract_json_payloads(html)
    ld = [p for p in payloads if p.source == "ld_json"]
    assert len(ld) == 1
    assert isinstance(ld[0].data, dict)
    assert ld[0].data["@type"] == "Product"
    assert ld[0].data["aggregateRating"]["ratingValue"] == "4.8"


def test_generic_application_json_detected_yandex_shape() -> None:
    html = (_FIX / "yandex_market_generic.html").read_text()
    payloads = extract_json_payloads(html)
    generic = [p for p in payloads if p.source == "generic"]
    assert len(generic) == 1
    assert isinstance(generic[0].data, dict)
    assert generic[0].data["products"][0]["name"] == "Mark Ryden MR9031Y_SJ"


def test_nuxt_data_detected() -> None:
    html = '<script id="__NUXT_DATA__" type="application/json">{"state":{"items":[1,2]}}</script>'
    payloads = extract_json_payloads(html)
    nuxt = [p for p in payloads if p.source == "nuxt_data"]
    assert len(nuxt) == 1
    assert nuxt[0].script_id == "__NUXT_DATA__"
    assert isinstance(nuxt[0].data, dict)
    assert nuxt[0].data["state"]["items"] == [1, 2]


def test_malformed_json_silently_skipped() -> None:
    html = (
        "<html><body>"
        '<script id="__NEXT_DATA__" type="application/json">{"valid":true}</script>'
        '<script type="application/ld+json">this is not json {{</script>'
        '<script type="application/ld+json">{"@type":"Article","headline":"ok"}</script>'
        "</body></html>"
    )
    payloads = extract_json_payloads(html)
    # Two valid: the __NEXT_DATA__ + the second ld+json. Malformed one is dropped.
    sources = [p.source for p in payloads]
    assert sources.count("next_data") == 1
    assert sources.count("ld_json") == 1


def test_empty_html_returns_empty_list() -> None:
    assert extract_json_payloads("") == []
    assert extract_json_payloads("<html><body><p>plain</p></body></html>") == []


def test_root_scalar_json_rejected() -> None:
    """JSON whose root is a bare number/string isn't useful — skipped."""
    html = '<script type="application/json">42</script>'
    assert extract_json_payloads(html) == []


# --------------------------------------------------------------------- #
# Ranking
# --------------------------------------------------------------------- #


def test_rank_payloads_prefers_strong_ld_json() -> None:
    """LD-JSON Product with >=3 populated fields beats __NEXT_DATA__."""
    strong_ld = JsonPayload(
        source="ld_json",
        data={
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "X",
            "brand": "Y",
            "offers": {"price": 1},
            "aggregateRating": {"ratingValue": "4.5"},
        },
        script_id=None,
        byte_size=200,
    )
    next_data = JsonPayload(
        source="next_data",
        data={"props": {"pageProps": {"products": [1, 2, 3]}}},
        script_id="__NEXT_DATA__",
        byte_size=1000,
    )
    ranked = rank_payloads([next_data, strong_ld])
    assert ranked[0] is strong_ld
    assert ranked[1] is next_data


def test_rank_payloads_strong_localbusiness_ranks_bucket_zero() -> None:
    """A strong LocalBusiness ld_json (contact schema) ranks ahead of opengraph."""
    strong_lb = JsonPayload(
        source="ld_json",
        data={
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": "VEITO",
            "telephone": "444 3 061",
            "email": "destek@veito.com",
            "url": "https://www.veito.com/",
            "image": "https://www.veito.com/images/logo.png",
        },
        script_id=None,
        byte_size=200,
    )
    og = JsonPayload(source="opengraph", data={"og:title": "Contact"}, script_id=None, byte_size=50)
    ranked = rank_payloads([og, strong_lb])
    assert ranked[0] is strong_lb


def test_rank_payloads_weak_organization_ranks_bucket_four() -> None:
    """An Organization with only name+url (2 fields) is weak — behind next_data + og."""
    weak_org = JsonPayload(
        source="ld_json",
        data={"@context": "https://schema.org", "@type": "Organization", "name": "x", "url": "https://x"},
        script_id=None,
        byte_size=80,
    )
    next_data = JsonPayload(
        source="next_data",
        data={"props": {"pageProps": {"x": 1}}},
        script_id="__NEXT_DATA__",
        byte_size=500,
    )
    ranked = rank_payloads([weak_org, next_data])
    assert ranked[0] is next_data


def test_rank_payloads_weak_ld_json_loses_to_next_data() -> None:
    """LD-JSON with only @type+@context loses to a populated next_data."""
    weak_ld = JsonPayload(
        source="ld_json",
        data={"@context": "https://schema.org", "@type": "WebSite", "name": "x"},
        script_id=None,
        byte_size=80,
    )
    next_data = JsonPayload(
        source="next_data",
        data={"props": {"pageProps": {"products": [1]}}},
        script_id="__NEXT_DATA__",
        byte_size=500,
    )
    ranked = rank_payloads([weak_ld, next_data])
    assert ranked[0] is next_data
    assert ranked[1] is weak_ld


def test_rank_handles_ld_json_graph_envelope() -> None:
    """Real-world LD-JSON nests inside @graph — recognizer walks one level down."""
    ld_graph = JsonPayload(
        source="ld_json",
        data={
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "Organization", "name": "x"},  # weak
                {
                    "@type": "Product",
                    "name": "P",
                    "brand": "B",
                    "offers": {"price": 1},
                    "aggregateRating": {"ratingValue": "5"},
                },
            ],
        },
        script_id=None,
        byte_size=400,
    )
    generic = JsonPayload(source="generic", data={"x": 1}, script_id=None, byte_size=20)
    ranked = rank_payloads([generic, ld_graph])
    assert ranked[0] is ld_graph


def test_rank_within_bucket_prefers_larger() -> None:
    a = JsonPayload(source="generic", data={"a": 1}, script_id=None, byte_size=100)
    b = JsonPayload(source="generic", data={"b": 1}, script_id=None, byte_size=5000)
    ranked = rank_payloads([a, b])
    assert ranked[0] is b
    assert ranked[1] is a


def test_ld_json_type_list_recognized() -> None:
    """@type may be a list of strings — a preferred member counts."""
    p = JsonPayload(
        source="ld_json",
        data={"@type": ["Thing", "Product"], "name": "X", "brand": "Y", "sku": "Z"},
        script_id=None,
        byte_size=100,
    )
    assert is_answer_bearing(p) is True


# --------------------------------------------------------------------- #
# window.<var> assignments
# --------------------------------------------------------------------- #


def test_window_var_state_assignment_detected() -> None:
    """`window.state = {...}` inside a text/javascript script is extracted."""
    html = (
        "<html><body>"
        '<script type="text/javascript">'
        'window.state = {"products":[{"name":"X","price":10}],"pageId":"search"};'
        "</script>"
        "</body></html>"
    )
    payloads = extract_json_payloads(html)
    wv = [p for p in payloads if p.source == "window_var"]
    assert len(wv) == 1
    assert wv[0].script_id == "state"
    assert isinstance(wv[0].data, dict)
    assert wv[0].data["products"][0]["name"] == "X"


def test_window_var_initial_state_with_strings_containing_braces() -> None:
    """String-aware bracket counting handles braces inside string literals."""
    html = '<script type="text/javascript">window.__INITIAL_STATE__ = {"label":"a{b}c","items":[{"id":1}]};var other = 42;</script>'
    payloads = extract_json_payloads(html)
    wv = [p for p in payloads if p.source == "window_var"]
    assert len(wv) == 1
    assert isinstance(wv[0].data, dict)
    assert wv[0].data["items"][0]["id"] == 1
    assert wv[0].data["label"] == "a{b}c"


def test_window_var_array_assignment_detected() -> None:
    """A `window.__DATA__ = [...]` array RHS is scanned the same as an object."""
    html = '<script type="text/javascript">window.__DATA__ = [{"id":1},{"id":2}];// trailing comment here padding length</script>'
    payloads = extract_json_payloads(html)
    wv = [p for p in payloads if p.source == "window_var"]
    assert len(wv) == 1
    assert isinstance(wv[0].data, list)
    assert wv[0].data[1]["id"] == 2


def test_window_var_not_extracted_when_followed_by_code_not_object() -> None:
    """`window.state = computeState()` (function call) is silently skipped."""
    html = "<script>window.state = computeState(); // padding to clear the minimum length</script>"
    assert [p for p in extract_json_payloads(html) if p.source == "window_var"] == []


def test_window_var_unknown_name_not_scanned() -> None:
    """Random `window.foo = {...}` (not in seed list) is not picked up."""
    html = '<script>window.foo = {"a":1}; // padding padding padding padding padding</script>'
    assert [p for p in extract_json_payloads(html) if p.source == "window_var"] == []


def test_window_var_ranks_after_ld_json_and_next_data() -> None:
    """LD-JSON strong > next_data > weak LD > window_var > generic."""
    wv = JsonPayload(source="window_var", data={"x": 1}, script_id="state", byte_size=100)
    next_data = JsonPayload(source="next_data", data={"x": 1}, script_id="__NEXT_DATA__", byte_size=100)
    ranked = rank_payloads([wv, next_data])
    assert ranked[0] is next_data
    assert ranked[1] is wv


# --------------------------------------------------------------------- #
# is_answer_bearing
# --------------------------------------------------------------------- #


class TestIsAnswerBearing:
    """`is_answer_bearing` — strong structured payloads only."""

    def test_strong_product_is_answer_bearing(self) -> None:
        p = JsonPayload(
            source="ld_json",
            data={"@type": "Product", "name": "X", "offers": {"price": 1}, "aggregateRating": {"ratingValue": "4.5"}},
            script_id=None,
            byte_size=100,
        )
        assert is_answer_bearing(p) is True

    def test_strong_localbusiness_is_answer_bearing(self) -> None:
        p = JsonPayload(
            source="ld_json",
            data={"@type": "LocalBusiness", "name": "VEITO", "telephone": "444 3 061", "email": "destek@veito.com"},
            script_id=None,
            byte_size=120,
        )
        assert is_answer_bearing(p) is True

    def test_strong_microdata_is_answer_bearing(self) -> None:
        p = JsonPayload(
            source="microdata",
            data={
                "type": ["https://schema.org/LocalBusiness"],
                "properties": {"name": "V", "telephone": "1", "email": "a@b"},
            },
            script_id=None,
            byte_size=120,
        )
        assert is_answer_bearing(p) is True

    def test_weak_organization_is_not_answer_bearing(self) -> None:
        p = JsonPayload(
            source="ld_json",
            data={"@type": "Organization", "name": "x", "url": "https://x"},
            script_id=None,
            byte_size=60,
        )
        assert is_answer_bearing(p) is False

    def test_opengraph_is_not_answer_bearing(self) -> None:
        p = JsonPayload(source="opengraph", data={"og:title": "T", "og:type": "website"}, script_id=None, byte_size=40)
        assert is_answer_bearing(p) is False

    def test_next_data_is_not_answer_bearing(self) -> None:
        p = JsonPayload(source="next_data", data={"props": {"a": 1}}, script_id="__NEXT_DATA__", byte_size=200)
        assert is_answer_bearing(p) is False


# --------------------------------------------------------------------- #
# Microdata
# --------------------------------------------------------------------- #


_MICRODATA_PRODUCT_HTML = """
<html><body>
  <div itemscope itemtype="https://schema.org/Product">
    <h1 itemprop="name">Stratos Hiking Boot</h1>
    <meta itemprop="sku" content="SK-2117">
    <img itemprop="image" src="https://example.com/boot.jpg">
    <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
      <meta itemprop="priceCurrency" content="USD">
      <span itemprop="price">189.00</span>
      <link itemprop="availability" href="https://schema.org/InStock">
    </div>
    <div itemprop="aggregateRating" itemscope itemtype="https://schema.org/AggregateRating">
      <meta itemprop="ratingValue" content="4.7">
      <meta itemprop="reviewCount" content="312">
    </div>
  </div>
</body></html>
"""


def test_microdata_product_is_extracted() -> None:
    payloads = extract_json_payloads(_MICRODATA_PRODUCT_HTML)
    micro = [p for p in payloads if p.source == "microdata"]
    assert len(micro) == 1
    items = micro[0].data
    assert isinstance(items, list)
    assert len(items) == 1
    item = items[0]
    assert item["type"] == ["https://schema.org/Product"]
    props = item["properties"]
    assert props["name"] == "Stratos Hiking Boot"
    assert props["sku"] == "SK-2117"
    assert props["image"] == "https://example.com/boot.jpg"
    # nested itemscope -> nested dict
    assert isinstance(props["offers"], dict)
    assert props["offers"]["properties"]["price"] == "189.00"
    assert props["offers"]["properties"]["priceCurrency"] == "USD"
    assert props["aggregateRating"]["properties"]["ratingValue"] == "4.7"


def test_microdata_strong_outranks_next_data() -> None:
    """A strong microdata Product (bucket 1) wins over next_data (bucket 2)."""
    html = _MICRODATA_PRODUCT_HTML + '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{}}}</script>'
    ranked = rank_payloads(extract_json_payloads(html))
    assert ranked[0].source == "microdata"


def test_microdata_weak_loses_to_next_data() -> None:
    """Microdata Product with <3 fields drops to bucket 4; next_data (bucket 2) wins."""
    html = """
    <html><body>
      <div itemscope itemtype="https://schema.org/Product">
        <span itemprop="name">Bare item</span>
      </div>
      <script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"x":1}}}</script>
    </body></html>
    """
    ranked = rank_payloads(extract_json_payloads(html))
    assert ranked[0].source == "next_data"


def test_microdata_unknown_type_falls_to_weak_bucket() -> None:
    html = """
    <html><body>
      <div itemscope itemtype="https://schema.org/LocalBusiness">
        <span itemprop="name">Some place</span>
        <span itemprop="address">123 Main St</span>
        <span itemprop="telephone">555-0100</span>
      </div>
    </body></html>
    """
    payloads = extract_json_payloads(html)
    micro = [p for p in payloads if p.source == "microdata"]
    assert len(micro) == 1
    # LocalBusiness IS in the preferred set + >=3 fields -> strong (bucket 1).
    ranked = rank_payloads(payloads)
    assert ranked[0].source == "microdata"


def test_microdata_multi_valued_itemprop_becomes_list() -> None:
    """Repeated itemprop names on one scope collapse into a list value."""
    html = """
    <html><body>
      <div itemscope itemtype="https://schema.org/Product">
        <span itemprop="category">boots</span>
        <span itemprop="category">outdoor</span>
        <span itemprop="category">hiking</span>
      </div>
    </body></html>
    """
    payloads = extract_json_payloads(html)
    micro = [p for p in payloads if p.source == "microdata"]
    assert isinstance(micro[0].data, list)
    props = micro[0].data[0]["properties"]
    assert props["category"] == ["boots", "outdoor", "hiking"]


def test_microdata_nested_scope_not_emitted_as_top_level() -> None:
    """The nested Offer inside Product is NOT a separate top-level item."""
    payloads = extract_json_payloads(_MICRODATA_PRODUCT_HTML)
    micro = [p for p in payloads if p.source == "microdata"]
    items = micro[0].data
    assert len(items) == 1  # only the outer Product, not Offer/AggregateRating


# --------------------------------------------------------------------- #
# OpenGraph
# --------------------------------------------------------------------- #


def test_opengraph_meta_tags_are_collected() -> None:
    html = """
    <html><head>
      <meta property="og:title" content="The Boots Article">
      <meta property="og:type" content="product">
      <meta property="og:url" content="https://example.com/p/123">
      <meta property="product:price:amount" content="189.00">
      <meta property="article:tag" content="hiking">
    </head><body></body></html>
    """
    payloads = extract_json_payloads(html)
    og = [p for p in payloads if p.source == "opengraph"]
    assert len(og) == 1
    data = og[0].data
    assert isinstance(data, dict)
    assert data["og:title"] == "The Boots Article"
    assert data["og:type"] == "product"
    assert data["product:price:amount"] == "189.00"
    assert data["article:tag"] == "hiking"


def test_opengraph_ranks_after_framework_state() -> None:
    """OG (bucket 3) sits behind next_data (bucket 2)."""
    html = """
    <html><head>
      <meta property="og:title" content="hi">
      <meta property="og:type" content="article">
    </head><body>
      <script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{}}}</script>
    </body></html>
    """
    ranked = rank_payloads(extract_json_payloads(html))
    sources = [p.source for p in ranked]
    assert sources.index("next_data") < sources.index("opengraph")


def test_opengraph_irrelevant_meta_tags_skipped() -> None:
    """Non-OG meta tags (e.g. viewport, description) must NOT be emitted."""
    html = """
    <html><head>
      <meta name="description" content="something">
      <meta name="viewport" content="width=device-width">
      <meta property="twitter:card" content="summary">
    </head></html>
    """
    payloads = extract_json_payloads(html)
    og = [p for p in payloads if p.source == "opengraph"]
    assert og == []


# --------------------------------------------------------------------- #
# Robustness
# --------------------------------------------------------------------- #


def test_page_with_no_structured_data_returns_empty() -> None:
    html = "<html><body><p>Just text.</p></body></html>"
    assert extract_json_payloads(html) == []
