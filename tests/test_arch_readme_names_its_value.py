"""One complete value, compact views (constitution Article IX): a package's README names its value, its default view and its opt-ins.

The convention (see docs/arch-rules.md, "README convention"), checked on `packages/<name>/README.md`:

- value: the first paragraph under the `# title` is prose, a sentence that says what the package is for (not a code fence, a
  table, a list or a heading); every README already opens this way
- default view: a line that starts with the label `Default view:` (bold allowed, a list marker allowed) and says which view the
  most common reader gets
- opt-ins: a line that starts with the label `Opt-ins:` (same forms) and lists what the caller asks for, or says `none`

A hit is one part a README lacks; a package with no README lacks all three. Each package with hits is a row with an exact
count, so a README that gains a line shrinks its row, and a README with all three parts has no row. Reason prefixes:

- `debt:` the README does not name the part yet; the fix is one labelled line in the README
- `outcome:` the package has no view or opt-in to name; its README says so in the line, so it never needs a row
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from any_arch import Rule, check, plant, rows

from tests.arch_keys import DEBT_UNTIL

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent

_LABEL = r"^\s*(?:[-*]\s+)?(?:\*\*)?{label}(?::\*\*|\*\*:|:)[ \t]*\S"
_DEFAULT_VIEW = re.compile(_LABEL.format(label="Default view"), re.IGNORECASE | re.MULTILINE)
_OPT_INS = re.compile(_LABEL.format(label="Opt-ins?"), re.IGNORECASE | re.MULTILINE)
_NOT_PROSE = ("#", "```", "|", "- ", "* ", ">", "<")


def _opens_with_prose(readme: str) -> bool:
    """True when the first non-blank line after the `# title` is prose."""
    lines = iter(readme.splitlines())
    for line in lines:
        if line.startswith("# "):
            break
    else:
        return False
    for line in lines:
        if line.strip():
            return not line.lstrip().startswith(_NOT_PROSE)
    return False


def _missing(readme: str | None) -> list[str]:
    if readme is None:
        return ["value", "default view", "opt-ins"]
    parts = {"value": _opens_with_prose(readme), "default view": _DEFAULT_VIEW.search(readme), "opt-ins": _OPT_INS.search(readme)}
    return [part for part, found in parts.items() if not found]


def _readme_rule(root: Path) -> Rule:
    def find(source: Source) -> Iterator[Hit]:
        """One hit per missing part, once per package: the finder runs on the package's first module only."""
        package_dir = root / "packages" / source.package
        first = min((package_dir / "src").glob("*/__init__.py"), default=None)
        if first is None or first.relative_to(root).as_posix() != source.rel:
            return
        readme = package_dir / "README.md"
        for _ in _missing(readme.read_text(encoding="utf-8") if readme.is_file() else None):
            yield source.package, 1

    return Rule(
        "readme-names-its-value",
        "a README that does not name its value, a `Default view:` line and an `Opt-ins:` line (add the line, or a reasoned row)",
        find,
        _ALLOWED,
        ("debt", "outcome"),
        scope=("packages/*/src/*/__init__.py",),
        debt_until=DEBT_UNTIL,
    )


