# Arch rules

A repo-wide rule ("only the owner reads X", "no silent `except`") is a finder over parsed files plus a list of reasoned rows for the hits
allowed to stay. [any-arch](../packages/any-arch/README.md) owns the rest: the one shared parse of the repo, the stale-row check, exact
counts, the planted-violation harness, the failure text and the debt report. Never copy the scaffold of `tests/test_arch_swallowed_exceptions.py`
into a new file; write the finder and the rows.

## Add a rule in 20 lines

```python
# tests/test_arch_no_print.py
import ast
from pathlib import Path

from any_arch import Hit, Rule, Source, check, plant, rows

_ROOT = Path(__file__).resolve().parent.parent


def _prints(source: Source) -> list[Hit]:                       # one file in, (key, line) hits out; source.tree is the shared parse
    return [(source.rel, n.lineno) for n in ast.walk(source.tree) if isinstance(n, ast.Call) and ast.unparse(n.func) == "print"]


NO_PRINT = Rule(
    "no-print",                                                 # name: failure header and debt report group
    "return the value or log it, or add a reasoned row",        # fix: what a failing run tells you to do
    _prints,
    rows("debt: print is the CLI's output; return it", ("packages/a/src/a/cli.py", 2)),   # (key, n): exactly n hits; a bare key: any number >= 1
    kinds=("debt", "outcome"),                                  # reason prefixes allowed; empty: any non-blank reason
)                                                               # scope defaults to packages/*/src/**/*.py; pass scope=("tools/*.py",) to widen


def test_no_print() -> None:
    check(NO_PRINT, _ROOT)           # fails on: a new hit, more hits than a row counts, a row with no hit, a count too high, a bad reason


def test_planted_print_is_found(tmp_path: Path) -> None:
    assert plant(NO_PRINT, tmp_path, "print(1)\n") == {"packages/pkg/src/pkg/mod.py": [1]}
```

Rules:

- The key is yours: a file path, or `package:function:parameter`. `source.package` is the `packages/<name>` folder.
- Reason kinds: `debt:` a real violation owed a fix (the reason names it); `outcome:` the failure is the operation's answer; `fact:`, `split:`,
  `cost:` and `construction:` are the kinds the existing rules use. A `debt:` row shows up in the debt report.
- Never change `source.tree`: it is shared by every rule in the run.
- Debt report: `uv run python -m any_arch tests/test_arch_*.py` lists every `debt:` row, grouped by rule (`debt_text(*rules)` as text, `debt(*rules)` as a dict).
- Not a fit: a rule that needs the whole repo at once (a name shared across packages), or reads `pyproject.toml`. Keep those as plain tests.

## Which of the other 16 arch tests fit

Read for this list: `output_shape_flags`, `environment`, `atomic_writes`, `hashing`, `sqlite_access`, `ttl_cache`, `cli_surfaces` in full;
`exe_env`, `process_spawn`, `time_json`, `text_hygiene`, `http_clients`, `threads`, `duplicate_names`, `public_any` by their scan and allowlist code.
A waiver by an inline comment (`# lossy-ok:`, `# Any:`) is the finder's own logic over `source.text`; it fits.

| migrated (shelf-tyld.33) | `cli_surfaces`, `threads`, `sqlite_access` (scope `packages`, `tools`, `skills` globs; the owners and `tests` are skipped in the finder), `atomic_writes` (the owner set skipped by `source.package`), `hashing` (two rules; its bare-set rows gained reasons), `exe_env`, `process_spawn`, `time_json`, `text_hygiene` (two to four rules each; bare-set rows gained reasons). None needed a `Hit` detail: a failure shows key and lines |
|---|---|
| fits, and wants one more field | a hit's detail text: `environment` (`os.environ`, `Path.home`), `output_shape_flags` (why the flag is an output shape), `ttl_cache` (the SQL string) print what was found today; a `Hit` is `(key, line)` only. Add the field when the first of them migrates |
| fits, with a local test beside it | checks that something still exists or the scan is not vacuous: `http_clients` (the two owners still build a client), `ttl_cache` (sources found), `public_any` (its opt-in list is read from `pyproject.toml`; the rule itself has no rows) |
| does not fit | `duplicate_names` (a name shared across packages: the finder sees one file, so it needs the whole repo at once), `rules` (pyproject and import-linter TOML, body duplication across packages) |
