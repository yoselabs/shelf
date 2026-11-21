# any-arch

**Stop re-writing the scaffold of an architecture test.** A repo-wide rule ("only the owner reads the environment", "no silent `except`") is
a finder over parsed files plus a reasoned list of hits allowed to stay. The walk, the parse, the stale-row check, the exact counts, the
planted-violation test, the failure text and the debt list are the same every time. `any-arch` is that, once; you write the finder and the rows.

```python
from any_arch import Rule, check, plant, rows

def prints(source):                                   # Source -> (key, line) hits; source.tree is the shared parse
    for node in ast.walk(source.tree):
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "print":
            yield source.rel, node.lineno

NO_PRINT = Rule("no-print", "log, or add a reasoned row", prints, rows("debt: move to the log", ("packages/a/src/a/cli.py", 2)),
                kinds=("debt", "outcome"))

def test_no_print():   check(NO_PRINT, ROOT)                                   # new hit, over count, stale row, bad reason
def test_planted(tmp_path): assert plant(NO_PRINT, tmp_path, "print(1)\n") == {"packages/pkg/src/pkg/mod.py": [1]}
```

| name | does |
|---|---|
| `Rule(name, fix, find, rows, kinds=(), scope=("packages/*/src/**/*.py",))` | the finder, its allowlist, the fix text, the allowed reason prefixes, the globs it sees |
| `Row(reason, count=None)`, `rows(reason, *keys)` | one allowed key; `count` is exact (`None`: any number of at least one); `rows` shares one reason, a `(key, n)` pair sets a count |
| `check(rule, root)` | raises one `AssertionError`: the fix text, then each `new` / `over` / `stale` / `reason` line |
| `plant(rule, tmp_path, source, path=...)` | writes `source` under `tmp_path`, returns key -> lines the rule finds |
| `debt(*rules)`, `debt_text(*rules)` | every `debt:` row, grouped by rule, as data and as text |
| `Source`, `Hit` | what a finder receives (`rel`, `package`, `text`, `tree`: parsed once per file per run, never mutate it) and yields (`(key, line)`) |

`python -m any_arch tests/test_arch_*.py` prints the debt of every `Rule` a test module defines at its top level.

Not here: rules that need no parse (a pyproject or TOML check), cross-file facts (a name shared across packages, a body duplicated across
files) and per-hit allowlists that are not keyed by a string. Stdlib only.
