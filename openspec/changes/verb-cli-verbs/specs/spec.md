## ADDED Requirements

### Requirement: A set of verbs is one parser
`VerbCli({name: fn}, shared=cls)` SHALL produce one parser with a subparser per verb, `shared` parameters as flags on each, positionals for `POSITIONAL` parameters, and argparse choices for `Literal`/`Enum` parameters; `parse(argv)` SHALL return the verb and the exact call arguments.

#### Scenario: shared flag and positional
- **WHEN** `show ADDR --repo /r` is parsed
- **THEN** the verb is called with `ADDR` and the shared instance holding `repo="/r"`

### Requirement: Existing behaviour is unchanged
`flags_of(fn)` without `choices=True` SHALL keep a `Literal` as one JSON flag.

#### Scenario: default
- **WHEN** `flags_of` is called without options on a Literal parameter
- **THEN** the spec needs JSON
