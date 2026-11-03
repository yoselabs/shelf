# Shell command parsing and rule running

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

`parse(text) -> list[Command] | None` lexes shell text quote-aware into simple commands, in order.
Unquoted `| || & && ; ;;` newline, parens, backticks and `$(` separate commands; a separator inside
quotes stays in its word. `Command` holds `argv`, leading `NAME=value` `assigns`, non-quiet `redirects`
(`>out`, `2>>log`, `<in`) and `stdin` (here-document or here-string text). `for/while/if ... do ... done`
keywords reduce to the commands inside. A shell run with `-c` (also `eval`, or a shell fed by a
here-document) is replaced by the commands of its script, nested to depth 3; deeper nesting, an
unclosed quote or `$'...'` returns `None` (the caller decides: fail closed). `parse` never raises;
`parse(shlex.join(argv))` yields exactly `argv`; a quoted separator never splits.

`Command.name` is the program with wrappers (`sudo env nohup time timeout xargs nice ...`, their options
and `NAME=v` words) and path stripped. `has_write_syntax(text)` is a quote-blind text check for output
redirects and substitutions. `strip_heredocs`, `strip_excluded(argv)` and `strip_wrappers(argv)` are pure.

`judge(rules, tool, tool_input) -> Verdict(blocked, reason)` runs rules in order; a rule answers a
`Verdict`, a non-empty reason string (blocks) or `None`/`""` (allows). The first block wins.

Not covered (use `has_write_syntax` or a rule on the text): variable expansion, `$'...'` decoding,
substitutions inside double quotes, a shell fed by a pipe, long wrapper options with a separate value
that are not in `WRAPPERS`. No consumer app is imported; stdlib only.

Executable acceptance: `tests/test_parse.py` (bypass corpus), `tests/test_command.py`,
`tests/test_judge.py`, `tests/test_property_parse.py` and `tests/test_boundary_any_shell_policy.py`.
