# Design

## The shape of the problem

```
   TODAY                                    PRESCRIBED
   ─────                                    ──────────
   runbook (300 lines of prose)             docs/runbooks/repo-bootstrap.md
        │                                        │  (contract: what must hold)
        │ read by an agent                       │
        ▼                                        ▼
   agent re-derives the order            make bootstrap
   agent remembers to verify                  │  order = prerequisites
   agent skips step 9                         │  verify = assertions
        │                                     │  idempotent = safe to re-run
        ▼                                     ▼
   works, until it doesn't,              make bootstrap-verify  ◄── make check
   silently                                   │
                                              ▼
                                        drift fails the build
```

Prose has no idempotency, no ordering enforcement, and no failure mode. Those three
properties are the entire content of the current runbook, expressed in the one medium that
cannot provide them.

## D1 — A contract, not a CLI

**Decision.** Ship `docs/runbooks/repo-bootstrap.md` (obligations) plus a reference `Makefile`
fragment. Do not ship a `shelf-bootstrap` program.

Resolution 0004 already decided this shape for the linter toolchain — a config preset
consumers inherit, not a CLI they install — and the reasoning transfers intact: a CLI creates
a version-skew surface and a dependency, for logic that is mostly "run these in this order and
check the result." Repos differ enough (uv vs poetry, beads or not) that the shared thing is
the obligation, not the code.

The one exception is *verification logic with real substance* — proving a hook fires is
fiddly and shouldn't be re-derived per repo. That already has a home: `tools/hooks/`, which
`fix-guard-hookspath-resolution` is extending for exactly this. Bootstrap calls it. This is
extension, not a new surface.

## D2 — Ordering is a prerequisite graph, not a sentence

**Decision.** Encode every ordering constraint as a Make prerequisite.

```
bootstrap: deps hooks beads-init beads-config bootstrap-verify
                 │       │
                 │       └── depends on `hooks` — bd init must find a native
                 │           hook to chain into, or it seizes core.hooksPath
                 └── pre-commit / guard install goes FIRST
```

The `pre-commit`-before-`bd init` rule cost this session a scratch-repo investigation to
discover and is currently a bolded sentence in the runbook. Bolding is not enforcement. As a
prerequisite it is simply not possible to get wrong, and it needs no reader.

Where an order exists because of a *finding*, the finding goes in a comment at the
prerequisite — not deleted, not relegated to prose elsewhere. The next person to reorder these
targets should meet the reason at the point of temptation.

## D3 — Verify the effect, never the artifact

**Decision.** Every assertion runs the thing and observes behavior. No assertion checks that a
file exists, a marker is present, or a mode bit is set.

This is the same decision as `fix-guard-hookspath-resolution` D2, promoted to a general rule,
and this session is the argument for it. Every cheap check would have passed while the repo
was unguarded: the file existed, the marker was present, `+x` was set, and the hook was dead.
The artifact and the effect came apart, and only executing the hook could tell.

Minimum assertions the contract names:

| assertion | how, concretely |
|---|---|
| the pre-commit hook actually blocks | seed an offending state, invoke the resolved hook, require non-zero |
| declared config is in effect | read it back through the tool (`bd config get`), never trust a `set`'s success |
| a tool's hooks are reachable by git | compare `git rev-parse --git-path hooks` against where each installer wrote |
| no two tools contend for the hook slot | detect pre-commit + `core.hooksPath` together; report, don't arbitrate |

**Three outcomes, never two.** Live / not-live / could-not-check must stay distinct. Collapsing
"couldn't check" into a pass is precisely how a dead guard reported `✔`.

## D4 — `make check` depends on `bootstrap-verify` (the contested one)

**Decision.** Yes — with the cost measured before it lands, not assumed away.

The argument for: bootstrap correctness *decays*, and every decay mode found this session was
silent. A `git reset --hard` reverts tracked config. A teammate follows pre-commit's hint and
unsets `core.hooksPath`. A fresh clone never onboards. A one-shot install cannot notice any of
these; only a recurring check can. This is also the honest resolution of `shelf-gag` — "guard
enforcement is per-clone" stops mattering when the gate itself asserts liveness.

The argument against, which is real: `make check` is the inner loop, and it already runs five
tools. Verification that spawns git subprocesses on every invocation is a tax on every
developer action, forever.

**Resolution:** land it, but measure first (task 3.1). If verification costs more than ~1s,
split it — a fast path in `check` (config readback, path comparison: cheap string work) and
the expensive behavioral assertions in `bootstrap` and CI only. Do not decide this by intuition;
the whole change is an argument against trusting intuition over measurement.

Rejected: a git hook instead of `make check`. The thing being verified is partly *whether hooks
work* — a verifier that runs as a hook cannot report its own absence.

## D5 — The beads runbook: same findings, different voice

**Decision.** Rewrite the voice; keep every finding; keep it self-contained.

The user constraint is explicit: it must not tell an agent what to do manually, and a reader
adopting beads must not need a second document first. Those pull against each other only if
"self-contained" is read as "repeats the general contract" — it doesn't. It means: states the
beads-specific obligations completely, and cites the contract for the shared frame.

The transformation is mechanical:

| current voice | prescribed voice |
|---|---|
| "Verify empirically: `bd create`, then `ls .beads/issues.jsonl`" | "`bootstrap-verify` asserts export is live by writing a bead and reading the export back" |
| "Don't trust `bd config set` — confirm with `bd config get`" | "`beads-config` re-reads every key it sets; a set that doesn't read back fails the target" |
| "Install pre-commit before `bd init`" | "`beads-init` declares `hooks` as a prerequisite" |
| "`bd doctor` is not supported in embedded mode" | unchanged — a fact about the tool, not an instruction |

Note the last row. Not everything converts: findings *about bd's behavior* stay as prose,
because they are what justify the assertions. The rule is that no line should read as a task
assigned to whoever is reading. Anything that would be a task becomes an assertion the target
makes.

Deliberately preserved verbatim: the three-way status-mapping table (§1.3), the migration
classification method (§1.4), and every "verified on <repo>, <date>" attribution. Those are
judgment and evidence — automation neither replaces nor invalidates them, and stripping the
attributions would make the next contradictory observation impossible to adjudicate.

## D6 — Sequencing against `fix-guard-hookspath-resolution`

**Decision.** Guard fix lands first; this consumes it.

That change produces the first real verify-by-behavior implementation. Landing the contract
first would prescribe a pattern with zero working instances — "do NOT build on spec". Landing
the guard fix first means this change's D3 has something concrete to point at, and its
`bootstrap-verify` has something real to call rather than a stub.

## Open questions for implementation

- **Does `bootstrap` mutate a developer's git config without asking?** Setting
  `core.hooksPath`, installing hooks, and writing tool config are all local-state changes.
  Idempotent and expected under an explicit `make bootstrap`, but `make check` depending on
  `bootstrap-verify` must remain strictly read-only — a gate that silently repairs is a gate
  that hides drift. Worth stating as a hard rule if implementation agrees.
- **What does bootstrap do in CI?** A fresh CI clone is unbootstrapped by definition. Either
  CI runs `bootstrap` first, or `bootstrap-verify` needs a CI mode that skips hook liveness
  (hooks being irrelevant where nothing commits). Unresolved; decide before D4 lands.
