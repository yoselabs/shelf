# The linter reference — how this repo stays clean, and how yours inherits it

The shelf's quality bar is a **config-preset** (resolution 0004): the toolchain below is configured in
`pyproject.toml` + driven by `make`, and a new project inherits it by **copying** the blocks and owning
the copy. No CLI, no runtime dependency, no cage. This file is the reference to converge toward.

The one rule that never bends: **`make check` is green over the WHOLE repo — no carve-outs** (AGENTS.md §1).

## The toolchain — one tool, one job

| Tool | Job | Where configured | In the gate? |
|------|-----|------------------|:---:|
| **ruff check** | lint — a broad, curated rule set (correctness, security, docs, dead code, exceptions, typing) | `[tool.ruff.lint]` | ✅ |
| **ruff format** | formatting — the single formatter; no bikeshedding | `[tool.ruff]` | ✅ |
| **ty** | type checking (Astral); `--error-on-warning` so a warning fails the build | `make typecheck` | ✅ |
| **codespell** | typos in code, docstrings, and docs | `[tool.codespell]` | ✅ |
| **deptry** | dependency hygiene per package — unused / missing / transitive | `make deps` (per-pkg) | ✅ |
| **pytest + coverage** | tests + a coverage floor that guards against regression | `[tool.pytest…]`, `[tool.coverage…]` | ✅ |

Run the whole thing with `make check`. Individual targets: `make lint typecheck spell deps test`
(and `make format`, `make cov` for a human coverage view).

## Why the ruff config looks the way it does

- **Curated-broad, not `ALL`.** An explicit, grouped `select` reads as a *reference* — it teaches the
  convention — and does not silently break when a ruff upgrade adds a rule. Every family is grouped and
  commented in `pyproject.toml`; every `ignore` states its reason.
- **The strict families that matter for "no chaos":** `S` (security/bandit), `D` (docstrings on the
  public surface, google convention), `ERA` (no commented-out code — *leave it smaller*, constitution
  III/VIII), `EM`/`TRY`/`BLE` (clean exceptions, no blind catches), `ANN` (everything typed),
  `C90` (complexity ceiling), `PTH` (pathlib), `FBT` (no boolean traps), `TC` (typing-only imports).
- **Tests get a lighter bar** (per-file-ignores): no docstrings, asserts allowed, magic numbers fine.
- **Every suppression is honest.** `# noqa` requires a reason; the only one in the tree today is the
  deliberate multi-engine fallback in `convert-md` (`BLE001`).

## The coverage floor

Set *just below* current total coverage (65% vs 68% today). It is a **regression guard, not a vanity
number** — the substrate adapters (docling / torch / subprocess) are legitimately hard to unit-test.
Raise the floor as real coverage climbs; never lower it to make a red build green.

## How a consumer inherits this (the onboarding copy)

When onboarding a project (`consuming-the-shelf.md`), copy from this repo:

1. The `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.codespell]`, `[tool.coverage.*]` blocks from
   `pyproject.toml`, and each package's `[tool.deptry]` if it needs ignores.
2. The `Makefile` targets (`check lint format typecheck spell deps test`).
3. The `dev` dependency-group (pytest, pytest-cov, ruff, ty, codespell, deptry).

Then **own it**: override any rule your project genuinely needs to, on purpose. Divergence is a local
choice, visible in your own `pyproject`. The shelf is the baseline you converge back toward, not a lock.

## Architectural fitness rules (native, not OPA — resolution 0005)

Beyond ruff, the shelf enforces *architectural* rules as pure-stdlib pytest (like
`tests/test_boundary.py`), reimplementing a2kit's Rego policies without dragging OPA in:

- **`tests/test_arch_rules.py`** (blocking, via `tools/arch_rules.py`): dependency **upper-bounds**;
  **body-duplication** and **private-name-collision** *within* a package. Suppress with a reasoned entry
  in `tests/arch_allowlist.toml`.
- **`make advisory`** (non-blocking): *cross-package* duplication — a T0-primitive candidate, not a
  violation (constitution VI values some duplication).

Still un-ported (add when a real violation appears): the import layer-DAG and the `dict[str,Any]`-ban.
