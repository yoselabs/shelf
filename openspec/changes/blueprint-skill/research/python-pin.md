# Pinning Python and uv in a uv project: rule set for blueprint

Date: 2026-10-11. Local uv: 0.10.12. Scratch projects: `scratchpad/t1..t4`.
Labels: [T] tested locally, [R] read (URL, fetched 2026-10-11), [U] untested / reasoned.

## 1. Verdict: rules blueprint should prescribe

Same rules for app and library unless marked.

| # | Rule | Why |
|---|------|-----|
| P1 | `pyproject.toml` has `project.requires-python = ">=X.Y"`: lower bound only, minor granularity, no upper cap, no `<`, no `~=`, no `==`. (library AND app) | It is the fact "what runs": consumers and resolver read it; a cap causes hard resolver failures (Schreiner, SciPy PP004). |
| P2 | Repo root has `.python-version` containing exactly one `X.Y` (minor, no patch, no `cpython-` prefix, no range, no comment). | It is the fact "what we develop and gate on": picks the interpreter for `uv run`/`uv sync`/`uv python install`. Minor-level keeps CI and laptops on the same series without chasing patch releases; the exact patch is not in the lock either way, so a patch pin buys false precision. |
| P3 | The pin satisfies `requires-python`. If workspace: it satisfies the intersection of root and ALL members. | A violating pin makes `uv sync`/`uv run` hard-fail [T]. Detected by the tool, but blueprint should say so before CI does. |
| P4 | Library (published, or consumed by git+tag): the pin SHOULD be the lowest-supported or the main-supported minor, and CI MUST also run the tests on the `requires-python` lower bound (`uv run --python X.Y ...`). App/service: pin = the deployed runtime minor; `requires-python` MAY equal the pin (`>=X.Y`). | The lower bound is a claim; only a run on it proves it. For an app, the range is the pin, nothing consumes the range. |
| P5 | `[tool.uv] required-version` in root `pyproject.toml` (or `uv.toml`) is set to a range `">=A.B.C"` (floor = the uv that wrote `uv.lock` format used), not `==`. | Fails loudly on too-old uv [T]; setup-uv reads it automatically [R]. Exact `==` is also valid [T] but forces a bump on every uv release (noise). |
| P6 | CI installs uv via `astral-sh/setup-uv` pinned by commit SHA, with `version` unset (so it reads `required-version`) OR `version-file: pyproject.toml`; CI does NOT use `actions/setup-python`; CI does not hard-code a python version when one pin exists (`uv sync`/`uv python install` read `.python-version`). A matrix sets `python-version:` (sets `UV_PYTHON`) only on matrix jobs. | One source for each fact; no third copy in the workflow. (Current shelf `check.yml` hard-codes `"3.12"` via setup-python: duplicate of `.python-version`; setup-uv `v3` also is old.) |
| P7 | `uv.lock` committed; CI runs `uv sync --locked` (or `uv lock --check`). | Lock's `requires-python` header must track pyproject [T]; `--locked` fails on drift. |
| P8 | Do not set `UV_PYTHON`, `python-preference`, or `python-downloads` in committed config unless a documented reason exists. | They override the pin silently [T: UV_PYTHON beats `.python-version`]. |
| P9 | No `.python-versions` file, no per-member `.python-version` in a workspace. | `.python-versions` is read only by `uv python install` (multi-install) and is not used by `uv run` as a pin [T]; per-member pins are ignored [T] so they mislead. |

Is `.python-version` + `requires-python` duplication? No: two facts. Range = what is supported (published contract); pin = what the repo runs by default. They coincide only for apps. The check is a relation (pin inside range), not equality.

## 2. What each rule's deterministic check reads

