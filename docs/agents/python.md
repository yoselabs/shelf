# Python conventions

Stack: python-uv. The gate is `make check`; this file is what to know before writing code.

## Tools per role

| role | tool | run by |
|---|---|---|
| toolchain | uv, committed `uv.lock`, declared Python range or `.python-version` | `uv sync` |
| formatter | `ruff format` | `make format` (check in the gate) |
| linter | `ruff check`, the shelf's rule set from `[tool.ruff.lint]` | `make lint` |
| types | pyrefly, `preset = "strict"` | `make typecheck` |
| spelling | codespell | `make spell` |
| dependencies | deptry (unused, missing, transitive) | `make deps` |
| tests | pytest, strict markers, xdist | `make test` (`make test-affected` while iterating) |
| coverage | pytest-cov with a floor just below current | in `make test` |
| architecture | none chosen yet (import-linter vs tach is open) | see [architecture.md](architecture.md) |
| hooks | prek: ruff check and ruff format on staged `.py` | [gate.md](gate.md) |

Why: one tool per role, strictest preset.

## Run

```bash
uv sync                  # environment from the lockfile
make check               # the gate: whole repo, same as CI
uv run pytest path::name # one test while iterating; the gate still decides done
```

Always `uv run <tool>`; never a global interpreter or `pip install`. Add a dependency with
`uv add` (`--dev` for tooling) and commit `uv.lock`.

## Code rules

| rule | why |
|---|---|
| Full type annotations; no `Any` without a one-line reason; no `# type: ignore` without the error code and a reason | Strict types catch what tests do not |
| Suppress a lint rule per path in `pyproject.toml` with a reason, not inline `# noqa` | Inline hides where the rule is weakened |
| `pathlib` over `os.path`; `from __future__ import annotations`; `X \| None` over `Optional` | One style, fewer imports |
| Dependencies injected at the edge (parameters, a factory); no module-level I/O or global state | Hermetic tests ([testing.md](testing.md)) |
| Comments say why (units, invariant, workaround with a link), never what; a docstring only states a public contract | The code already says what |
| No `print` in library code; return values or log | Output belongs to the surface |
| Dataclass or small class owns its derived state; do not pass loose dicts around | A dict has no contract |

## Layout and naming

| thing | convention |
|---|---|
| Source | `src/<package>/`, one concept per module |
| Tests | `tests/<mirrored source path>/test_<module>.py`; scenarios in `packages/<name>/tests/features/` |
| Names | modules and functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE`; a domain term spelled as in CONTEXT.md |
| Test names | `test_<behaviour>`; never after a bead or fix |

## Traps

- Mutable default arguments: use `None`, build inside.
- A test reading `HOME`, env or git config: scrub in `conftest.py`.
- `uv` choosing a different Python in a fresh worktree: commit `.python-version`.
- pyrefly skips hidden worktree folders; pass paths explicitly if a worktree lives under one.
- A dependency added without `uv lock` fails the gate.
