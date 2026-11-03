---
name: shelf-scan
description: Scan a codebase for code that belongs in the shelf instead — find duplicated or generic modules, judge each one adopt, evolve, promote or skip, and file the findings as one epic of beads. Invoke as /shelf-scan in the repository to scan, optionally with a path or module list.
disable-model-invocation: true
---

# shelf-scan

Goal: less code in the host repo. Every module the host owns is judged against the shelf
(`$SHELF`, default `~/Workspaces/shelf`) and gets one verdict with the reason it fails the other three.
You orchestrate; Sonnet subagents read; you verify and file.

**Resume rule:** after compaction or a new session, re-invoke the skill, find the scan epic in the
host's tracker (label `shelf-scan`), and continue from its first child that has no verdict.

## Verdicts

| verdict | meaning | file as |
|---|---|---|
| adopt | the shelf already has it; the host reimplements it, or vendors it and never imports it | bug-sized task, fix-now |
| evolve | the shelf has most of it; the host's extra is generic | task in the shelf repo |
| promote | generic, no shelf equivalent | task: new package |
| skip | the host's product or glue; or too thin to earn a package | no bead; one line in the report |

Read `rubric.md` before judging: the tests behind each verdict, the naming rule, the stdlib-only rule.

## Steps

1. **Inventory the shelf.** Read `$SHELF/AGENTS.md` and `docs/constitution.md` (Articles VI-VIII), then
   `ls $SHELF/catalog` and each entry's `capability` line. Write the one-line-per-package list into the brief.
2. **Map the host.** `git ls-files`, group by directory into seams of 5-15 modules each. A seam is a
   directory plus its callers; one reviewer per seam. Skip generated code, vendored copies and tests.
3. **Dispatch reviewers.** One read-only Sonnet subagent per seam, all in one message, using `brief.md`
   verbatim with the seam filled in. Each returns one row per module in the format the brief fixes.
4. **Verify before judging.** Re-run every count, grep and size a verdict leans on. A claim you did not
   re-run is not evidence; a wrong count has already sunk one scan ("18 files", actually 4).
5. **Settle each module.** Apply `rubric.md`. Then ask the owner only the forks that are taste, priority or
   risk: a package name, a sequencing, a rewrite of a live consumer.
6. **File.** One epic labelled `shelf-scan`, one child per adopt, evolve or promote. Use the host's own
   tracker verbs and its body template; for `bd`, bug type needs Steps to Reproduce, Expected, Actual,
   Acceptance Criteria and Touches, other types need Acceptance Criteria and Touches. Findings live in beads;
   write no markdown report files.
7. **Report.** A table: module, verdict, reason, bead. Then the owner's open forks. Nothing else.

## Gotchas

- "Only this repo uses it" is no reason to skip. The shelf promotes at one consumer (Article VII).
- Glue stays: a client for the host's own backend, a dashboard on its API. Dependent on the host's
  contracts means skip.
- Count a repo as a consumer or prior art only if it is alive. Ask the owner when unsure.
- A name with the `any-` prefix promises swappable backends. A wrapper of one tool is named for the tool.
- When the host vendors a shelf package but never imports it, the verdict is adopt; the fix is to import it.
- A host with no pyproject (stdlib-only plugin) can use only packages that vendor cleanly: check the
  package's dependencies before promising it.
- Judge the wrapper's verbs by the tool's real verbs, not by what one consumer calls today.
- Never edit `$SHELF`, the host or a plugin cache from this skill. It reads and files beads.
