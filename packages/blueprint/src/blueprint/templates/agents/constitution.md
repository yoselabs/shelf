# Constitution

How work is done in this repo. Short on purpose. Reads on top of the shelf constitution
(https://github.com/yoselabs/shelf/blob/main/docs/constitution.md), which this file never copies:
where the two differ, this file wins for this repo and says why.

## Articles

| # | Article | Why |
|---|---|---|
| 1 | **Done = the bead's acceptance scenarios green and `just check` green.** `just check` runs the cross-file checks over the whole repo and narrows tests to what the change reaches (shelf ADR 0021). The full test run is CI, shared-file changes, keystone beads and nightly. No "pre-existing", no "unrelated file". | A full test run per change costs minutes and catches little the narrowed run misses (lifesim, 79: the gate caught 1-3 of 22 reds) |
| 2 | **Test first, from a scenario.** The planner writes the acceptance as scenario text (Gherkin); the writer implements the steps, then the code. No free-written unit tests. See [testing.md](testing.md). | A test written after the code only confirms what the code does; volume is not purpose |
| 3 | **Never skip a hook or the gate.** No `--no-verify`, no `SKIP=`, no commenting out a check. A red check is fixed or the rule is changed in a reviewed commit. | A bypassed gate trains everyone to bypass it |
| 4 | **A guard is seen red before it is trusted.** Plant the violation, watch the gate fail, remove it. | A check that never failed may check nothing |
| 5 | **Files are truth; indexes are derived.** Never hand-edit a generated index, catalog or report: change the source and regenerate. | Hand edits are overwritten and conflict |
| 6 | **One concept per file.** A big file means a missing boundary: find it, do not trim lines. | Parallel work stays on disjoint files |
| 7 | **Leave the code smaller than you found it.** Delete the dead, collapse the duplicate. | Accumulation without pruning is drift |
| 8 | **Suppress nothing silently.** A suppression is one scoped line in the config with a reason; never inline `# noqa`, `#pragma`, `@ts-ignore` without it. | Inline suppressions hide where the rule is weakened |
| 9 | **Decide anything reversible yourself and record it as an assumption** (a bead comment starting `Assumption:`). Ask the owner only before a step that cannot be undone. | See below. Asks stalled beads and made little sense to the owner |
| 10 | **Decisions are written down** as ADRs ([domain.md](domain.md)); chat is not a record. | The next session has no memory of this one |
| 11 | **Compatibility is a declared phase.** `docs/blueprint/blueprint.toml` says `phase = "early"` or `"released"`. While `early`, nothing is precious (code, saves, screenshots): no migrations, shims or compatibility tests. | Tokens spent on compatibility buy nothing before the first consumer |
| 12 | **Slice by feature.** One bead = one checkable behaviour inside one feature folder plus its Core contract. More behaviours or folders become child beads, each landing alone and unwired; the last child wires the entry point. No feature flags. | Small landings avoid drift; in task-loop data a 1-stage bead lands 84% vs 63% for 2 stages, at 4.3M vs 11.3M tokens |
| 13 | **Core changes need a reason.** A plan that touches Core says why the change cannot live in a feature. | Core churn is the main sign that slicing is failing |
| 14 | **Shared files are split per feature** where they can be: translations, config, content, public-API lists. | One feature's change should not trigger every test |

## What is the owner's

| Ask the owner (cannot be undone) | Decide yourself (record the assumption) |
|---|---|
| Spending money or reaching outside the repo (publish, deploy, delete data) | Naming inside the code, file placement by [architecture.md](architecture.md) |
| A public contract with a consumer, once `phase = "released"` | Which test level, which helper, how to split a task |
| Overriding a blueprint checkpoint or an article here | Fixing a red check the right way |
| A standing rule | A choice with two defensible answers and a cost: take one, write why |

## Health signals

Read [health.md](health.md) before planning. A bad trend is a defect in slicing or in the system, not noise.

Ask in this form: the decision, why it matters, the options with their cost, your recommendation.
Never a bare question and never an unrequested wall of reasoning.

## Changing this file

- Add an article only after a failure it would have prevented; cite the failure.
- Remove an article that no check, hook or review enforces and that no one has cited in a quarter.
- This file is a map of rules, not a style guide: stack rules live in the stack file, not here.
