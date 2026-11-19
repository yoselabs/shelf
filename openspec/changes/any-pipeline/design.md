# Design: any-pipeline

## Decision 2026-11-19: asyncio-native (Denis)

Stage functions are `async def`; concurrency is `asyncio` and nothing else. Why it is also better, not only requested:

| need | asyncio tool | what it fixes |
|---|---|---|
| branches at the same time | `asyncio.TaskGroup` | a failed branch cancels its siblings and nothing is left running; `asyncio.gather` leaves orphans |
| at most N of a stage | `asyncio.Semaphore` | no thread pool to size |
| a time limit | `asyncio.timeout` | **a real timeout** for any stage that awaits (the thread design could only record an overrun) |
| a child process | `asyncio.create_subprocess_exec`, killed on cancel | the FluidAudio shape, with the same real limit |
| a blocking sync function | `blocking(fn)` = `asyncio.to_thread` | explicit at the call site; a sync function given where async is required is a type error (spike3: `bad-argument-type`) |

Names come from Python's own vocabulary where one exists: `gather(a, b)` (arity 2-4, built on `TaskGroup`; the raw `asyncio.gather` is what the lint preset bans) and `>>` for "then".
`(hear & diar) >> label` was considered; `&` nests (`(a & b) & c` is `tuple[tuple[A, B], C]`), so parallel is `gather(...)` and only sequence is an operator.
There is one way to call it: `await run(...)`. A sync script writes `asyncio.run(run(...))`; the package does not ship a second, sync API (constitution III, no dual paths).
Still not guaranteed: a stage that blocks the loop without awaiting (CPU work) cannot be interrupted; wrap it in `blocking` or run a child process.

## The idea

A pipeline is built from immutable values and cannot be built wrong. Each rule below is either rejected by the type checker, rejected when the
pipeline is built (before one item runs), or made impossible by what the runner does. Nothing is left to review by eye.

## What is enforced, and by what

Spike (2026-11-19, pyrefly strict, python 3.12, `/scratchpad/spike`): each ✅ was tried with a wrong program and the checker rejected it.

| # | mistake | how it is ruled out | enforced by | spike |
|---|---|---|---|---|
| G1 | a stage is fed the wrong shape | `Stage[I, O] >> Stage[O, P] -> Stage[I, P]`; `gather(Stage[I, A], Stage[I, B]) -> Stage[I, tuple[A, B]]` | pyrefly | ✅ `Words` into a stage wanting `tuple[Words, Turns]` is `bad-argument-type`; two stages with different inputs is `bad-argument-type`; the good chain reveals `Stage[Audio, Labelled]` |
| G2 | fan-out result mistyped | `gather` with the arity written out (2, 3, 4) | pyrefly | ✅ `Stage[int, tuple[str, float, bytes]]`. A variadic `*Ts` form is **not** expressible in pyrefly (it accepted a meaningless signature without error), so arity stops at four; wider fan-out is built by nesting |
| G3 | a stage with no bound or no timeout | `Limit(calls, seconds, tries)` is a required argument of every `Stage`: no default, so there is no unbounded stage to write | pyrefly (`missing-argument`) ✅ + build check that every number is > 0 | ✅ / runtime |
| G4 | an error swallowed | a stage's failure is never raised to the caller and never returned: the runner catches it, stores a `Failed(stage, item key, why)` in the run's `Report` and carries on with the next item. There is nothing to forget to check. `Outcome[T] = Ok[T] | Failed` is closed, and a `match` with `assert_never` is exhaustive | pyrefly | ✅ `assert_never` on `Outcome` is an error while `Failed` is unhandled. ❌ a bare ignored call (`risky()`) is **not** detected by pyrefly or ruff, which is why failure is a record, not a return value |
| G5 | a stage edits what the next one reads | items are frozen dataclasses; assignment is rejected. A stage's input type that is not frozen is refused when the pipeline is built (`dataclasses` params, runtime) | pyrefly (`read-only`) ✅ + build check | ✅ / runtime |
| G6 | a cycle | composition returns a new value; a stage cannot name a later stage. A DAG by construction | the shape of the API | n/a |
| G7 | unbounded or deadlocking concurrency | a stage names the pool it runs in (`Pool("transcribe", 2)`) and the body gets no handle to acquire another; the runner takes every pool a stage needs in one ordered step | the API; pools are provided by the caller (any-speech wires any-lease) | n/a |
| G8 | work redone, or done twice | a stage that writes anywhere outside the process declares `key: Callable[[I], str]` (required for `Persistent` stages); the runner skips a stage whose key already has a result | pyrefly (required) + runner | by test |
| G9 | an unbounded retry | `tries` is in `Limit`, an int >= 1; retries sleep with no sleep in user code. There is no `forever` | build check | by test |
| G10 | hand-rolled threads, sleeps, orphan tasks | the package ships a ruff `banned-api` preset (`threading`, `concurrent.futures`, `asyncio.gather`, `asyncio.create_task`, `time.sleep`, bare `except:`), plus the `ASYNC` rules for blocking calls inside `async def` for modules that build pipelines, with the reason per ban | ruff TID251 | by test that the preset rejects each |
| G11 | no record of what ran | every stage run emits a `StageRecord(stage, item key, seconds, outcome)` into the `Report` automatically | the runner | by test |

