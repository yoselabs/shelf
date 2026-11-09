# One execution with separately validated answer

## ADDED Requirements

### Requirement: Strict typed answer decoding
The library MUST consume one complete JSON value and use the caller's typed decoder.
Whitespace-only text MUST be missing. Malformed/ambiguous JSON (including parser depth exhaustion) and expected decoder
ValueError rejection MUST be distinct invalid outcomes. Unexpected decoder faults
MUST propagate. No extraction, correction, retry or launch is allowed in decoding.

#### Scenario: Ambiguous output
- WHEN output contains trailing prose/documents, fences, duplicate keys or nonfinite numbers
- THEN it is invalid JSON and no repaired answer is returned.

#### Scenario: Schema rejection or programmer fault
- WHEN the decoder rejects a parsed value with ValueError
- THEN the result is schema-invalid with a bounded reason
- AND TypeError, RuntimeError and BaseException faults are not swallowed.

### Requirement: Preserve independent execution facts
Answer validity MUST NOT change RunOutcome, existing classification, answer-grace,
session or raw usage evidence. Valid JSON MUST NOT establish execution success.

#### Scenario: Valid text after failed execution
- WHEN one execution fails but returns structurally valid answer text
- THEN callers retain both the failed execution facts and the validated typed answer.

### Requirement: Owning semantic fake of the consumed run call
The fake MUST drive started, ordered observed refs and the configured raw outcome
for one four-positional-argument run invocation. Consumer composition MUST share the
real answer decoder. The fake MUST NOT simulate processes or promise drainage,
parent-death, descendant-stop or raising-ref behavior beyond the real contract.

#### Scenario: Registration refusal
- WHEN started raises
- THEN no refs or terminal outcome are delivered
- AND a second invocation is refused as an already consumed fake.

#### Scenario: Missing or late session
- WHEN no ref is configured or a ref arrives just before return
- THEN only configured observations reach the callback, without an invented session.

#### Scenario: Inconsistent fake session fixture
- WHEN observed refs are configured and the raw summary explicitly supplies a different terminal ref
- THEN constructing the fake raises ValueError instead of fabricating inconsistent observations.
