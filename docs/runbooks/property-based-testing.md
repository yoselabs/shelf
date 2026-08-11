# Runbook — adopt property-based testing on a shelf package

**Additive, never a replacement.** A property suite lives alongside a package's existing
example-based tests, in its own file (`test_property_<pkg>.py`), and never removes or
weakens an example test. Hypothesis is a real, workspace-wide dev dependency (root
`pyproject.toml`, `dependency-groups.dev`) — no package declares it itself, same pattern
as `pytest-asyncio`.

**Origin.** Written after three probes (K project 160, hypotheses H016/H017/H018, probes
P012/P013) ran the same idea across a toy task, a Dafny substrate, and a real package
(`settings-base`) and found the same failure pattern every time: **verification-authoring
quality, not the tool, is what determines whether a property suite catches anything.**
Every rule below exists because it was the specific thing that went wrong.

## When to add one

A package earns a property suite when it has a **real invariant** — something that must
hold across an input space, not just at the specific inputs a human happened to write
examples for. Signals worth reaching for this runbook:

- **Idempotency** — applying an operation twice must equal applying it once
  (`managed-region`'s marker block, anything with a "seen" or dedup check).
- **Conservation / no-leak** — a total, a count, or a secret set must never silently grow
  or shrink (`settings-base`'s secret-stripping, `http-cache`'s content-hash dedup).
- **Round-trip** — encode then decode (or format then parse) should recover the original,
  or should be well-defined for every input, not just the happy path
  (`lean-wire`, `mcp-result-wire`, `page-tsv`, `convert-md`).
- **Crash-safety / atomicity** — an operation must never leave observable state
  half-done (`atomic-io`'s write, `async-scope`'s LIFO teardown).
- **Tiered/boundary logic** — a function with magnitude- or range-based branches
  (`timefmt`'s four tiers) — though check first whether the example suite already
  hand-covers every boundary; if it does, a property suite adds least value here.

**Skip it** for thin I/O wrappers and provider-dispatch glue (`any-browser`, `anyllm`,
`anyembed`, `browser-cookies`, `http-fetch`, `git-porcelain`) — their "logic" is mostly
calling an external system correctly, which a property test doesn't exercise any better
than a mock-based example test, and writing one risks the tautology trap below for no
real gain.

## Writing the properties — the six failure modes already found, and the fix

**1. Tautological properties.** [[S053]] and [[S055]] independently found the identical
blind spot in two unrelated verification paradigms (a TypeScript property test and a
Dafny postcondition): a property that checks the code's own bookkeeping is internally
consistent, not whether the bookkeeping is *correct*. Concretely: `sum(recorded_deltas)
== balance_change` is satisfied even if the delta *formula* itself is wrong, because the
same wrong formula produces both sides of the equation.

  *Fix:* state the property against an independently-computed expected value, or against
  a domain fact that doesn't reuse the code under test's own intermediate output. If you
  can't write the property without calling the function you're testing to compute half of
  it, it's tautological.

**2. Construction-bypass blind spots.** [[S053]]'s bug 5 was invisible to the property
suite because Hypothesis's generated state was built directly via `st.builds`/`fc.record`,
never going through the package's own (buggy) construction helper. A property suite that
generates its own fixtures from scratch tests a *parallel* code path, not the one real
callers use.

  *Fix:* where a package exposes a constructor/factory function, route generated inputs
  through it at least once, or write a separate property specifically targeting that
  function. Don't assume generating the target shape directly is equivalent to calling the
  package's own API.

**3. Generator coverage gaps for adversarial inputs.** [[S053]]'s bug 1 (idempotency) went
uncaught because `fc.uuid()`-style generators essentially never produce a *duplicate* id by
chance — the property was correctly written, but the input space it explored never
included the adversarial case it existed to catch.

  *Fix:* for anything keyed by an id/dedup field, explicitly generate collisions
  (`hypothesis.strategies.shared`, or reuse a small fixed pool of ids rather than
  `st.uuids()`) rather than trusting uniform random generation to find them. Keep at least
  one explicit example test for the exact adversarial case too — belt and suspenders,
  cheap insurance the property alone doesn't buy.

**4. The test infrastructure itself, not the product, is what's flaky or wrong.** [[S058]]
found three bugs in this pattern before reaching a trustworthy result on `settings-base`,
all in the *test*, none in the product:

  - `pytest`'s function-scoped fixtures (`monkeypatch`, `tmp_path`) are **not** reset
    between Hypothesis-generated examples inside one `@given` call. Hypothesis's own
    health check catches this and fails loudly — don't suppress it, fix it: use
    `pytest.MonkeyPatch.context()` as a context manager inside the test body, and
    `tempfile.TemporaryDirectory()` instead of the `tmp_path` fixture.
  - Hypothesis's default 200ms per-example deadline is too tight for any property doing
    real file or network I/O, and a `DeadlineExceeded` under system load looks exactly
    like a flaky assertion failure until you read the traceback with `--tb=long`. Set
    `@settings(deadline=None)` explicitly for I/O-touching properties; don't leave it to
    chance.
  - A generated fixture that gets serialized (e.g., written as YAML) can be reinterpreted
    by the format itself — an unquoted key like `true` parses as a boolean, not the
    string you generated. Quote generated keys/values explicitly when writing to a format
    with its own type coercion (YAML, TOML, CSV).

**5. Assertions built on `str.rstrip()`/`str.split()` mis-handle an empty trailing
segment.** [[S059]] found this once (lean-wire), and [[S060]] found the SAME bug shape
again two packages later (page-tsv) without recognizing it from having just read this
runbook — writing a lesson down does not guarantee it transfers within the same session
that wrote it. `"header\n\n".rstrip("\n")` strips BOTH trailing newlines when the last
line is itself empty, silently miscounting lines. *Fix:* never `rstrip()` before
splitting to count lines; assert `.endswith("\n")` then split on `text[:-1]`, or count
`"\n"` occurrences directly.

**6. An assertion that counts a separator character can be fooled by generated content
containing that same character.** [[S060]] (record-mine): a test counted `"·"`
occurrences to infer how many links were rendered, and Hypothesis eventually generated
link text that itself contained `"·"`, inflating the count. *Fix:* count a structural
marker the content can't produce (e.g. `"["` — exactly one per rendered
`[anchor](href)` — rather than the separator between them), or restrict the generator's
alphabet to exclude characters with structural meaning in the output format.

## Verifying a property suite before trusting it

A property suite passing once is weaker evidence than an example suite passing once,
because Hypothesis reseeds its random exploration on every run. **Rerun a new property
file 5–8 times before trusting a green result** — [[S058]] found a genuine failure on the
5th run after 4 clean ones, and it took another ~15 reruns to reproduce and diagnose (it
turned out to be the deadline issue above, not a product bug). A property suite that only
gets run once in CI and never rerun locally during authoring is a suite whose reliability
nobody has actually checked.

```sh
for i in 1 2 3 4 5 6 7 8; do uv run pytest packages/<pkg>/tests/test_property_<pkg>.py -q; done
```

## Confirming the addition is non-breaking

Before considering a package done, run the **whole workspace's default test command**, not
just the new file — a new test file with an import error breaks collection for everything,
not just itself:

```sh
uv run pytest --cov --cov-report=term-missing --cov-fail-under=65
```

## Worked example: a real, non-tautological finding, and how it was handled

`atomic-io`'s round-trip property (`Path.read_text() == written_text`) failed
reproducibly on `text='\r'`. Diagnosis before assuming a product bug (per the four
failure modes above): the raw bytes on disk **were** exactly `\r` — confirmed with
`Path.read_bytes()` — so `atomic_write_text` itself is byte-faithful. The mismatch was
Python's own universal-newline translation on **text-mode read**, which silently turns a
lone `\r` into `\n`. Two changes followed from this, not one: the property was rewritten
to assert against `read_bytes()` (the guarantee the function actually makes), and the
function's docstring was extended to state the newline behavior explicitly — a real,
previously-undocumented contract gap, found by generating unicode/control-character
input no hand-written example had tried. This is the shape a genuine finding takes: not
"the code is wrong," but "the property assumed a stronger guarantee than the code (or the
platform underneath it) actually makes," which is itself worth fixing in the docs even
when nothing needs to change in the implementation.

