# a2effect — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(the ledger carries that). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

## 0.2.0

- `class E(AppError): kind = ...`  ⇒  `class E(AppError): kind = ...; code = "snake_case"` (missing or inherited `code` → `TypeError` at definition)
- intermediate base `class B(AppError): kind = ...`  ⇒  `class B(AppError, abstract=True)` (may omit `kind`/`code`; instantiating → `TypeError`)
- `InputError`/`AuthError`/`PolicyError`/`InfrastructureError` concrete  ⇒  abstract (subclass with a `code`)
- `ErrorEnvelope{type, kind, base_kind, retryable, hint, details, cause, envelope_version: "1"}`  ⇒  `ErrorEnvelope{code, message, hint, retryable, details, envelope_version: "2"}`
- `UnexpectedDefect` envelope `type="UnexpectedDefect"`  ⇒  `code="internal_error"`
- `pydantic_validation_error_enricher` returns `InputError`  ⇒  returns `InvalidInputError` (`code="invalid_input"`, an `InputError`)
- `envelope._extract_cause`  ⇒  removed
- new: `a2effect.codes(root) -> dict[str, type[AppError]]` (raises `ValueError` on a duplicate code); `AppError.is_abstract()`
- `contract_tests` envelope/surface-parity checks compare `type`/`kind`  ⇒  compare `code`
