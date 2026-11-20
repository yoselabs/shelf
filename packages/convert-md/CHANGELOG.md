# convert-md changelog

Arrow-notation, AI-facing: one line per contract-shape change (old ⇒ new).

- 0.12.0: breaking  ⇒  `grade(*, markdown, source_size, check_yield=True)` -> `grade(*, markdown, source_size)` (yield ratio checked) plus `grade_container(*, markdown, source_size)` (ZIP containers and PDFs: every check but yield; the structure check still reads `source_size`); `check_yield=` removed; `grade_container` exported from `convert_md`
- 0.8.0 — `convert_html(html, *, url, source_kind)` ⇒ `convert_html(html, *, url, source_kind, include_links=False)` (additive; `include_links=True` keeps in-body anchors as `[label](url)` on the trafilatura path).
- 0.10.0 — new `missing_engines(suffixes) -> dict[str, list[str]]` (additive); each engine class gains `modules: tuple[str, ...]`.
- 0.11.0: breaking  ⇒  `convert(path)` -> `convert(path, *, env)` and `missing_engines(suffixes)` -> `missing_engines(suffixes, *, env)` (`env` required): LibreOffice (`soffice`, else `libreoffice`) is found with `child_env.find` on `env["PATH"]`, not `shutil.which` on the process PATH; the soffice call keeps its 120 s timeout
- 0.11.0: new dependency `child-env>=0.2,<1`