_ALLOWED = {
    **rows(
        "debt: no `Default view:` line and no `Opt-ins:` line yet (the convention is new: every README opens with its value)",
        ("a2effect", 2),
        ("any-agent", 2),
        ("any-arch", 2),
        ("any-breaker", 2),
        ("any-browser", 2),
        ("any-clock", 2),
        ("any-contract", 2),
        ("any-disk", 2),
        ("any-failure-fp", 2),
        ("any-file", 2),
        ("any-frontmatter", 2),
        ("any-gate", 2),
        ("any-gate-python", 2),
        ("any-json-doc", 2),
        ("any-knowledge", 2),
        ("any-lease", 2),
        ("any-mailbox", 2),
        ("any-markdown", 2),
        ("any-net", 2),
        ("any-path-glob", 2),
        ("any-pipeline", 2),
        ("any-plugin-cache", 2),
        ("any-proc", 2),
        ("any-recorded-fixture", 2),
        ("any-shell-policy", 2),
        ("any-ttl-cache", 2),
        ("any-versioned", 2),
        ("any-work", 2),
        ("any-yaml", 2),
        ("anyembed", 2),
        ("anyllm", 2),
        ("app-dirs", 2),
        ("argparse-mcp", 2),
        ("asgi-token-gate", 2),
        ("async-scope", 2),
        ("atomic-io", 2),
        ("bdd-tags", 2),
        ("beads-client", 2),
        ("blueprint", 2),
        ("browser-cookies", 2),
        ("child-env", 2),
        ("content-digest", 2),
        ("content-extract", 2),
        ("convert-md", 2),
        ("dir-trust", 2),
        ("dom-schema", 2),
        ("duckdb-sidecar", 2),
        ("due-schedule", 2),
        ("event-bus", 2),
        ("fts-query", 2),
        ("git-porcelain", 2),
        ("html-fragment", 2),
        ("http-cache", 2),
        ("http-fetch", 2),
        ("json-in-html", 2),
        ("json-match", 2),
        ("jsonl-log", 2),
        ("launchd-agent", 2),
        ("lean-wire", 2),
        ("llm-cache", 2),
        ("llm-wobble", 2),
        ("managed-region", 2),
        ("mcp-arg-errors", 2),
        ("mcp-bridge", 2),
        ("mcp-call", 2),
        ("mcp-clients", 2),
        ("mcp-feedback", 2),
        ("mcp-result-wire", 2),
        ("mcp-steps", 2),
        ("page-tsv", 2),
        ("partial-time", 2),
        ("path-pattern", 2),
        ("plugin-surface", 2),
        ("process-lock", 2),
        ("py-symbols", 2),
        ("record-mine", 2),
        ("settings-base", 2),
        ("shelf-vendor", 2),
        ("sqlite-resource", 2),
        ("sqlite-sidecar", 2),
        ("sqlite-store", 2),
        ("static-page-check", 2),
        ("stream-proc", 2),
        ("task-spec", 2),
        ("test-reach", 2),
        ("timefmt", 2),
        ("verb-cli", 2),
        ("yaml-merge", 2),
    ),
    **rows(
        "debt: the README opens with a code block, not a sentence of value, and has no `Default view:` or `Opt-ins:` line yet",
        ("any-speech", 3),
    ),
}

README_NAMES_ITS_VALUE = _readme_rule(_ROOT)


def test_every_readme_names_its_value_default_view_and_opt_ins_or_has_a_reasoned_row() -> None:
    check(README_NAMES_ITS_VALUE, _ROOT)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


_INIT_PATH = "packages/p/src/p/__init__.py"
_FULL = "# p\n\n**Stop doing x.** One call does it.\n\n**Default view:** the summary.\n\n- Opt-ins: `full=...`\n"


@pytest.mark.parametrize(
    ("readme", "found"),
    [
        (_FULL, {}),
        ("# p\n\nStop doing x.\n\n**Default view:** the summary.\n\nOpt-ins: none\n", {}),
        ("# p\n\nStop doing x.\n\n**Default view**: the summary.\n\n**Opt-ins:** none\n", {}),
        ("# p\n\nStop doing x.\n\nOpt-ins: none\n", {"p": [1]}),
        ("# p\n\nStop doing x.\n\nDefault view: the summary.\n", {"p": [1]}),
        ("# p\n\nStop doing x.\n", {"p": [1, 1]}),
        ("# p\n\n```python\nrun()\n```\n\nDefault view: x\n\nOpt-ins: none\n", {"p": [1]}),
        ("# p\n\n| a | b |\n|---|---|\n", {"p": [1, 1, 1]}),
        ("Default view:\n\nOpt-ins:\n", {"p": [1, 1, 1]}),
    ],
)
def test_the_scanner_counts_the_missing_parts(tmp_path: Path, readme: str, found: dict[str, list[int]]) -> None:
    _write(tmp_path, "packages/p/README.md", readme)
    assert plant(_readme_rule(tmp_path), tmp_path, "", path=_INIT_PATH) == found


def test_a_package_without_a_readme_lacks_all_three_and_is_counted_once_per_package(tmp_path: Path) -> None:
    _write(tmp_path, "packages/p/src/p/other.py", "")
    _write(tmp_path, "packages/p/src/q/__init__.py", "")
    assert plant(_readme_rule(tmp_path), tmp_path, "", path=_INIT_PATH) == {"p": [1, 1, 1]}