## Package rollout status (2026-08-08)

Surveyed all 27 packages against the "when to add one" criteria above.

| Status | Packages |
|---|---|
| **Done** | `settings-base` (${VAR} interpolation + secret-stripping), `atomic-io` (round-trip, overwrite-is-total, no-temp-file-survivor, arbitrary nesting depth), `managed-region` (idempotency, always-exactly-one-pair, prose-preservation, escape-neutralizes-injection), `lean-wire` (line-oriented invariant + independent reversibility check of `_escape`), `mcp-result-wire` (the pure `_project_row`/`_apply_to_items` core of `ListViewMiddleware`), `timefmt` (tier-shape + independently-recomputed precision + negative-input crash-safety), `async-scope` (LIFO teardown under any failure pattern, record-after-enter, memoized-builds-once at any concurrency), `sqlite-resource` (on_open runs exactly once under any concurrency, close/ensure idempotency for any repeat count), `http-cache` (variant isolation, content-hash independently verified, exact ttl_s>0/<=0 boundary), `dom-schema` (OK/EMPTY/ROT verdict selection on synthetic HTML, including the all-fields-missing→ROT-not-vacuous-OK edge case), `a2effect` (the kind-taxonomy validation state machine — core-kind protection, non-core-base rejection, extension resolution), `page-tsv` (envelope-key fidelity + TSV line-count through the assembly seam), `json-in-html` (content-type/body-sniffing predicates, rank_payloads-is-a-permutation, generic-script round-trip), `record-mine` (depth-indent exactness, char/link truncation bounds, to_markdown header consistency), `convert-md` (the three calibrated fidelity-grade thresholds, generalized off the real-corpus examples to arbitrary constructed input) — 15 packages, 55 new property tests, all stable across 8+ reruns |
| **Surveyed, skipped with a reason** | `duckdb-sidecar` (thinner than expected — one function, already well-covered, no further generalizable invariant), `plugin-surface` (the real logic — priority sort — is inline in a function that needs dynamically-generated importable Python modules to exercise in isolation; disproportionate cost for a well-known, low-risk operation) |
| **Skip — thin I/O/dispatch, low value per "when to skip" above** | `any-browser`, `anyembed`, `anyllm`, `browser-cookies`, `http-fetch`, `git-porcelain`, `content-extract`, `html-fragment`, `llm-cache`, `llm-wobble` |

Re-triage this table whenever a package in "not yet done" gets a real bug report in its
invariant-bearing logic — that is the concrete trigger for moving it up the priority order,
not a schedule.
