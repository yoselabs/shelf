# Affected-build tools on the shelf: hands-on trials (2026-10-10)

Bead shelf-qgz. Four tools wired into worktrees of the shelf (52 packages, uv 0.10.12), measured on
the macOS host. Full reports were scratch files; the measured facts are below. One trial each, not
repeated.

| criterion | tools/affected.py (today) | Turborepo 2.11.7 | moon 2.6.1 | Nx 23.3 + @nxlv/python 23.2.1 | Pants 2.33.1 |
|---|---|---|---|---|---|
| reads the package graph itself | ✅ 6/6 edges, optional extras included | ✅ from uv | ⚠️ 3/6 edges: a version specifier hides the dependency | ❌ nothing until 52 project.json; then misses an optional-extra edge | ✅ from imports; ~20 sys.path imports invisible |
| leaf change → only it | ✅ | ✅ | ✅ | ✅ | ✅ |
| shared change → dependents | ✅ | ✅ | ❌ dependents served stale cache | ✅ | ✅ |
| docs-only → nothing | ✅ | ✅ | ✅ | ✅ | ✅ |
| lockfile → everything | ✅ | ✅ (dry run) | ✅ once listed as input | ✅ once listed by hand | ❌ ignores uv.lock; needs its own lock |
| Makefile / root tests/ change | ✅ everything / fitness tests | ❌ nothing | ❌ nothing | ❌ nothing | not measured |
| result cache | ❌ none | ✅ 6m15s → 13.6s | ✅ 52/52 hits | ✅ 52/52 hits | ✅ content-hash |
| config added | 1 script | 23 lines | 35 lines, 6 files | 55 files + Node | 119 BUILD files + 4,647-line lock |
| extra runtime | none | Node | none (binary) | Node | its own Python, 7.2 GB cache |
| Python/uv maturity | ours | "experimental", 2 flags; needs uv ≥ 0.13 for lock-aware hashing | `unstable_*` toolchains | community plugin | uv "experimental", no remote cache |
| tests pass as they are | ✅ | ✅ | ✅ | ✅ | ❌ 43/184 files fail in its sandbox |
| git-ref installs untouched | ✅ | ✅ | ✅ | ✅ | ✅ |

## Verdicts

- ❌ **Pants**: a second build system beside uv; its own lock, 119 BUILD files, sandbox breaks 43 test files.
- ❌ **Nx**: fail-open (a package without project.json is never tested), one edge missed, Node.
- ❌ **moon**: dependents silently skip their tests after a shared change: the worst failure possible here.
- ❌ now, revisit: **Turborepo**: the closest. Graph and affected correct, real cache, small config.
  Blocked by experimental Python flags, uv 0.10.12 (needs 0.13), and root files invisible to it.
  Trigger to revisit: its Python support leaves experimental, and the shelf is on uv ≥ 0.13.

**Refuted as of 2026-10-10: "an existing tool does this better for a uv repo".** Every tool tied or
lost to tools/affected.py on finding the affected set; each beat it only on result caching.

## Recommendation

Keep tools/affected.py; add the one thing it lacks, a result cache: per package, a hash of its files,
its dependencies' files, uv.lock and the tool versions; a package whose hash passed before skips its
tests. Untested.
