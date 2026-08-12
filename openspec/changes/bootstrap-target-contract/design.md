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
   works, until it doesn't,              make bootstrap-verify
   silently                              (environment: is THIS clone wired?)
                                              │
                                              ▼
                                        a developer learns their
                                        fast feedback is broken

   separately, and this is the safety net (D4):

        make check ──► content assertions (no local path= source, …)
                       true on any clone, needs no bootstrap, no hooks,
                       no CI mode. The gate that actually enforces.
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

## D4 — Split by what is being checked, not by what it costs

**Decision.** `make check` always runs **content assertions**. `bootstrap-verify` holds
**environment assertions** and is *not* a `check` prerequisite.

An earlier draft of this design proposed making `check` depend on the whole of
`bootstrap-verify`, with a fast/slow split decided by measurement if it proved expensive.
That was wrong, and the question "does CI even need beads and hooks?" is what exposed it. Cost
is the wrong axis. The right one is **what kind of thing is being asserted:**

| | content assertion | environment assertion |
|---|---|---|
| example | no local `path=`/editable shelf source | the pre-commit hook actually blocks; `bd config get` reads back |
| what it describes | the repo's own files | this working copy's configuration |
| true on a fresh clone? | yes — needs nothing installed | no — meaningless until bootstrapped |
| meaningful in CI? | **yes, and it is the point** | no — CI never commits, so hooks are inert |
| home | `make check` | `make bootstrap-verify` |

Conflating them produced a bad conclusion: that hook liveness is safety-critical and therefore
worth taxing every `make check`. It isn't, once the content assertion is in the gate.

**The inversion this produces is the real result.** Today `forbid-local-shelf-source.py` is
invoked by nothing but the pre-commit hook — so a per-clone, silently-disableable artifact is
the *sole* enforcement path, which is exactly how this repo ended up unguarded without anyone
noticing. Moving the assertion into `make check` makes the hook *fast feedback* rather than
enforcement: you learn at commit time instead of at gate time, and a dead hook costs latency,
not safety.

That reframes the neighbouring work rather than just relocating a check:

- `shelf-gag` stops being a downstream consequence and becomes the **cheapest, highest-value,
  and first** of the three. It depends on neither of the others. It has been unblocked and
  re-prioritized to P1.
- `shelf-efh` (the guard is dead under `core.hooksPath`) stays a real bug — fast feedback that
  lies is still worth fixing — but it is no longer a safety hole.
- This change's hook-liveness verification becomes a **convenience**: it tells a developer
  their fast feedback is broken. Not a gate.

**On CI specifically** (this resolves design open question 2): CI needs neither beads nor
hooks. Beads has no CI role at all — nothing creates issues or syncs, and
`.beads/issues.jsonl` is committed and read-only. Hooks are inert where nothing commits. What
CI needs is `make check`, and with content assertions inside it, that is sufficient. No CI
mode, no skip flags, no special-casing.

Worth stating plainly: **this repo currently has no CI** (no `.github/workflows/`). `make
check` is the only gate that exists, which makes putting the assertion there not merely the
better option but the only one that enforces anything.

Rejected: a git hook as the enforcement point. The thing being verified is partly *whether
hooks work* — a verifier that runs as a hook cannot report its own absence.

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
- **Resolved (was: what does bootstrap do in CI?).** Nothing. See D4: CI needs neither beads
  nor hooks, and content assertions in `make check` cover what CI must enforce. No CI mode and
  no skip flags. Kept here as a record of the question, because "CI is a fresh unbootstrapped
  clone" is a reasonable worry that the content/environment split dissolves rather than answers.
