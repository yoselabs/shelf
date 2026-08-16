## 1. Glossary and catalog schema

- [x] 1.1 Add `skill` to the `Kind` enum in `docs/glossary.md`'s spine diagram (one line, alongside
      `primitive | any-lib | composite | cli | framework | config-preset`) — no new glossary concept.
- [x] 1.2 Verify `tools/catalog.py`'s `render_catalog` and its field set accept `kind = "skill"` with
      no other catalog field changes (name, tier, release, capability, implementation, status, owner,
      notes already generic); adjust only if something is silently Python-shaped. Confirmed generic —
      no catalog.py change needed. Found and fixed a real gap this surfaced:
      `test_catalog_release_is_current.py` assumed every catalog entry maps to `packages/<name>/`,
      which would have broken the first real `kind = "skill"` entry; made both its assertions
      Kind-aware.
- [x] 1.3 Confirm `make catalog` regenerates `catalog/README.md` cleanly with a `kind = "skill"`
      dry-run entry (create and delete a throwaway `catalog/_skill-kind-smoke-test.toml` to verify,
      do not leave it committed). Verified — including that a deliberate name/dir mismatch in the
      throwaway was correctly caught by the fixed test before cleanup.

## 2. Resolution and loop distillation

- [x] 2.1 Write `docs/resolutions/0014-skill-is-a-shelf-kind.md` — the alternatives rejected (second
      loop file, second repo, blanket runbook conversion, hand-rolled char-count budget vs `claude
      plugin details`, and a single mechanism covering both `.agents/skills/` tooling skills and
      catalog-registered skills — see design.md's "Two skill tiers" decision), each with its
      rationale, and an `Expires:` date.
- [x] 2.2 Distill the operational takeaway into `docs/agent-loop.md`'s `WORKFLOW: SEAM` → `PROMOTE`
      direction: the earned-conversion gate for runbook→skill promotion (matches
      `specs/agent-loop-workflows/spec.md`'s ADDED requirement). Also branched steps 3–5 by Kind
      (unit dir, token-budget check, tag mechanism) — the loop was only implicitly Kind-generic
      before; now it says so explicitly at the exact points that differ.
- [x] 2.3 Fill the resolution's `Distilled into:` field pointing at the `PROMOTE` step edited in 2.2,
      per `EVOLVE-THE-LOOP`'s same-change requirement. Verified via
      `tests/test_resolution_distillation.py`.
- [x] 2.4 Add a short cross-reference note to `docs/consuming-the-shelf.md` near its
      `onboard-consumer` mention: that skill is a pull-based, `.agents/skills/` tooling skill,
      deliberately outside the `Kind: skill` catalog contract — so a future agent doesn't try to fold
      it into the catalog or gate it on `claude plugin details`.

## 3. Shelf plugin scaffold

- [x] 3.1 Create `.claude-plugin/marketplace.json` at shelf root, listing one plugin whose `source` is
      a relative in-repo path to `skills/` (pattern confirmed against `context7-marketplace`'s
      same-repo marketplace+plugin layout).
- [x] 3.2 Create `plugin.json` for the shelf's skills plugin (name, description, version starting at
      `0.1.0`, author).
- [x] 3.3 Create an empty `skills/` directory (`.gitkeep` — no skill content authored here; that's
      `shelf-c2s`'s job once this contract exists).
- [x] 3.4 Run `claude plugin validate` against the scaffold to confirm `marketplace.json`/`plugin.json`
      are well-formed before anything depends on them. Went further than the task asked: ran the full
      end-to-end path (`claude plugin marketplace add` → `claude plugin install skills@shelf`) against
      the real scaffold — it installed cleanly. Un-registered and uninstalled afterward so the
      smoke-test didn't leave the user's global `~/.claude` config pointing at a dev scaffold.

## 4. Enforcement gates

- [x] 4.1 Add a gate-coverage test (mirrors `tests/test_gate_covers_every_package.py`'s shape) that
      fails if a `skills/*/` directory exists with no wired eval coverage
      (`tests/test_gate_covers_every_skill.py`). Anti-vacuity confirmed: it fails against a throwaway
      uncovered skill dir, passes once removed. No non-zero population floor yet (unlike the package
      gate) since zero skills exist as of this change — noted in the test's own docstring.
- [x] 4.2 Add a token-budget assertion (mirrors `tests/test_catalog_release_is_current.py`'s "hand-
      maintained fact checked against the tool that knows it" shape): the catalog entry's recorded
      always-on token figure is checked against a fresh `claude plugin details <name>` run at
      `PROMOTE`/`RECONCILE` time — implemented as a runbook step now (`agent-loop.md` PROMOTE step 4),
      per the task's own scoping (no skill exists yet to assert against in CI); becomes a real
      automated test once the first skill lands.
- [x] 4.3 Confirm `make check` still passes with the scaffold in place (nothing in `packages/*` should
      be affected). Green: 836 passed, 86.30% coverage, whole repo.

## 5. Close the loop

- [x] 5.1 `make catalog` if any `catalog/*.toml`/`use-cases/*.toml` changed (expected: none — this
      change adds schema capability, not a catalog instance). Confirmed no drift.
- [x] 5.2 Append a `ledger/0091-skill-kind-delivered.toml` `delivery` row.
- [x] 5.3 `bd create` a follow-up bead (`shelf-uvf`) for the first real skill's `PROMOTE` (nominates
      `shelf-c2s`'s catalog/onboard skill as the likely vehicle, in the bead's own text) to exercise
      this contract end-to-end and surface the numeric token-budget ceiling design.md left open. No
      hard `bd dep` edge to `shelf-c2s` — they may turn out to be the same effort; a synthetic
      blocking relationship between two beads that might collapse into one would be structure without
      a fact behind it.
- [x] 5.4 `make check` green (836 passed, 86.30% coverage, whole repo, confirmed twice). Merge/push
      withheld per session profile — reporting status and proposed commands, waiting for explicit
      authority rather than pushing unprompted.
