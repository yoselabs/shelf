"""argparse-mcp: the subcommands of an argparse parser as FastMCP tools.

``tools_from_parser(parser, run)`` returns one tool per subcommand. The schema comes from the
subcommand's options, positionals and choices; the parser's own (global) options are inputs of every
tool. A call rebuilds argv and hands it to your ``run(argv) -> (exit_code, lines)`` in this process, so
the CLI and the tools are one operation. ``SystemExit`` from argparse is caught and returned as a usage
result (exit code ``usage``, default 2) carrying what argparse printed.

Interim form: when verb-cli can generate the parser from typed functions, a verb-mcp registering those
same functions supersedes this package, and no argv round trip remains.
"""

from argparse_mcp.tools import Result, Run, tools_from_parser

__all__ = ["Result", "Run", "tools_from_parser"]
