# Proposed factory call, with the same real and fake boundary

This is a sketch for the future tl-8bh9.4.3.1 / .3.2.1 consumer, not factory source.
The task-loop successor currently has repository/task inspection only. Nothing here
implements its DB, admission, attempt process, lock custody or workflow policy.

## Inputs already owned by the factory

The admitted attempt supplies a fresh Codex LaunchInputs (argv/environment/cwd/prompt,
schema artifact path and answer artifact path), execution timeout and its two
publication callbacks. It chooses its domain PlanResult and decode_plan(object)
function. Its decoder enforces the schema's shape, returning PlanResult or raising
ValueError for expected validation failures. Shelf has no dependency on that type,
plan schema, factory token or DB.

For this first call the factory uses the supervisor's normal limits and NullSink;
there are no live/limits or other keyword overrides. If a real factory requirement
needs one later, review that actual boundary before extending the fake.

## Exact composition

```python
# Proposed factory-local types and operation; library signatures are in design.md.
type Execute = Callable[[Harness, LaunchSpec, float, RunHooks], RunOutcome]

# Real composition root injects any_agent.run. Tests inject any_agent.testing.FakeRun.
# Inputs include schema=the_factory_schema_path and out_file=the_attempt_answer_path.
harness = CodexHarness()
spec = harness.launch_spec(inputs)
hooks = RunHooks(
    started=register_worker,  # conditional durable registration; refusal raises
    ref=publish_ref,          # bounded, nonraising publication composition
    unattended=False,
)
raw = execute(harness, spec, timeout, hooks)  # exactly one call
answer = decode_answer(raw.summary.text, decode_plan)
# Preserve raw AND answer; factory publishes matching terminal facts, then applies
# its existing execution classification and plan-result workflow acceptance rules.
```

The existing unattended flag is counterintuitive here: True watches the attempt
process's parent and stops work when that parent changes. Explicit False allows the
attempt process to survive coordinator death, as the factory restart contract requires.

The caller uses nonsealed launch_spec so the requested schema is forwarded; the
sealed completion branch currently does not forward schema and is not this path.
The factory supplies the ordinary launch/sandbox/credential decisions. This proposal
does not change login, refusal or sealed-completion behavior.

The decode line is identical with the real and fake execute callables. No optional
library decoder parameter, second execution wrapper, new success boolean or result
callback is needed. In tests, construct a RunOutcome with explicit Worker, Summary
answer text, termination facts and raw usage/ref evidence, then inject FakeRun(raw,
refs=(native_ref,)). Do not configure an already-validated PlanResult on the fake.
CodexHarness construction is inert; its ordinary launch_spec assembles the same spec
without launching a process. FakeRun records that spec and the actual invocation.

## Observable flows

| Observation | Consumer keeps / does next |
|---|---|
| Registration accepted, ref observed, valid text | Raw outcome plus DecodedAnswer[PlanResult]; execution/workflow acceptance remains a separate factory decision. |
| Execution failure plus valid text | Preserve both facts; structural validity cannot relabel the execution as successful. |
| Answer-grace stop / nonzero rc / summary.stands | Preserve all existing facts; do not substitute an rc-only success ladder. |
| Malformed or schema-invalid text | Raw outcome plus explicit InvalidAnswer; no repair, retry, fallback or hidden second call. |
| No answer / whitespace only | Raw outcome plus MissingAnswer; do not treat Summary.data=None as the answer. |
| No native ref yet / late ref | No invented session; publish only observed ref under matching identity. Lack of ref is not proof that execution never started. |
| Registration callback refuses | Exception, no terminal outcome or decoding; fake delivers no ref/result, native gate forbids target exec. |
| Exception after accepted registration | Retain accepted worker/session facts and unresolved state; no fabricated empty completion or whole-tree stop. |
| Ref publication unavailable | Nonraising callback records bounded pending input/failure for factory reconciliation; it must not claim a durable accepted session. |
| Decoder programming error | Propagate fault; do not relabel as ordinary invalid model output. |

Factory publishes terminal facts from the returned raw outcome in its surviving
attempt process using its conditional STORE operations. That placement requires no
finished hook. It keeps custody and unresolved reservations according to its own
plan; answer decoding cannot release custody or prove descendants stopped.
