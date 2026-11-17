## Why

ogy (consumer) hand-writes its argparse tree beside the ops functions it calls. verb-cli maps one signature to flags; ogy needs subcommands from `{name: fn}`, positional parameters, `Literal` as choices, and shared parameters (`Target`: repo, kb, rev, ontology) folded into every verb. The same verb list later feeds verb-mcp.

## What changes

Additive, 0.2.0: `POSITIONAL` marker, `flags_of(fn, choices=False)` (Literal/Enum choices, opt-in), `FlagSpec` gains `positional`, `variadic`, `choices`, `enum`, and `VerbCli(verbs, shared=)` with `parser()`, `parse()`, `invocation()`, `specs()`. Existing a2kay calls behave as before.

## Scope

`packages/verb-cli`, its catalog manifest and the `ogy--verb-cli` use-case. No tag, no consumer repoint.