## What typing cannot give, said plainly

- **A timeout on blocking code.** `Limit.seconds` is a real `asyncio.timeout` for a stage that awaits and for a child process. A `blocking(fn)` stage runs in a thread that cannot be killed: the stage fails at the limit and the thread is abandoned until it returns. Say so; do not trust a timeout that does not exist.
- **Purity.** A stage can still read a global. The ruff preset bans the common leaks; the rest is review.
- **Sensible numbers.** `Limit(1_000_000, ...)` type-checks.

## API (v0.1.0)

```python
from any_pipeline import Limit, Stage, gather, run

hear  = Stage("hear",  transcribe, Limit(calls=2, seconds=3600, tries=1))     # Stage[Audio, Words]; transcribe is async def
diar  = Stage("diar",  diarize,    Limit(calls=1, seconds=3600, tries=3))     # Stage[Audio, Turns]
label = Stage("label", assign,     Limit(calls=4, seconds=60,   tries=1))     # Stage[tuple[Words, Turns], Labelled]

pipeline = gather(hear, diar) >> label         # Stage[Audio, Labelled]; a wrong edge is a type error
report = await run(pipeline, [audio_a, audio_b], key=lambda a: a.path, workers=4)   # Report: outcomes, StageRecords
```

`gather` runs its branches at the same time inside a `TaskGroup`, each limited by the `calls` of its `Limit`; `>>` runs the next stage when the previous one returned. One item never stops another.

## Names and the split

- `any-pipeline`: the domain is the pipeline, not the origin (constitution VII). `any-queue` would name the other half, which stays in any-speech until a second consumer needs it, then becomes `any-drain` (deferred bead).
- One module per concept: `stage.py` (Stage, Limit, composition), `outcome.py` (Ok, Failed, Report, StageRecord), `run.py` (the runner), `preset.py` (the ruff bans).

## Proof

any-speech's `Pipeline` (transcribe in a slot, diarize concurrently, label, record provenance, memory budget) is re-expressed as `gather(hear, diar) >> label`. That makes any-speech's `transcribe(path)` async: a breaking change, released as any-speech 0.4.0 with the CLI unchanged.
Its 96 tests stay as they are; if they need to change, the shape was wrong and the design is revised first.

## Risks

- Fan-out stops at four by type. If a consumer needs more it nests, or the arity is reopened.
- `blocking()` is the one place a thread exists (`asyncio.to_thread`); a cross-process lease wait (any-lease) goes through it and is cancelled by the lease's own timeout.
- A package this abstract can become speculation. The guard: nothing is added that any-speech's re-expression does not use, and the next feature waits for the second consumer.
