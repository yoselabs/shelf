# One execution, separately validated answer

Status: proposed for independent review; documentation only. Task: shelf-7a2v.
Source baseline: d3d611ca15e07bacbf39727d14174f06bdc59e2a.

## Concrete consumer and gap

The factory's first plan attempt needs one supervised Codex execution, pre-exec
registration, native-session publication and a typed plan answer. Factory plans
`docs/design/tl-8bh9.4.3.1/plan.md` (Minimum typed seams) and
`docs/design/tl-8bh9.3.2.1/plan.md` (plan execution) require this boundary.
They are in the successor task-loop repository; its consumer is not implemented yet.

Existing `any_agent.run(harness, spec, timeout, hooks)` already supplies the execution
boundary. `RunHooks.started`, `RunHooks.ref` and its returned `RunOutcome` provide the
three publication points. Keep those interfaces. Codex forwards a schema path, but
its summary returns answer text without validating it. The public package also lacks
an owning semantic fake of the run call used by this consumer.

## Proposed bounded change

Add a pure `decode_answer(text, decode)` operation and explicit typed
valid/missing/invalid results in any-agent. Factory supplies its typed decoder and
forwards its corresponding schema through existing `LaunchInputs.schema`. Add
`any_agent.testing.FakeRun`, callable at the existing run boundary. Factory composes
real or fake run with the same answer decoder, as shown in `consumer.md`.

No new execution facade, finished callback, durable state, process platform or
workflow policy. Neither run nor decoding launches a correction, retries, resumes,
switches model or falls back. Structural validity never changes execution facts.
Existing classification and factory workflow decide acceptance, including the
existing answer-grace/`Summary.stands` behavior; this change adds no success flag.

## Review and subsequent verification

Review these three documents before source or test changes. Proposed implementation
is confined to any-agent's answer helper, testing helper, exports and focused tests;
normal package metadata/OpenSpec updates follow only after implementation approval.
No factory runtime pin changes before an actual consumer uses the capability.

Tests will first expose the missing boundary, then exercise shared decoding through
real harmless Codex-shaped child output and through FakeRun. Cases include valid,
missing, malformed/ambiguous JSON, schema rejection, failed execution with valid
text, answer-grace facts, absent/late native session, registration refusal and exactly
one invocation. No model calls. Focused checks, normal/full Linux gates, independent
review and exact-final-tree native Mac verification precede delivery. This proposal
is not evidence that these gates or the future consumer have passed.
