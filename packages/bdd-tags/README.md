# bdd-tags

**Stop rewriting the tag hooks every Gherkin suite grows.** A pytest plugin: install it and
it is on (entry point `pytest11`; nothing to add to a conftest).

```gherkin
@spec:entity-crud @bug:proj-12
Feature: Move an entity

  @known_bug:proj-40
  Scenario: A move keeps the attachments      # strict xfail until proj-40 is fixed

  @pending
  Scenario: A move across vaults               # collected, reported as skipped
```

## Rules

- `@spec:<capability>` and `@bug:<id>` are **traceability**, read from the feature files.
  They are not pytest markers, so `--strict-markers` does not ask for them.
- `@known_bug:<id>` is a **strict** expected failure: the scenario states the right
  behaviour, the code does not do it yet. When it passes, the run fails and the tag goes.
  Never weaken a scenario to make it pass.
- `@pending` is a scenario whose steps are not written: skipped, not failed. A missing step
  in a scenario without the tag still fails. The plugin registers the `pending` marker.
- Every other tag is an ordinary marker, registered by the suite.
