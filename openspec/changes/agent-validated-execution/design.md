# Minimal API and evidence

Status: proposed, not an accepted owner policy. Baseline d3d611c.

## Existing source and callers

| Evidence | Consequence |
|---|---|
| `packages/any-agent/src/any_agent/supervisor.py:78` and `:259` | Reuse started/ref hooks; started runs behind the registered exec gate. |
| `supervisor.py:100` and `:348` in the same directory | Reuse RunOutcome and the existing run function; preserve worker, termination, watcher and summary facts. |
| `packages/any-agent/src/any_agent/harnesses/codex.py:94` | Nonsealed launch forwards the caller's schema file using --output-schema; no answer validator here. |
| Same Codex module `:217` | Summary extracts the answer file, else last message; raw ref/tokens remain in summary.res. It does not populate Summary.data. |
| `packages/any-agent/src/any_agent/protocol.py:74` | Summary.stands is existing answer evidence; data defaults to None and cost to 0.0, neither proves an answer or known cost. |
| `supervisor.py:180`, `:233`, `:285` | Ref callbacks run in the pump; raising can terminate it. Five-second joins do not establish complete output drainage. |
| `packages/any-agent/src/any_agent/classify.py:102` | Existing execution classifier remains separate from answer text. |
| `packages/anyllm/src/anyllm/providers/_agent.py:18` | Actual existing caller already composes run and classification. Its completion/cancellation policy is not the factory contract; do not copy or modify it here. |

Paths abbreviated as supervisor.py refer to the full any-agent path in the first row.
The current factory composition only inspects repositories/tasks; `consumer.md` is
an explicit proposed caller, not a claim of existing integration.

## Answer operation

Proposed exports (Python signatures, record fields shown without implementation):

```python
@dataclass(frozen=True, slots=True)
class DecodedAnswer[T]:
    value: T

@dataclass(frozen=True, slots=True)
class MissingAnswer:
    pass

@dataclass(frozen=True, slots=True)
class InvalidAnswer:
    kind: Literal["json", "schema"]
    reason: str

type Answer[T] = DecodedAnswer[T] | MissingAnswer | InvalidAnswer

def decode_answer[T](text: str, decode: Callable[[object], T]) -> Answer[T]: ...
```

Whitespace-only text is missing. Otherwise consume exactly one complete JSON value,
allowing JSON whitespace around it. Reject trailing documents/prose, Markdown fences,
duplicate object keys at any depth and nonfinite numbers (including numeric overflow).
Do not extract a convenient substring, strip fences or repair syntax. JSON null is a
value, not missing; the caller decoder decides whether it meets its schema.

After strict JSON parsing, call decode exactly once. The decoder validates domain
shape and returns T; ValueError means expected schema rejection and becomes
InvalidAnswer(kind="schema"). Unexpected errors, such as TypeError/RuntimeError in
a broken decoder, propagate. Do not blanket-catch Exception or BaseException.
Malformed JSON becomes InvalidAnswer(kind="json"). Bound reported reasons to 300
characters; retain the original answer only in the existing execution evidence.
No decoder or helper changes RunOutcome, Summary.data, classification or cost.

Use stdlib json with explicit strictness checks and object-typed decode input; no
new dependency or generic JSON Schema implementation. The factory's schema artifact
and typed decoder must describe the same contract; conformance is factory-owned.
Reviewed nearby helpers: any-agent/_json.py is event coercion/types, any-contract
checks contract number/capabilities or schema drift, any-json-doc owns file documents,
and json-match is assertion matching. None supplies this strict typed-answer operation;
do not add their file/contract/testing semantics to the execution path.

## Owning fake at the existing call

Proposed testing-only surface (no pytest runtime dependency is needed):

```python
class FakeRun:
    def __init__(self, outcome: RunOutcome, *, refs: tuple[str, ...] = ()) -> None: ...
    def __call__(
        self, harness: Harness, spec: LaunchSpec, timeout: float,
        hooks: RunHooks | None = None,
    ) -> RunOutcome: ...
    # calls records the arguments actually received, for consumer assertions.
```

Require an explicit outcome.worker fixture; never invent a PID or infer liveness.
The fake has one consumable execution. Record invocation, call hooks.started with
that worker, deliver configured native refs in order through hooks.ref, then return
the configured raw RunOutcome unchanged. A second invocation refuses as an exhausted
fake, exposing accidental retries. If started raises (including BaseException),
propagate it and deliver neither refs nor a terminal return. No launch occurs.
Empty refs means no session; a ref delivered immediately before the return represents
a late session. Repeated refs remain observable, not deduplicated by library policy.
Fixture refs and terminal summary.res must be internally consistent where both report
a session. FakeRun does not manufacture an answer-validity result: the consumer
always invokes the same decode_answer afterward, even for failure fixtures.

This is the precise subset called by the proposed first consumer: four positional
arguments, no live/limits/gone/log/policy/net_up/clock overrides. The real run function
accepts it unchanged; its harness defaults and NullSink apply. FakeRun is not advertised
as a drop-in for all Supervisor observers/options. Extend only for an actual consumer.
It supplies semantic ordering, not threads, timing, output pumps, process death or
stop proof. Ref callbacks must be bounded and nonraising, as in the real consumer;
the fake does not promise real-run propagation of a raising ref callback. No fake
Popen, process state, token registry, scheduler, DB, timeouts or subtree model.

## Failure boundaries retained

Registration refusal can propagate before execution. Postpermit launch uncertainty
can still raise RegisteredStartUncertainError while retaining the already published
worker; this change neither turns that into MissingAnswer nor erases registration.
A run exception has no terminal RunOutcome to decode. The caller retains facts it
already durably accepted and follows factory reconciliation.

A returned outcome with valid JSON may still describe failed execution. Conversely,
a nonzero signal exit after answer grace can preserve an answer. Keep rc, stop,
summary.stands, classifier inputs and answer validity independently observable; do
not define success as rc == 0 or as DecodedAnswer alone. Factory decides acceptance.

Ref persistence must not throw into the pump or retry indefinitely. The factory owns
bounded nonraising publication and explicit unresolved/unavailable handling; volatile
pending ref input is not durable acceptance. This proposal does not fix ref callback
fault transport, pump/drain completeness, descendant custody or coroutine cancellation
(separately tracked as shelf-rf1y). A worker return is not a whole-workload stop proof.
Missing usage remains unknown; Summary.cost's default zero is not measured free cost.

## Proposed test boundary

Use the existing real-child style in tests/test_registration.py with CodexHarness
and a harmless Python child emitting Codex-shaped JSON events, never the Codex CLI.
Assert hooks and retained outcomes, then call decode_answer just as the factory does.
Run the same answer/callback-order consumer assertions against FakeRun. Exercise
failed exit with valid answer text, answer-grace facts, invalid/missing/schema-invalid
answer, duplicate/trailing/nonfinite JSON, absent/late ref and registration refusal.
Keep existing gate tests as the process safety proof; fake tests cannot prove exec
ordering, drainage or descendant cleanup. Decoder programming errors must escape;
invalid answers must neither cause a second run nor acquire a session by invention.
