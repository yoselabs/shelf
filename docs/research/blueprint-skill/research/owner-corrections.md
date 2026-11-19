# R6 — owner corrections during repo setup (one pass, provisional)

Settles: blueprint's anti-patterns list and missing checkpoints (design.md R6). Not cross-checked;
per the cross-check rule, a second pass is due before any row drives a decision.

**Method.** A python stream over the owner's local session transcripts, user
turns only (no sidechains, no tool results, no injected skill text), keyword regex for setup topics
and correction tone; 3,299 owner messages across 13 repos, ~830 matched, read by hand.
`search_session_transcripts` was tried first: one snippet per session, and for correction phrases
("why didn't you", "you forgot") it returned the same injected skill text in ~30 sessions, so it
was not usable here. Owner feedback memories (private) read for
setup rules. Quotes are voice transcripts: verbatim, with `[sic]`/`[x]` repairs only. Cited as
`repo · date`. Client, people and host names redacted.

## Findings

| # | quote (verbatim, short) | where | what the agent did wrong or missed | implies |
|---|---|---|---|---|
| 1 | "how are linters failing at CI level, but not before we push the code" | homelab · 2026-09-12 | local gate was a subset of CI; agent pushed on a green local run | CP: local gate ⊇ CI, checked by diffing workflow steps against `make check` |
| 2 | "Do pre-commit install … add it into make check to check up that pre-commit is installed" | homelab · 2026-07-11 | hooks configured, never installed | CP: hooks installed, and the gate verifies it (corroborates R2) |
| 3 | "we should always rely on CI … If CI doesn't work … there is like a critical problem" | homelab · 2026-07-26 | agent went around a blocked CI by hand instead of flagging it | AP: working around a red or blocked CI; CI down is reported as critical |
| 4 | fb: "a CI job silently red for 9.5 days / ~130 runs … a green Deploy read as 'CI is fine'" | fb:local-gate-must-match-ci · 2026-08-12 | agent read one green workflow as "CI healthy" | CP: after a push, the agent checks every workflow, by name |
| 5 | "We should never do anything mainly with SSH … should be defined either through [Nix/Komodo]" | homelab · 2026-07-05 | imperative fixes over SSH (e.g. `docker network create`) | AP: manual state on a host; CP (infra pack): everything to rebuild from scratch is declared in the repo |
| 6 | "every service templae [sic] should have it's own quirkcs.md. wtf we store it in a2web feedback?!" | homelab · 2026-08-08 | quirks recorded in another project's feedback channel | CP: quirks live next to the thing they describe |
| 7 | "how did it happen? I want to prevent stale env vars" | homelab · 2026-08-17 | an env var outlived its use; nothing checked | CP: declared env vars ⇔ read env vars, checked in the gate |
| 8 | "keep in mind, we need to ensure we will leverage build caching in CI and locally" | homelab · 2026-07-21 | Docker build design without a cache plan | CP (docker): build cache used in CI and locally |
| 9 | "Forget about [Renovate] … I'll be fine to run like scheduled work, like every … Wednesday" | homelab · 2026-10-10 | agent proposed a paid / hosted dep-update service | CP: dependency updates on a scheduled job; AP: adding a paid service without asking (principle 9) |
| 10 | "I think we need to review our CloudMD [CLAUDE.md] file first and most migrated to agents.md" | shelf · 2026-07-10 | CLAUDE.md was canonical, single-agent | corroborates F8: AGENTS.md canonical, CLAUDE.md symlink |
| 11 | "it should have no timed event messages … we should not be changing CloudMD every time" | shelf · 2026-07-10 | AGENTS.md carried dated, evolving instance data | CP: AGENTS.md holds stable rules only; rosters and dates live in derived files |
| 12 | "I don't want to have those indexes like catalog and agent loop to go stale … pre-commit hooks" | shelf · 2026-07-08 | derived indexes hand-maintained, no staleness check | CP: every index is generated and the gate fails on drift (constitution I–II) |
| 13 | "Ideally, I want linters to fail … it should fail on tests and should also fail on linters" | shelf · 2026-07-09 | contract change (stringly-typed provider name) passed the type gate | CP: contracts are typed so an upgrade breaks the consumer's linter, not runtime |
| 14 | "if we have any errors with a rough [ruff] or ty or make check, we need to fix it all anyway" | shelf · 2026-07-07 | agent treated pre-existing errors as out of scope | AP: "pre-existing drift" carve-out (already AGENTS.md DoD) |
| 15 | "onboard that project with shelf and with beads … make sure that there will be no conflicts with the gate hooks" | shelf · 2026-08-12 | beads hooks and pre-commit hooks fought; onboarding had no conflict check | CP: one hook manager; bd's hooks chained into it, proven by one commit going through |
| 16 | "please don't forget to create ADRs and mention all things which we tried and rejected" | a2web · 2026-07-03 | decision recorded without rejected options | CP: a decision record names the options rejected and why |
| 17 | "we need to retain information about other options compared … it should be trackable" | shelf · 2026-07-09 | same, second repo; also wrong primary reason recorded | same as 16; the primary reason is the evidence, not the convenient one |
| 18 | "Memory files take 35, almost 36k tokens in our context window, it's unacceptable" | a2web · 2026-08-05 | nobody measured always-loaded context | CP: always-loaded context (AGENTS.md + imports + memory) measured, with a budget |
| 19 | "session stop … make sure that we won't forget to close in the task if it's pending" | a2web · 2026-08-05 | session-start hook only | corroborates F8: session-end hook on |
| 20 | "put that 'backlog = kanban = beads' into prescription for others - beads runbook in shelf" | a2web · 2026-08-06 | a second backlog (backlog.md) kept alive next to beads | CP: one backlog; no `backlog.md`/TODO files once beads is in |
| 21 | "I want our Backlog to contain only items which are not [re]solved" | homelab · 2026-07-26 | resolved items left in the open list | CP: closed work leaves the open view, linked to the change that closed it |
| 22 | "I think we need to publish only 1 docker image - and it should include the browsers" | a2web · 2026-07-16 | variant images multiplied | CP (docker): one published image unless a variant is decided |
| 23 | "real client names, man … clear that stuff up … should we rewrite git history? … yes" | a2kay · 2026-10-08 | client, family and owner names committed to a public repo | CP: name/PII guard in the gate; history checked at onboarding |
| 24 | "Secrets - do it right now / Remote - private github" | a2kay · 2026-09-28 | secrets handling and repo visibility left undecided | CP: visibility and secrets scheme decided before the first push |
| 25 | "Make check should run use cases. And unit tests … I don't want to … schedule the nightly" | a2kay · 2026-10-09 | agent proposed a nightly-only run for slow tests | AP: tests outside `make check`; CP: every test kind runs in the gate |
| 26 | "prune unit tests. Is running for almost four hours already … is it expected?" | a2kay · 2026-10-09 | no time budget on mutation / suite run; no ETA | CP: gate and mutation runs have a time budget, measured |
| 27 | "we need to be able to run make check in a container. Maybe even by default" | a2kay · 2026-10-10 | host-only gate, slowed by host AV scanning | CP: gate runs hermetic (container) as well as on host |
| 28 | "I really want to shrink down number of unit tests tremendously" | a2kay · 2026-10-09 | agents wrote many narrow unit tests per function | AP: unit-test sprawl; feeds R1 testing (use cases first) |
| 29 | "Not small unit tests, but rather like end to end tests or integration tests" | budget · 2026-08-11 | test effort spent on code shape | same; corroborates behaviour-first testing |
| 30 | "Required field should never say … that it's okay to have empty string or zero" | a2kay · 2026-10-01 | schema accepted empty values for required fields | CP (stack): strict validation preset; required means non-empty |
| 31 | fb: "the drag-and-drop plan put BDD tests as Task 4 (last), after all implementation" | fb:bdd-first | plan wrote Gherkin last | CP: the plan's first task is the feature file |
| 32 | fb: "lane 4's 'never bind 0.0.0.0' … satisfied on 7 of 8 stacks by an unrelated env var" | fb:mutation-test-the-rules · 2026-08-02 | lint rule could never fire; green for months | corroborates principle 4 (gate seen red once) |
| 33 | fb: needle list shrank 80% when an unrelated config map was cut | fb:guard-scope-from-population · 2026-08-12 | guard sourced its needles from config | CP: guards take needles from the population they protect |
| 34 | "first we need to create a new workspace folder and move to that folder, initialize everything in there" | a2kay · 2026-07-07 | agent set up a new project inside the old repo's session | CP (new repo): own folder, own git, session moved there first |
| 35 | "We also need to add something into Cloud MD of that software itself … 'Oh, you use shelf'" | a2kay · 2026-07-07 | consumer onboarded without the shelf block in its instructions | delegated to `onboard-consumer`; blueprint checks the effect |
| 36 | "wrap up everything to be a strict as possible best linters, best layering" | a2peer · 2026-10-10 | (kickoff ask, not a miss) | corroborates strict preset + layering tool areas |
| 37 | fb: "Before running any dev/test/build command, check if there's a `make` target" | fb:use-make-commands | agent ran raw commands and killed ports by hand | CP: every routine command has a make target; AGENTS.md lists them |
| 38 | fb: "Don't open GitHub PRs to finish feature branches" | fb:no-prs | agent opened PRs on a solo repo | CP: merge policy recorded per repo (solo → direct to main) |

