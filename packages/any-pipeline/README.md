# any-pipeline

**Stop hand-writing pipelines.** A pipeline is a typed value: async stages composed with `>>` (then) and `gather` (at the same time),
each bounded by a `Limit` it cannot omit, failures recorded per item and never swallowed. Asyncio-native; stdlib plus `atomic-io` (for `FileStore` only).

```python
from any_pipeline import Limit, Stage, gather, run

hear  = Stage("hear",  transcribe, Limit(calls=2, seconds=3600, tries=1))   # transcribe: async def (Audio) -> Words
diar  = Stage("diar",  diarize,    Limit(calls=1, seconds=3600, tries=3))   # async def (Audio) -> Turns
label = Stage("label", assign,     Limit(calls=4, seconds=60,   tries=1))   # async def (tuple[Words, Turns]) -> Labelled

pipeline = gather(hear, diar) >> label            # Flow[Audio, Labelled]
report = await run(pipeline, audios, key=lambda a: a.path, workers=4)       # a sync script: asyncio.run(run(...))
report.done      # tuple[Ok[Labelled], ...]     report.failed   # tuple[Failed, ...] (key, stage, why)
report.records   # one StageRecord per stage run: seconds, tries, ok, skipped
```

One item never stops another: a stage that raises, times out or returns something mutable becomes a `Failed` in the report.
`gather` runs its branches in a `TaskGroup`, so a failed branch cancels its sibling. `Limit.seconds` is an `asyncio.timeout`, a real one for
anything that awaits. A plain function goes in through `blocking(fn)` (a thread, which a timeout abandons rather than stops).
`stage.otherwise(lambda why: fallback)` makes a failure a typed value instead of a failed item (the record still shows it); `run_one(flow, item, key=...)` returns the value and raises the stage's own exception. `Persistent(name, fn, limit, key=..., store=...)` keeps a result under `key(item)` and skips the call next time. Fan-out is `gather`, `gather3`, `gather4`.
`FileStore(directory)` is a `Store[str]` of one file per key (atomic write through `atomic-io`, the key hashed to a safe name, the directory made on the first `put`), so a `Persistent` step survives the process: `Persistent(..., store=FileStore(Path("cache")))`.

## Pattern: re-ask a source for new items

There is no watcher or scheduler here, on purpose: the caller's loop asks the source again and `run` skips what a `Persistent` stage already holds.

```python
seen = -1
while True:
    items = read_source()                                           # a file, a list, a query: whatever grows
    report = await run(pipeline, items, key=item_key, workers=4)    # a finished item costs a store read, not a call
    if len(items) == seen and not report.failed:
        break                                                       # nothing new, nothing to retry
    seen = len(items)
    await asyncio.sleep(60)
```

Failed items are retried on the next pass (nothing is stored for them); count passes per key in the caller to give up after N.

## What is checked, and when

| mistake | caught by |
|---|---|
| a stage fed the wrong shape; two branches with different inputs | the type checker (`unsupported-operation`, `bad-argument-type`) |
| a stage with no `Limit`; a plain function where an async one is required | the type checker (`missing-argument`, `bad-argument-type`) |
| an unhandled failure case in a `match` over `Outcome` | the type checker with `assert_never` |
| editing a frozen item | the type checker (`read-only`) |
| a limit of zero; a stage name used twice; fewer than one worker | when the pipeline is built or run (`ValueError`) |
| an item or stage result that is not frozen | the run (`TypeError`, or a `Failed` for a result) |
| threads, pools, `asyncio.gather`, bare `create_task`, `time.sleep`, bare `except:`, blocking calls in `async def` | the ruff preset: `any_pipeline.preset.ruff_config()` |

`tests/test_types.py` runs pyrefly on programs that must be rejected and fails if one is accepted. Not guaranteed by anything: a stage that
computes without awaiting cannot be interrupted, a stage that reads a global, a limit of a million.

Design and evidence: [openspec/changes/any-pipeline](../../openspec/changes/any-pipeline/design.md).
