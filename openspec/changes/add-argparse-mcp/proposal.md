## Why

ogy builds its MCP tools by reflecting its argparse tree (ogy shelf audit T17). That is a technical mechanism, not
ogy's business. The end state is `verb-mcp` over verb-cli 0.2; until then a promotion of the existing design is cheaper.

## What Changes

- New package `argparse-mcp`: `tools_from_parser(parser, run)` returns one FastMCP tool per subcommand, with the
  schema from options, positionals and choices and the parser's global options folded into every tool. A call runs
  the injected `run(argv) -> (exit code, lines)` in process; argparse's `SystemExit` becomes a usage result.
- Built on FastMCP 3 (`mcp<2`), the stack of mcp-arg-errors and mcp-result-wire.

## Impact

- New catalog entry, ogy use case, ledger delivery. Superseded by `verb-mcp` after verb-cli 0.2.
