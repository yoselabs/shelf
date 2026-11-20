# Affected-only builds + task caching for a uv/Python monorepo (research, 2026-10-10)

Provenance key: TESTED = I ran it here (uv 0.10.12, poethepoet 0.48.0, macOS). READ = fetched a page this session, one pass, not cross-checked. KNOWLEDGE = from memory, unverified. Web fetches returned shallow summaries; version/date gaps are marked.

## Q2 first (it gates everything): are uv workspaces incompatible with git-ref installs?

**Refuted for uv consumers. Confirmed for pip consumers.** (TESTED)

Setup: temp project `/private/tmp/claude-501/t1`, one dependency, no source for siblings:

```toml
dependencies = ["mcp-result-wire"]
[tool.uv.sources]
mcp-result-wire = { git = "https://github.com/yoselabs/shelf", subdirectory = "packages/mcp-result-wire", tag = "mcp-result-wire-v0.2.0" }
```

| Command | Result |
|---|---|
| `uv lock` | `Resolved 77 packages`. uv.lock holds `page-tsv` and `lean-wire` as `git ...?subdirectory=packages/page-tsv&tag=mcp-result-wire-v0.2.0#5e5afa9...`: SAME commit as the requested tag. |
| `uv sync` + `import mcp_result_wire, page_tsv, lean_wire` | OK |
| `uv pip install "page-tsv @ git+https://github.com/yoselabs/shelf@page-tsv-v0.2.1#subdirectory=packages/page-tsv"` | OK: `lean-wire==0.2.0 (from git+...@bf332d8...#subdirectory=packages/lean-wire)` |
| `python -m pip install "page-tsv @ git+...@page-tsv-v0.2.1#subdirectory=packages/page-tsv"` | **FAILS**: `Could not find a version that satisfies the requirement lean-wire>=0.2 ... (from versions: none)` |

- Mechanism (inferred from behaviour, not from a doc): uv reads `[tool.uv.sources]` from the workspace ROOT of the cloned git checkout, so root `lean-wire = { workspace = true }` becomes "same git repo, same rev, subdirectory packages/lean-wire". Root sources, not the member's own pyproject, carry it (page-tsv's pyproject has no sources table). A sibling missing from root `[tool.uv.sources]` would fall to the index; none of the shelf's siblings are on PyPI (`pypi.org/pypi/lean-wire/json` and `page-tsv` return 404).
- The sibling resolves at the SAME commit as the tag asked for, not at the version its tag implies. In the test, `page-tsv-v0.2.1` pulled `lean-wire` 0.2.0 (whatever sat at that commit), while `mcp-result-wire-v0.2.0` pulled lean-wire 0.3.0. This is why a2kay's pyproject says page-tsv and lean-wire must name the SAME tag (a2kay `[tool.uv.sources]`, lines ~186-193): a consumer's own explicit source overrides it.
- pip, poetry, pdm without uv-source support: cannot resolve unpublished siblings. This fails with or without a uv workspace; a workspace neither causes nor fixes it. Fix, if ever needed: a PEP 508 direct URL in `[project].dependencies` (`lean-wire @ git+...`), which pins an exact tag in the member and loses the "root sources" convenience. Not needed while all consumers are uv.
- Docs: `https://docs.astral.sh/uv/concepts/projects/workspaces/` (READ): root `tool.uv.sources` applies to all members; says nothing about git-subdirectory installs. Search surfaced a related uv fix, "Fix transitive Git path dependencies in lockfiles (#19269)", closing uv issue #19152 (READ via search snippet only, not opened; I did not find an issue titled "workspace member from git subdirectory fails"). So my "earlier attempt found incompatibility" hypothesis: the likely real cause is pip/non-uv installs, or an older uv. Not reproduced on uv 0.10.12.
- Not tested: a consumer on an older uv; a sibling absent from root sources; a consumer using `uv add git+...` CLI form (should write the same table).

## Q1 Tools

