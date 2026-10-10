# Constitution

How work is done in this repo. Short on purpose. Reads on top of the shelf constitution
(https://github.com/yoselabs/shelf/blob/main/docs/constitution.md), which this file never copies:
where the two differ, this file wins for this repo and says why.

## Articles

| # | Article | Why |
|---|---|---|
| 1 | **Done = `make check` green over the whole repo.** No "pre-existing", no "unrelated file". | A partial gate lets drift accumulate where nobody looks |
| 2 | **Test first, from a scenario.** Write the failing scenario that states the behaviour, then the code. See [testing.md](testing.md). | A test written after the code only confirms what the code does |
| 3 | **Never skip a hook or the gate.** No `--no-verify`, no `SKIP=`, no commenting out a check. A red check is fixed or the rule is changed in a reviewed commit. | A bypassed gate trains everyone to bypass it |
| 4 | **A guard is seen red before it is trusted.** Plant the violation, watch the gate fail, remove it. | A check that never failed may check nothing |
| 5 | **Files are truth; indexes are derived.** Never hand-edit a generated index, catalog or report: change the source and regenerate. | Hand edits are overwritten and conflict |
| 6 | **One concept per file.** A big file means a missing boundary: find it, do not trim lines. | Parallel work stays on disjoint files |
| 7 | **Leave the code smaller than you found it.** Delete the dead, collapse the duplicate. | Accumulation without pruning is drift |
| 8 | **Suppress nothing silently.** A suppression is one scoped line in the config with a reason; never inline `# noqa`, `#pragma`, `@ts-ignore` without it. | Inline suppressions hide where the rule is weakened |
| 9 | **Decide only what is yours; ask the owner the rest.** | See below |
| 10 | **Decisions are written down** as ADRs ([domain.md](domain.md)); chat is not a record. | The next session has no memory of this one |

## What is the owner's

| Ask the owner | Decide yourself |
|---|---|
| Anything that changes scope, a public contract, or a standing rule | Naming inside the code, file placement by [architecture.md](architecture.md) |
| Spending money or reaching outside the repo (publish, deploy, delete data) | Which test level, which helper, how to split a task |
| Overriding a blueprint checkpoint or an article here | Fixing a red check the right way |
| A choice with two defensible answers and a cost | A choice with one answer in a doc: follow the doc |

Ask in this form: the decision, why it matters, the options with their cost, your recommendation.
Never a bare question and never an unrequested wall of reasoning.

## Changing this file

- Add an article only after a failure it would have prevented; cite the failure.
- Remove an article that no check, hook or review enforces and that no one has cited in a quarter.
- This file is a map of rules, not a style guide: stack rules live in the stack file, not here.