Agent practice, out of scope per proposal (one line each): "running for 13 mins already wtf"
(shelf · 2026-08-12 · c52ce5f8) and "wtf 34 minutes. I had to iterrupt [sic] you" (a2web ·
2026-08-02 · 685a3917) — long runs with no ETA or check-in.

## Evidence for F3 (restart vs migrate)

- "I kind of want to remove the whole thing honestly and start from scratch … removal of
  everything will be the first step except linters" (reco · 2026-07-15 · 98c71ca2).
- "I don't feel attached to any of the code we we [sic] wrote … the shape of the code doesn't
  matter that much" (budget · 2026-08-11 · a241bf2f).
- Signal both share: behaviour is captured first (requirements, e2e tests), then code is free to go.
  A restart keeps the gate (linters) and the behaviour tests, never the code.

## Implied checkpoints not already in design.md / proposal.md areas

Already covered there, so only corroborated above: hooks installed (R2), AGENTS.md canonical +
symlink (F8), session-end hook (F8), derived indexes (constitution), no carve-outs (DoD), gate
seen red once (principle 4), behaviour-first testing (areas), CI pinned + gate.yml (R2/R3).

New candidates (deduped):

1. **Local gate ⊇ CI.** `make check` runs every step CI runs; verified by diffing the workflow.
   After a push, every workflow is checked by name, not inferred (rows 1, 4).
