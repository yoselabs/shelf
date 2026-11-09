## Output ownership

`_Output` supplies inherited post-initialization redaction for frozen result dataclasses. Its writable base annotation conflicts with the immutable descendant fields. A `TYPE_CHECKING` readonly property describes the actual frozen contract without installing a runtime descriptor, adding dataclass fields, reordering constructor parameters, or duplicating post-init methods.

## Collection shape

Type existing empty fake trees as `dict[str, str]`, parent files as `Mapping[str, str]`, and exclusion lines as `list[str]`. Dictionary/trailer parsing explicitly unpacks partition triples and retains `(key, value)` pairs. Partition at the first separator preserves the existing parser behavior, including values containing additional separators.

## Verification

The explicit package type check is the failing evidence (18 errors before edits). Existing contract, history, parser and diagnostic tests verify unchanged runtime behavior. Do not add tests that merely mirror annotations. Run explicit package types and the normal affected gate, recording both independently. Hidden-ancestor gate discovery remains owned by `shelf-j4qq`.
