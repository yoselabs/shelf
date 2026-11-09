## MODIFIED Requirements

### Requirement: Frozen output results retain their public construction contract

Result records SHALL preserve existing fields, constructor parameter order, immutability and inherited diagnostic redaction. Static typing SHALL accurately describe output as readonly, with no runtime property installed on the base.

#### Scenario: Existing callers construct output results

- WHEN callers construct the existing frozen result records
- THEN fields and output redaction behave as before
- AND explicit package type checking accepts immutable output fields

### Requirement: Parser and fake collection types are concrete

Existing parsing and fake operations SHALL retain runtime semantics while producing concrete key/value pairs and typed empty collections. Explicit package type checks SHALL pass without added `Any`, casts or ignores.

#### Scenario: Typed package validation

- WHEN the package source is explicitly passed to pyrefly
- THEN the package reports no type errors without changes to gate discovery or severities
