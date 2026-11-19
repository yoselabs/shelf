# any-pipeline: a pipeline is a typed value, so the common mistakes do not compile

## Why

Every consumer writes the same shape by hand: stages that pass a value on, some in parallel, each limited, each able to fail
without stopping the rest. any-speech already has one (transcribe and diarize in parallel, then label; one bad file never stops
the queue). channel-research (fetch, transcribe, LLM extraction, profile) and perform (script, voice, render) are next.
Hand-written, the same mistakes recur: a stage fed the wrong shape, concurrency with no bound, a swallowed error,
an unbounded retry, shared mutable state between stages, a hang with no timeout, work redone because nothing is keyed.

Denis's ask (2026-11-19): make the pipeline a primitive that prevents these on the syntax level, with typing doing as much as it
can, checked statically (pyrefly strict). The shape of the code matters less than what it rules out.

## What changes

- New package `any-pipeline` (stdlib only): `Stage[I, O]`, `Limit`, composition (`>>`, `gather`), `Outcome[T]`, an async runner,
  a record per stage run, and a ruff preset that bans the raw tools the primitive replaces.
- any-speech's `Pipeline` is re-expressed on it. That is the shape proof: the package is extracted from a working pipeline, not invented.

## Not in this change

- The queue half (claim a keyed job, slots across processes, failure records, skip what is current): that is any-speech's `Drain`
  and `Speech` today. It is a separate concern with other dependencies (process-lock, any-lease, atomic-io). Filed as a deferred bead
  to become `any-drain` when a second consumer needs it; a pure core with no dependencies is worth more than one package that does both.
- A pipeline DSL, config files, a graph editor, an async runtime. Plain Python values.
- Retry policy beyond a bounded count (any-failure-fp already owns what to wait).
