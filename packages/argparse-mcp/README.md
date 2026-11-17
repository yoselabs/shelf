# argparse-mcp

The subcommands of an argparse parser as FastMCP tools. One operation, two surfaces: the CLI and the
tools both end in your own `run(argv)`.

```python
from argparse_mcp import tools_from_parser
from fastmcp import FastMCP

def run(argv: list[str]) -> tuple[int, list[str]]:   # your CLI entry: exit code, output lines
    ...

server = FastMCP("ogy-mcp", instructions=parser().description)
for tool in tools_from_parser(parser(), run):
    server.add_tool(tool)
server.run("stdio")
```

- **One tool per subcommand** (one level). Name and description are the subcommand's.
- **Schema from argparse**: positionals are required unless `?`/`*`; options are optional unless
  `required=True`; `choices` become an enum; `store_true`/`store_false` a boolean; `type=int|float`
  and `append`/`nargs="*"|"+"` a typed list; `count` an integer. Help text and the default are the
  parameter description.
- **Global options** (the top parser's own) are parameters of every tool and are placed before the
  command in argv. A subcommand's own option of the same name wins.
- **In process**: `run(argv)` is called directly; no subprocess. Its `(exit_code, lines)` returns as
  `Result(exit_code, output)` (structured content).
- **Usage**: argparse's `SystemExit` is caught with stderr captured; the result is
  `Result(exit_code=usage, output=<what argparse printed>)`, `usage` defaulting to 2.
- Built on FastMCP 3 (`fastmcp>=3.4,<4`, `mcp<2`), so it composes with `mcp-arg-errors` and
  `mcp-result-wire` on the same server.

Interim form. After verb-cli 0.2 (subcommands from `{name: fn}`, positionals, `Literal` choices, shared
parameters) `verb-mcp` registers the same typed functions directly: the SDK derives the schema from the
signature, so there is no argv round trip and no `SystemExit`, and this package is retired.