2. **CI down is loud.** A blocked or red CI is reported as critical; no manual workaround around
   it (row 3).
3. **No test outside the gate.** No nightly-only or manual-only suites; every test kind runs in
   `make check` (row 25).
4. **Gate time budget.** Gate and mutation runs are timed; the budget is recorded and a breach is
   a finding (rows 26, 27).
5. **Hermetic gate.** `make check` also runs in a container (row 27).
6. **Always-loaded context budget.** Tokens of AGENTS.md, its imports and project memory are
   measured at audit; over budget is failing (row 18).
7. **AGENTS.md holds no dated or roster data** (row 11) — a mechanical check: no dates, versions or
   package counts outside derived files.
8. **One backlog.** No `backlog.md` / TODO lists beside beads; closed work leaves the open view
   (rows 20, 21).
9. **Decision record completeness.** Each decision names rejected options, why, and the primary
   evidence (rows 16, 17).
10. **Name / PII guard.** Gate fails on client, people or owner names in tracked files; git history
    scanned once at onboarding of a public repo (row 23).
11. **Visibility and secrets decided before first push** — public/private recorded; secrets scheme
    (e.g. sops) chosen (row 24).
12. **Hook manager single-owner.** One hook framework; beads and others chained into it, proven by
    a real commit (row 15).
13. **Quirks co-located** with the component they describe (row 6).
14. **Env var parity.** Declared env vars equal the ones the code reads (row 7).
15. **Guard needles from the population**, never from an unrelated config list (row 33).
16. **Typed contracts at package seams**, so upgrades break at lint time (row 13).
17. **Strict validation preset**: required fields reject empty values (row 30, stack pack).
18. **Docker: one image, build cache in CI and locally** (rows 8, 22).
19. **Dependency updates on a scheduled job**; no paid service without the owner's yes (row 9).
20. **Infra repos are declarative-only**: no state created by hand over SSH (row 5, infra pack).
21. **Make targets for every routine command**, listed in AGENTS.md (row 37).
22. **Merge policy recorded** per repo (solo → direct to main, no PRs) (row 38).
23. **New repo kickoff step:** own folder and git, session moved there before setup (row 34).

Anti-patterns list seed: CI workaround (3) · pushing on a local-only green (1) · pre-existing-drift
carve-out (14) · nightly-only tests (25) · unit-test sprawl (28, 29) · Gherkin written last (31) ·
dated data in AGENTS.md (11) · second backlog (20) · rule that cannot fire (32) · guard sourced from
config (33) · manual host state (5) · paid service added unasked (9) · decision without rejected
options (16).