- P1: parse `pyproject.toml` (tomllib) `project.requires-python`; `packaging.specifiers.SpecifierSet`; require exactly one specifier, operator `>=`, version has 2 segments (or 3 allowed if justified; blueprint choice), no `<`/`<=`/`!=`/`==`/`~=`. Workspace: apply to root and each member `packages/*/pyproject.toml` (member list from `[tool.uv.workspace].members`).
- P2: read `<root>/.python-version`; regex `^\d+\.\d+$` after strip; single line; file exists at root.
- P3: `Version(pin + ".0")` (or probe highest patch) `in SpecifierSet`: use `SpecifierSet.contains(pin+".999", prereleases=False)` style check, i.e. is the minor series admitted by the range; for workspace, intersect (`&`) all member sets plus root. Alternative oracle: `uv sync --dry-run` / `uv lock --check` exit code and the "incompatible with the project's Python requirement" message [T].
- P4 (library): from `requires-python` take lower bound L; check CI workflow YAML contains L as a matrix entry / `--python L` / `python-version: L`. App: skip.
- P5: `tool.uv.required-version` in pyproject.toml or `uv.toml` present, parses as SpecifierSet, operator `>=` (or `==`, allowed); and `uv --version` satisfies it (blueprint's own run proves nothing about CI, so also compare against the `uv.lock` `revision` it needs: see section 4).
- P6: parse `.github/workflows/*.yml`: any `uses: actions/setup-python` -> finding; `uses: astral-sh/setup-uv@<40-hex>` required; a literal `python-version:` not derived from `matrix.` -> finding when `.python-version` exists.
- P7: `uv.lock` exists, `uv lock --check` exit 0 (or `uv sync --locked`); first-line `requires-python` in `uv.lock` equals normalized `project.requires-python` (for workspace: the intersection, see W2 [T]).
- P8: grep committed `.env`/`uv.toml`/pyproject `[tool.uv]` for `python-preference`, `python-downloads`, and workflows/Makefile for `UV_PYTHON`.
- P9: glob `.python-versions` anywhere; glob `**/.python-version` not at root.

## 3. Evidence table

| Claim | Label | Evidence |
|---|---|---|
| Without any pin, `uv run` picks a managed interpreter satisfying `requires-python` (first compatible found; here 3.13.12, not Homebrew 3.14 and not Xcode 3.9) | T | t1/a T1 |
| `.python-version` chooses the interpreter for `uv run`/`uv sync` (3.12 -> 3.12.13) | T | t1 T2 |
| uv.lock's `requires-python` comes from pyproject, not from the pin (lock said `>=3.11` with pin 3.12) | T | t1 T2 |
| Pin outside `requires-python` hard-fails `uv sync`/`uv run` ("resolved to Python 3.10.20, which is incompatible with the project's Python requirement"); also auto-downloaded 3.10 first | T | t1 T3, T4 |
| `uv python pin X` refuses a version incompatible with `requires-python` | T | t1 T9 |
| `UV_PYTHON` beats `.python-version`; `--python` beats both; next plain `uv run` recreates the venv back to pin (venv thrash) | T | t1 T5-T7 |
| Pin `3.12.13` works; `uv python pin 3.12.13` rewrites file from `3.12`; uninstalled exact patch (3.12.1) fails offline since managed download is needed | T | t1 T8, T10 |
| `.python-version` content `cpython-3.12` is accepted; content `>=3.12` did not error (outcome inconclusive: reused venv) | T / U | t2 |
| `.python-versions` alone: `uv run` used 3.12 (first line; actually inconclusive vs existing state), `uv python install` installed ALL listed | T (install) / U (run) | t2 |
| `required-version`: PEP 440 specifier; `>=99` errors "Required uv version `>=99` does not match the running version"; `==0.10.12` and bare `0.10.12` accepted; works in `pyproject.toml [tool.uv]` and `uv.toml` | T | t2 R1-R6; R: https://docs.astral.sh/uv/reference/settings/ |
| `uv lock` writes `revision = 3` on uv 0.10.12; uv 0.6.0 rewriting the lock downgrades it to `revision = 1`; uv 0.10.12 does not re-bump on a no-op `uv lock` | T | t4 |
| Version skew = lockfile churn (revision flaps, upload-time metadata dropped), not a hard error, for older uv on a newer-revision lock; hard rejection only for newer schema `version` | T (churn) / R (policy) | t4; https://github.com/astral-sh/uv/issues/15220 (via search summary), uv versioning docs |
| Workspace: `requires-python` is the intersection of all members; lock header shows the intersected value (`>=3.13` when members `>=3.10`,`>=3.11`,`>=3.13`); a root pin outside intersection errors naming the offending member | T | t3 W1, W2; R: https://docs.astral.sh/uv/concepts/projects/workspaces/ |
| Workspace: root `.python-version` is used from member dirs; a member's own `.python-version` (3.11) had no effect | T | t3 W3, W4 |
| `uv python install` (no args) installs the `.python-version` version; installs all of `.python-versions` | T / R | t2; https://docs.astral.sh/uv/concepts/python-versions/ |
| `.python-version` lookup walks cwd and parents, stops at project/workspace boundary; recommends a version number for interop | R | https://docs.astral.sh/uv/concepts/python-versions/ |
| `python-preference` default `managed`; `python-downloads` default `automatic` | R | https://docs.astral.sh/uv/reference/settings/ |
| setup-uv: `python-version` sets `UV_PYTHON` and overrides pyproject/.python-version; `version` default = `required-version` from `uv.toml`/`pyproject.toml` at repo root else latest; `version-file` accepts uv.toml, pyproject.toml, .tool-versions, requirements.txt, uv.lock | R | https://github.com/astral-sh/setup-uv/blob/main/README.md |
| uv docs: "best practice to pin to a specific uv version" in setup-uv `version:`; `uv python install` "respects the Python version pinned in the project"; matrix via `python-version: ${{ matrix.python-version }}` or `UV_PYTHON` | R | https://docs.astral.sh/uv/guides/integration/github/ |
| Never cap Python version, libraries or apps; apps ship a lock file | R | https://iscinumpy.dev/post/bound-version-constraints/ |
| `requires-python`: specify the minimum, no upper cap (PP004) | R | https://learn.scientific-python.org/development/guides/packaging-simple/ (page does not cover testing the minimum) |
| Hynek: caps on deps postpone breakage; he does not discuss `requires-python` | R | https://hynek.me/articles/semver-will-not-save-you/ |
| A consumer installing a library by git ref uses the consumer's interpreter; the library's `.python-version` is not consulted, only its `requires-python` metadata | U (reasoned from the lookup rules: pin is a project-local dev file) |
| CI lower-bound testing via `uv run --python X.Y` works against the same lock (ran 3.11 on a `>=3.11` project) | T | t1 T6. Better to use separate env per version (`UV_PROJECT_ENVIRONMENT`) to avoid venv thrash: U |
| Astral does not publish a recommendation for patch-level pins; docs use `3.12`-style examples | R (absence) |

## 4. Resolution order (answers Q1)

```
interpreter for uv run / uv sync:
  --python  >  UV_PYTHON (setup-uv python-version sets this)  >  .python-version (nearest, root of project/workspace)
  >  requires-python (first compatible; managed preferred over system by default)
  then: chosen interpreter MUST satisfy requires-python (workspace: intersection)  else hard error [T]
resolution (what uv.lock contains):  requires-python only (pin is ignored) [T]
what consumers can install:           requires-python metadata of the package only
which uv runs:                        required-version only enforces (error), never selects/installs; setup-uv reads it to install
```

## 5. Answers to Q4, Q5, Q6, Q7 in short

- Workspace: one root `.python-version`; members carry only their own honest `requires-python`; uv intersects [T]. Member lower bounds can differ, but the pin must fit the intersection [T]. A member that must run on an older Python than the intersection cannot, in one workspace (docs suggest `uv pip` in a separate venv) [R].
- CI: no setup-python needed; `uv sync`/`uv run` read the pin and download the interpreter [T locally]. Whether setup-uv itself reads `.python-version` by default: docs ambiguous [R], irrelevant since uv does.
- uv pinning: `required-version` is a floor/gate, not an installer. Version skew effects: lock `revision` flaps and diff noise [T]; hard failure only for unknown future schema [R]. Pin CI uv via `required-version` (setup-uv reads it) so laptop, hooks and CI agree.
- Patch pins: `X.Y` wins. Reasons: `.python-version` is also read by pyenv, asdf, actions/setup-python (interop with minor form, [R] uv docs); patch pin forces a download of that exact patch everywhere [T: T10]; security patches arrive without a commit; reproducibility lives in `uv.lock`, not the interpreter patch. Exception (U): an app container image should pin the patch in the Dockerfile, not in `.python-version`.

## 6. Refused alternatives

- Upper cap on `requires-python` (`<3.14`): Schreiner "never"; SciPy PP004; resolver treats it as hard fail; shelf consumers on newer Python get blocked.
- `.python-version` = exact patch: false precision, forced downloads [T], churn; lock covers reproducibility.
- Making `.python-version` equal to `requires-python` lower bound for libraries as a rule: two facts conflated; CI matrix is the correct way to test the bound. Allowed as a choice, not required.
- Per-member `.python-version` in a workspace: ignored by uv [T].
- `.python-versions`: only `uv python install` uses it; as a pin it is not honoured the way `.python-version` is (partly U).
- `required-version = "==X"` as default: valid [T], but each uv bump becomes a mandatory commit across repos; floor gives the same gate against too-old uv. Acceptable for deployment repos that want byte-identical locks.
- Hard-coded `python-version` in workflow plus setup-python: third copy of the fact.
- Checking `UV_PYTHON` / env in blueprint audit at runtime: environment-dependent, non-deterministic; check committed files only.
- tox/nox for range testing: unnecessary here; `uv run --python X.Y` over the shared lock does it. Nox with uv backend remains valid for multi-version matrices with many sessions (U).

## 7. Notes for shelf specifically (read)

- All 52 members and root declare `requires-python = ">=3.11"`; root `.python-version` = `3.12`; no `required-version` set; `.github/workflows/check.yml` uses `actions/setup-python` with literal `"3.12"` and `setup-uv@...# v3`. Under this rule set: P1 pass, P2 pass, P3 pass, P4 FAIL (no 3.11 job: lower bound untested), P5 FAIL, P6 FAIL.