| Tool | uv lockfile | per-pkg tasks | affected from git | caching | adoption weight | maintenance | status |
|---|---|---|---|---|---|---|---|
| Turborepo (`experimentalPythonWorkspaces`) | reads root uv.lock; never writes it | members become packages; built-in `build/format/check/lint/test` mapped to uv/ruff/pytest; custom `experimentalTaskCommand`; override per member `py-api#lint` | `--affected`, `--filter`, follows Python dep edges between members | local; hash = member sources + internal deps + root uv config + uv.lock external closure; remote cache available | `turbo.json` at root, `[tool.turbo].name` in root pyproject, node/npm toolchain, Rust binary. Per-package config optional | Vercel, active | **Docs say experimental, "side projects and proofs of concept", can change any time; built-in uv tasks `cache: false` until fingerprints cover uv/python/ty versions** (per search snippet; the fetched page said `check` cacheable when uv+Python identified: sources disagree, one pass). https://turborepo.dev/docs/guides/tools/python (READ) |
| Pants | experimental uv lockfile support in 2.32.0 (2026-05-28); **"uv does not yet work with remote caching"** | per-target via BUILD files (`tailor` generates); pants.toml | `--changed-since=<merge-base>` + `--changed-dependents=transitive`; lockfile change marks all users changed | local + remote (not with uv) | Heaviest Python-native: pants.toml, BUILD files per dir, own resolves/lockfiles, own venv/pex model. Rust engine, no JVM | Active, releases monthly-ish | https://www.pantsbuild.org/blog/2026/05/28/pants-2-32 (READ), https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection (READ). Community report: uv sync-whole-lockfile bloats CI disk (chat.pantsbuild.org thread, user report) |
| moon (moonrepo) | Python toolchain `pip` or `uv`, introduced in v2, flagged unstable at the rc (https://moonrepo.dev/blog/moon-v2-rc, READ via search). Current key names unconfirmed | `moon.yml` per project (optional), `.moon/toolchains.yml` | `moon ci` / `--affected` exist (KNOWLEDGE; the cache page I fetched did not cover it) | local `.moon/cache` tar.gz hydration; remote supported (page gave no config) | `.moon/` dir + moon.yml per package, Rust binary, proto toolchain manager | v2.6.1 released 2026-10-07 (READ, GitHub releases) | Python/uv support is the weak part: unstable at v2 rc, not re-checked at 2.6 |
| Nx + `@nxlv/python` | README for v23.0.0 says supports "Uv or Poetry" (READ, https://cdn.jsdelivr.net/npm/@nxlv/python@23.0.0/README.md); date of uv support unknown | `project.json` per package (generated) | `nx affected` | local + Nx Cloud/remote | node + nx.json + project.json per package + a community plugin; plugin repo `lucasvieirasilva/nx-plugins` listed as "Preview Version" with Poetry 1.2+ prereq on the repo page (READ: that page is stale or about the older plugin; conflict unresolved) | community plugin, not Nx core | Untested |
| Bazel + rules_python | rules_python has uv-based lock support (KNOWLEDGE) | BUILD per package (gazelle generates) | via bazel-diff / target-determinator (KNOWLEDGE) | best-in-class local/remote | Heaviest: MODULE.bazel, BUILD files, hermetic rewrites, packages no longer installable the uv way | Google, active | Not tested, KNOWLEDGE only |
| Buck2 / Please | no mainstream Python+uv story (KNOWLEDGE) | BUILD/TARGETS | yes | yes | heavy, tiny Python ecosystem | active | Not investigated |
| `uv` itself | native | `uv run --package X`, `uv sync --package` (READ workspaces doc) | **none found** (no affected feature in docs or search) | build/wheel cache only; "rebuilds a local member only when pyproject/setup changes" (`cache-keys`, search snippet) | zero | Astral | Not a task cache. Source of the graph (uv.lock + member pyprojects), which tools/affected.py already walks |
| `una` (python-polylith/una) | KNOWLEDGE: build backend plugin for uv/hatch | n/a | none | none | imposes bases/components/projects layout | small | Not investigated; wrong shape (shelf packages are independent libs) |
| `python-polylith` | lists uv, hatch, pdm, poetry, rye, pixi, pants (READ: https://github.com/davidvujic/python-polylith) | n/a | `poly diff` / `poly test` exist (KNOWLEDGE; page did not mention) | none | forces bases/components/projects layout | active | Refuse: restructures repo |
| hatch / pdm workspaces / rye | hatch has `hatch run` envs (KNOWLEDGE); pdm has own lock; rye superseded by uv (KNOWLEDGE) | hatch: `[tool.hatch.envs.*.scripts]` | none | none | n/a | n/a | No affected, no cache: do not solve the problem |

## Q3 Per-package task definitions in pyproject.toml (TESTED for poe)

- poethepoet 0.48.0: `[tool.poe.tasks]` in `packages/a/pyproject.toml`; both `cd packages/a && uvx --from poethepoet poe check` and `uvx --from poethepoet poe -C packages/a check` from the root ran `echo checking-a`. So a thin root runner can do `poe -C packages/<p> check`. (Note: `uvx poethepoet` fails; need `--from poethepoet poe`.)
- Turborepo reads tool declarations in member pyprojects (ruff/pytest/mypy/etc. in dependencies) and maps tasks itself, with per-member override (READ). Not tested.
- moon wants `moon.yml` per project, Nx `project.json`, Pants `BUILD`: none of these live in pyproject.toml. `[tool.moon]` does not exist as far as I found (KNOWLEDGE: unverified).
- Cost to the shelf: 52 packages x one tasks table. Gain: the Makefile stops knowing package names, but the tasks (ruff, pyrefly, deptry, pytest) are identical for every package, so per-package tables are duplication; central config + a loop is DRYer. Per-package tables pay off only for the few odd packages (browser lane, extras). Verdict below.

## Q4 Verdicts for THIS repo

Constraints: consumers install by git ref (uv only, so Q2 is not a blocker for anything below); blueprint checks are stdlib Python.

| Option | Verdict | Why |
|---|---|---|
| Keep `tools/affected.py` (merge-base diff, uv-graph walk, reverse dependents, "unknown path = everything" fail-safe, stdlib) | ✅ keep | Does the affected half with zero deps. Every tool above would re-derive the same graph from the same pyprojects. Its safety defaults are the valuable part: copy them into whatever replaces it |
| Task result caching | ✅ do later, cheaply: hash (package files + transitive dependents' files + uv.lock + tool versions) -> skip on hit, in affected.py or a tiny sibling | Nothing off the shelf gives this without a runner. Untested; this is the only gap vs Nx/Turbo |
| Turborepo (experimental uv flag) | untested, ❌ now | Experimental by its own docs; adds node + turbo.json to a pure-Python repo; its affected + cache is exactly what affected.py + hash cache gives. Re-check when the flag is removed. Cheapest first experiment if the owner insists: root turbo.json only, no per-package files |
| Pants | ❌ refuse | BUILD per dir, own lockfile model, uv lockfiles experimental (2.32), no uv remote cache. A rewrite of the setup, not an addition |
| Bazel / Buck2 / Please | ❌ refuse | Hermetic rewrite; disproportionate for ~52 small libraries |
| moon | untested, ❌ now | moon.yml per package or heavy inheritance config; Python/uv toolchain unstable at v2 rc, not verified at 2.6.1 |
| Nx + @nxlv/python | untested, ❌ | Community plugin, project.json per package, node dependency, uv support dating unclear |
| polylith / una | ❌ refuse | Imposes bases/components layout; shelf packages are independent distributions |
| hatch / pdm / rye workspaces | ❌ refuse | No affected, no cache; uv already covers the workspace role |
| poethepoet per-package `[tool.poe.tasks]` | ✅ only for packages that deviate from the default gate; do not stamp 52 copies | Tested working with `-C`. Default tasks stay central |
| "Makefile is a thin runner" | ✅ adopt as framing: Makefile -> `tools/` Python -> per-package override tables | Answers the owner's unease without a new tool |
| Move to pip-compatible sibling deps (`dep @ git+...` in member pyprojects) | ❌ not now | Only needed if a non-uv consumer appears; uv root-source mechanism works today |

Open risks to note in the design: (1) sibling resolves at the requested tag's commit, so a consumer pinning only mcp-result-wire gets whatever page-tsv/lean-wire sat at that commit: acceptable, but document it. (2) Behaviour tested on uv 0.10.12 only.

Sources: https://turborepo.dev/docs/guides/tools/python · https://www.pantsbuild.org/blog/2026/05/28/pants-2-32 · https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection · https://moonrepo.dev/blog/moon-v2-rc · https://moonrepo.dev/docs/concepts/cache · https://github.com/moonrepo/moon/releases · https://cdn.jsdelivr.net/npm/@nxlv/python@23.0.0/README.md · https://github.com/lucasvieirasilva/nx-plugins · https://github.com/davidvujic/python-polylith · https://docs.astral.sh/uv/concepts/projects/workspaces/
