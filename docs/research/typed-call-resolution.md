# Typed call resolution and source rewriting: follow-up to checked-exceptions.md

Researched 2026-11-21 on `main` at 1633803 (pyrefly 1.3.2). Follows [checked-exceptions.md](checked-exceptions.md) (branch `w19/effects-research`). Scratch scripts were not committed.

## Verdict

- ✅ **Q1: types do fix call resolution. The check is still not worth enabling.** pyrefly's `--report-pysa` resolves 96.7% of calls (30.2% to a shelf function, vs 22% for the ast pass). The pass then finds **2 to 10 cross-package hits**, none a clear bug. The blocker was never resolution; there is almost nothing to catch.
- ❌ **Q2 new syntax** (`x = f()?`): refuse. Breaks pyrefly, ruff and every AI reader; verified below.
- ❌ **Q2 runtime enforcement by import-time rewrite:** refuse. Hides the check from every tool that reads source.
- ✅ **Q2 compile-time inspection** (read-only `ast` pass, what `tests/test_arch_*.py` already do): the only form that fits. No rewriting needed.

## Q1. What exposes resolved callees

| Tool | Result |
|---|---|
| `pyrefly check --report-pysa DIR --report-pysa-format json` | ✅ per-module call graph: each call site (line:col) to `call_targets` / `init_targets` (`Function` or `Overrides` with module, function id, name), plus `definitions/` (function id to def line, class). Whole-project, typeshed and venv included: 1.1 GB, **114 s** (plain `pyrefly check` 15 s). Not stable API ("experimental" family). |
| `--report-trace`, `--debug-info`, `lsp`, `tsp` | Not run. LSP go-to-definition would work per call, too slow for 15k calls. |
| pyright, ty, jedi | Not installed; not tried (`uvx` would fetch them). |
| stdlib alone | ❌ `ast`/`symtable` have no types. |

### Prototype and numbers (`packages/*/src`, 421 files, 14,676 call sites matched)

Rule: callee outside the caller's package, public, raises a shelf typed exception directly (class defined in the shelf, 87 of them) or transitively through resolved callees; no enclosing `try`/`suppress` covers it (MRO-aware). Join script: 8 s on top of the pysa run.

| Measure | Value |
|---|---|
| Resolved to a shelf function | 4,428 = **30.2%** (1,051 via protocol dispatch) |
| Resolved to stdlib/third-party | 9,769 (66.5%); unresolved 466 (3.2%) |
| Hits, strict (protocol call resolves to the declared method only) | direct **2**, transitive **4** |
| Hits, widened (a protocol call may reach any same-package method of that name) | direct 3, transitive **10** (9 call sites) |
| Any module, same package too, strict direct / transitive | 136 / 286 |

Judged by reading all 9 call sites of the widened-transitive set (fewer than 15 exist):
- **Documented pass-through, 4 sites:** `opencode.find_exe` ("NotFound on a miss"), `Bd.__init__` (comment), `merge3_text` (`Raises` section), `any_json_doc.update` (docstring). Rule hits, no defect.
- **Undocumented pass-through, 5 sites:** `any_agent.procs.spawn`, `any_mailbox._locked`, `any_speech._slot` (2 exceptions), `jsonl_log.locked`, `Transcript.from_json` (a `ValueError` subclass). The remedy is a docstring line, not a handler.
- **Clear bug: 0.** False-positive rate on "caller forgot to handle": 9/9 if the bar is a missing handler; 4/9 (44%) if the bar is "undocumented". Read by me, one reviewer.

The wide count (286) repeats the earlier finding: the hits are deliberate re-raises, about 90 to 300 docstring edits.

### Protocol design (exception declared on the Protocol method)

- Count: **36 Protocol/ABC classes, 162 methods**; 2 have a `Raises` docstring. Callers on a Protocol resolve to the declared method (1,051 call sites), so a `Raises:` there is exactly what the pass would read.
- The shelf's Protocol impls (`FakeRepo`) are structural: pysa reports an empty MRO, so impl-to-Protocol checking is not available; the declaration and the impls can drift unchecked.
- Burden: up to 162 declarations, plus one per propagating caller. Not measured: how many of the 162 have an implementation that raises a typed exception (the real burden); I did not match impls to Protocols.

## Q2. Source rewriting

**(a) Possible.**
- `# coding:` codec (PEP 263): a custom codec decodes bytes to text, so it can rewrite `x = f()?` into plain Python before the parser sees it (`future-fstrings` does this).
- `sys.meta_path` finder or `importlib` loader: `source_to_code` can run `ast.parse`, an `ast.NodeTransformer`, then `compile`. pytest's assertion rewriting is the proof; it can wrap every call in a handler check at import.
- Macro systems (MacroPy, pyxl) use the same two hooks.
- New syntax needs the codec path, because `ast.parse` rejects `?`. A transformer only reshapes valid Python.

**(b) Breaks.** Run: pyrefly on `x = f()?` gives `Parse error: Got unexpected token ?`; ruff gives 2 `invalid-syntax` errors (plus the namespace-package note); `ast.parse` raises `SyntaxError`. So the gate, `just check`, fails on the dialect. Also:
- Editors and LSP see the source, not the rewritten code; coverage and tracebacks map to rewritten line numbers unless every transform preserves them (pytest does extra work for this).
- AI readers meet an unknown dialect; each file needs a header line and a rule note, and a model's priors about Python stop holding. That raises token cost and API explanation for every consumer. This repo's rule ("smaller API wins") counts against it.
- Every consumer must install the hook; a package imported without it silently runs different code.

**(c) Read-only alternative.** An `ast` pass that only reads (`tests/test_arch_*.py`, 19 files, e.g. `test_arch_atomic_writes.py`) needs no rewriting, no dialect, and lints on the real source. For exceptions, the narrow slice already recommended is the swallowed-handler arch test.

| Use | Verdict |
|---|---|
| New syntax (`?`) | ❌ gate fails on parse; AI cost |
| Runtime enforcement at import | ❌ invisible to every tool; different code under test and in use |
| Compile-time inspection | ✅ already the shelf's method |

No rewriting prototype built: the parse failures above already show the trade-off; a working `?` codec is over 40 lines.

## Recommendation

Do not build the call-graph check. If one is wanted later, use pysa JSON as the resolver (one dev-time run, 114 s, so a `check-all` step, not `check`) and revisit when strict cross-package hits pass ~50. Next step: ship the swallowed-handler arch test.

## Not measured

- Impl-to-Protocol raising count; pyright, ty, jedi; the LSP route; `except*`; handler bodies that re-raise (counted as covered); same-named classes (merged by name); exceptions from stdlib/third-party; pysa runtime on a warm cache.
- My 9-site judgement is single-reviewer. The earlier study's `suppress` gap is closed here (`suppress` is read).
