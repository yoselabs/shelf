from __future__ import annotations

import hashlib
import os
from typing import TYPE_CHECKING

from static_page_check import budget_problems, colour_problems, import_problems, page_problems, pin_problems

if TYPE_CHECKING:
    from pathlib import Path


def tree(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return root


def test_imports_that_resolve_and_export_pass(tmp_path: Path) -> None:
    root = tree(
        tmp_path,
        {
            "app.js": "import { a, b as c } from './lib.js';\nimport './side.js';\nimport { h } from './vendor/rt.js';\n",
            "lib.js": "export function a() {}\nexport const b = 1;\n",
            "side.js": "",
            "vendor/rt.js": "var h=1;export{h as default}",
        },
    )
    assert import_problems(root, vendored=["vendor/rt.js"]) == []


def test_bad_imports_are_each_named(tmp_path: Path) -> None:
    root = tree(
        tmp_path,
        {
            "app.js": "import { a, zz } from './lib.js';\nimport x from './gone.js';\n"
            "import y from 'https://cdn.example/y.js';\nimport z from 'preact';\nimport { nope } from './vendor/rt.js';\n",
            "lib.js": "export function a() {}\n",
            "vendor/rt.js": "var h=1;",
        },
    )
    got = import_problems(root, vendored=["vendor/rt.js"])
    assert len(got) == 5
    assert any("does not export ['zz']" in p for p in got)
    assert any("gone.js" in p and "no such file" in p for p in got)
    assert sum("no bare or absolute" in p for p in got) == 2
    assert any("does not export ['nope']" in p for p in got)


def test_relative_asset_urls_that_exist_pass(tmp_path: Path) -> None:
    root = tree(
        tmp_path,
        {"index.html": '<link href="css/a.css?v=1"><script src="./js/a.js"></script><a href="#top">', "css/a.css": "", "js/a.js": ""},
    )
    assert page_problems(root) == []


def test_absolute_cdn_and_missing_references_fail(tmp_path: Path) -> None:
    root = tree(
        tmp_path,
        {"index.html": '<link href="/css/a.css"><script src="https://cdn.example/x.js"></script><img src="gone.png">', "css/a.css": ""},
    )
    got = page_problems(root)
    assert len(got) == 3
    assert sum("not a relative url" in p for p in got) == 2
    assert any("gone.png" in p and "no such file" in p for p in got)


def test_pinned_file_passes_and_changed_or_missing_fails(tmp_path: Path) -> None:
    root = tree(tmp_path, {"vendor/rt.js": "runtime"})
    sha = hashlib.sha256(b"runtime").hexdigest()
    assert pin_problems(root, {"vendor/rt.js": sha}) == []
    got = pin_problems(root, {"vendor/rt.js": "0" * 64, "vendor/gone.js": sha})
    assert len(got) == 2
    assert any("is not the pinned" in p for p in got)
    assert any("missing" in p for p in got)


def test_colours_only_in_tokens_pass(tmp_path: Path) -> None:
    root = tree(
        tmp_path,
        {
            "tokens.css": ":root { --bg: #fff; --fg: rgb(0 0 0); }",
            "a.css": "/* was #123456 */\n#ph, #abc > i { color: var(--fg); }\nb { fill: url(#abc); }",
            "a.js": "const c = 'var(--bg)';",
            "index.html": '<a href="#add">x</a>',
            "vendor/rt.js": "var c='#ff0000'",
        },
    )
    assert colour_problems(root, "tokens.css", vendored=["vendor/rt.js"]) == []


def test_colour_literals_outside_tokens_fail(tmp_path: Path) -> None:
    root = tree(
        tmp_path,
        {
            "tokens.css": ":root { --bg: #fff; }",
            "a.css": "#ph { color: #abc; }\nb { border: 1px solid #fff }\nc { x: hsla(0,0%,0%,.5) }",
            "a.js": "el.style.color = 'rgb(1,2,3)';",
        },
    )
    got = colour_problems(root, "tokens.css")
    assert len(got) == 4
    assert any(p.startswith("a.css:1:") for p in got)
    assert any(p.startswith("a.css:2:") for p in got)


def test_within_budget_passes_and_over_budget_fails(tmp_path: Path) -> None:
    root = tree(tmp_path, {"a.js": "x" * 1000, "b.css": "y{}", "ignored.html": "<p>" * 5000})
    assert budget_problems(root, 10_000) == []
    got = budget_problems(root, 10)
    assert len(got) == 1
    assert "budget 10" in got[0]


def test_incompressible_data_counts_toward_the_budget(tmp_path: Path) -> None:
    root = tree(tmp_path, {})
    (root / "noise.js").write_bytes(os.urandom(5000))
    assert budget_problems(root, 4000) != []


def test_a_wrong_static_dir_is_a_problem_not_a_pass(tmp_path: Path) -> None:
    gone = tmp_path / "gone"
    assert import_problems(gone) != []
    assert page_problems(gone) != []
    assert pin_problems(gone, {}) != []
    assert colour_problems(gone, "t.css") != []
    assert budget_problems(gone, 1) != []
