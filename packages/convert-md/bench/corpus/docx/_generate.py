"""Generate the synthesized single-capability docx bench fixtures (design.md D2).

Run isolated:  uv run --no-project --with python-docx python3 _generate.py

Each fixture carries **one** docx capability and an otherwise-minimal body, so a
scoring difference between engines attributes to that single feature (D1). docx
is semantic OOXML, so synthesis loses no realism the bench cares about — the
inverse of the PDF corpus's real-document rule (design.md D2).

Not committed: nothing here is a user document. Regenerate deterministically.
"""

from __future__ import annotations

from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

HERE = Path(__file__).parent


def _baseline() -> docx.Document:
    """Headings + paragraphs + inline emphasis — the convergent common case."""
    d = docx.Document()
    d.add_heading("Quarterly Field Notes", level=1)
    d.add_heading("Summary", level=2)
    p = d.add_paragraph("The pilot ran for ")
    p.add_run("six weeks").bold = True
    p.add_run(" across ")
    p.add_run("three regions").italic = True
    p.add_run(" with no downtime.")
    d.add_heading("Detail", level=2)
    d.add_paragraph("Throughput held steady. Latency improved after week two.")
    d.add_heading("Deeper detail", level=3)
    d.add_paragraph("A third-level heading, to test heading-depth nesting.")
    return d


def _nested_table() -> docx.Document:
    """A single table with a header row and merged/nested structure."""
    d = docx.Document()
    d.add_paragraph("Financial summary (consolidated):")
    table = d.add_table(rows=4, cols=3)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text = "Metric", "FY24", "FY25"
    data = [
        ("Revenue", "1,204", "1,388"),
        ("Operating income", "212", "301"),
        ("Net margin", "9.1%", "11.4%"),
    ]
    for r, (a, b, c) in enumerate(data, start=1):
        cells = table.rows[r].cells
        cells[0].text, cells[1].text, cells[2].text = a, b, c
    return d


def _nested_list() -> docx.Document:
    """Nested bullet + numbered lists — indentation/level fidelity."""
    d = docx.Document()
    d.add_paragraph("Rollout checklist:")
    d.add_paragraph("Prepare environment", style="List Bullet")
    d.add_paragraph("Install runtime", style="List Bullet 2")
    d.add_paragraph("Verify version", style="List Bullet 2")
    d.add_paragraph("Migrate data", style="List Bullet")
    d.add_paragraph("First numbered step", style="List Number")
    d.add_paragraph("Second numbered step", style="List Number")
    return d


def _footnote() -> docx.Document:
    """A real footnote reference. python-docx has no high-level footnote API,
    so inject the minimal OOXML: a footnoteReference run pointing at a
    footnotes part. Kept deliberately small — one note.
    """
    d = docx.Document()
    p = d.add_paragraph("This claim needs a source")
    # footnote reference run
    run = p.add_run()
    ref = OxmlElement("w:footnoteReference")
    ref.set(qn("w:id"), "1")
    rpr = OxmlElement("w:rPr")
    vert = OxmlElement("w:vertAlign")
    vert.set(qn("w:val"), "superscript")
    rpr.append(vert)
    run._r.append(rpr)
    run._r.append(ref)
    p.add_run(" and the body continues after the marker.")
    # NOTE: a fully-wired footnotes.xml part requires editing the package
    # relationships; for the bench we test whether engines surface the marker
    # + note text. If this proves too thin, swap for a real authored file (D2).
    _attach_footnotes_part(d)
    return d


def _attach_footnotes_part(d: docx.Document) -> None:
    """Best-effort: add a footnotes part with one note. If the docx library
    version doesn't expose the part cleanly, the reference still exercises the
    engines' handling of an orphan marker (documented in README)."""
    try:
        from docx.opc.constants import CONTENT_TYPE as CT
        from docx.opc.constants import RELATIONSHIP_TYPE as RT

        footnotes_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:footnote w:id="1"><w:p><w:r><w:t>'
            "Primary source: internal telemetry, 2026-07."
            "</w:t></w:r></w:p></w:footnote></w:footnotes>"
        )
        part = d.part
        from docx.opc.packuri import PackURI
        from docx.opc.part import Part

        uri = PackURI("/word/footnotes.xml")
        fn_part = Part(uri, CT.WML_FOOTNOTES, footnotes_xml.encode("utf-8"), part.package)
        part.relate_to(fn_part, RT.FOOTNOTES)
    except Exception as exc:  # noqa: BLE001 — best-effort synthesis, documented fallback
        print(f"  (footnotes part not attached: {exc}; marker-only fixture)")


def _tracked_changes() -> docx.Document:
    """One insertion + one deletion as real w:ins / w:del revision markup.
    This is pandoc's sole differentiator — the whole reason the fixture exists.
    """
    d = docx.Document()
    p = d.add_paragraph("The migration took ")

    # deleted text: "four" (w:del > w:r > w:delText)
    del_el = OxmlElement("w:del")
    del_el.set(qn("w:author"), "editor")
    del_el.set(qn("w:date"), "2026-07-10T00:00:00Z")
    del_el.set(qn("w:id"), "1")
    del_r = OxmlElement("w:r")
    del_t = OxmlElement("w:delText")
    del_t.text = "four"
    del_r.append(del_t)
    del_el.append(del_r)
    p._p.append(del_el)

    # inserted text: "two" (w:ins > w:r > w:t)
    ins_el = OxmlElement("w:ins")
    ins_el.set(qn("w:author"), "editor")
    ins_el.set(qn("w:date"), "2026-07-10T00:00:00Z")
    ins_el.set(qn("w:id"), "2")
    ins_r = OxmlElement("w:r")
    ins_t = OxmlElement("w:t")
    ins_t.text = "two"
    ins_r.append(ins_t)
    ins_el.append(ins_r)
    p._p.append(ins_el)

    p.add_run(" weeks longer than planned.")
    return d


def _embedded_image() -> docx.Document:
    """A paragraph + one embedded PNG — image-handling axis (extract/ref/drop)."""
    d = docx.Document()
    d.add_paragraph("Figure 1 shows the deployment topology:")
    png = _tiny_png()
    img_path = HERE / "_fixture_image.png"
    img_path.write_bytes(png)
    d.add_picture(str(img_path), width=Pt(120))
    d.add_paragraph("The topology is a single hub with three spokes.")
    return d


def _tiny_png() -> bytes:
    """Build a guaranteed-valid 8x8 solid-colour PNG from scratch (no asset,
    no external lib beyond stdlib zlib) so python-docx's image validator is
    satisfied."""
    import struct
    import zlib

    width = height = 8
    # raw image data: each row prefixed with a filter byte (0), RGB pixels
    row = b"\x00" + b"\x44\x88\xcc" * width
    raw = row * height

    def _chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit, colour type 2 (RGB)
    idat = zlib.compress(raw)
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


_FIXTURES = {
    "clean_baseline": _baseline,
    "table_nested": _nested_table,
    "list_nested": _nested_list,
    "footnote": _footnote,
    "tracked_changes": _tracked_changes,
    "image_embedded": _embedded_image,
}


def main() -> None:
    for name, builder in _FIXTURES.items():
        doc = builder()
        out = HERE / f"{name}.docx"
        doc.save(str(out))
        print(f"wrote {out.relative_to(HERE.parent.parent)} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
