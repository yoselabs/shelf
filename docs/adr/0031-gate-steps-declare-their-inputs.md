---
id: 0031
title: Every gate step declares the files it reads; a step whose inputs did not change is not started
statement: gate-inputs.toml lists each step's input globs; any-gate does not start a step none of whose inputs changed; blueprint checkpoints stay one step reading the whole repo.
concerns: [gate]
status: accepted
decided_by: owner
updated: 2026-11-20
distilled_into: any-gate inputs.py (`steps` skips, `--all` for check-all), gate-inputs.toml, blueprint gate.step-inputs; bead shelf-lb5h
---

# 0031 — Gate steps declare their inputs

## Decision

- **Declared, plain text.** `gate-inputs.toml` at the repo root: one key per step (the recipe name), a list of fnmatch globs. `["*"]` says the step reads the whole repo. No entry means the step always runs.
- **Unaffected means not started.** `any-gate steps` compares the changed files (the upstream merge-base, as `any-gate changed`) with each declared step; a step none of whose inputs changed gets no process and no file read. Git is asked three times at most, and not at all when no step declares anything.
- **Everything runs** when the changed files cannot be told (no base), when `gate-inputs.toml`, the `justfile` or `.blueprint/` changed, and in `check-all` (`steps-all`, `--all`), the release gate.
- **A golden test per step** (`packages/any-gate/tests/test_inputs.py`): on an unchanged tree no declared step starts a process and git is asked at most three times.
- **Audit row** `gate.step-inputs` (new checkpoints warn first, ADR 0018): every step `check` hands to `steps` declares its inputs.
- **Blueprint checkpoints are not scoped.** The `blueprint` step declares `["*"]`: a checkpoint reads repo-wide facts, so per-checkpoint scoping would need each to declare inputs, and a wrong declaration is a silent miss. The cost that earlier kept them unscoped was 0 s on Linux; on Windows with Defender each process start costs about 20 ms, and the one `blueprint` step is one process, which an unaffected commit now skips whole. Revisit when one checkpoint's work is measured, not before.

## Rejected

- Scoping each checkpoint now: more declarations to keep true, for a saving the step-level skip already takes on an unaffected commit.
- Declaring inputs in the justfile: the justfile is rendered and shared; the declaration is the repo's own, so it is its own file.

## History

- 2026-11-20: decided (shelf-lb5h), from ogy PR #3 (affected.py): a staged run spawned about 51 git processes.
