## ADDED Requirements

### Requirement: Runbook-to-skill conversion is earned, not swept
`WORKFLOW: SEAM`'s `PROMOTE` direction, when the candidate is a `docs/runbooks/*.md` procedure being
considered for conversion into a `Kind: skill`, SHALL require evidence that a live agent has
demonstrably missed the runbook (failed to find or follow it when it should have) before conversion —
the same "protection is earned" test the constitution already applies to contracts (Article V). A
blanket or speculative conversion of a runbook to a skill SHALL NOT proceed under `PROMOTE`.

#### Scenario: A runbook is a candidate for skill conversion
- **WHEN** an agent considers converting `docs/runbooks/<name>.md` into `skills/<name>/`
- **THEN** it can point to a concrete instance of an agent missing or not following the runbook —
  absent that, the runbook stays a runbook and the conversion does not proceed

#### Scenario: A runbook is converted speculatively "just in case"
- **WHEN** an agent proposes converting a runbook to a skill with no missed-runbook evidence, citing
  only that it "might get used more" or "would be handy as a skill"
- **THEN** `WORKFLOW: PROMOTE` rejects the conversion — this is protecting on fear, forbidden by
  Article V, now also costing every consumer session a measured token tax with no demonstrated need
