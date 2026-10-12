# verb-cli

**Stop hand-writing argparse for a function that already says what it takes.** A
pydantic-annotated signature becomes CLI flags, and the parsed flags become its keyword
arguments.

```python
from typing import Annotated
from pydantic import Field
import verb_cli as vc

async def read(type_: Annotated[str, Field(alias="type", description="the kind")], id_: Annotated[str, Field(alias="id")],
               *, dry_run: bool = False, frontmatter: dict | None = None, limit: int = 8) -> ...: ...

specs = vc.flags_of(read)            # [FlagSpec(dest='type_', flag='--type', ...), ...]
vc.to_argparse(parser, specs)        # --type --id --dry-run/--no-dry-run --frontmatter --limit
kwargs = vc.kwargs_of(parser.parse_args(argv), specs)
await read(**kwargs)
```

## Rules

- One flag per parameter; `self`, `*args` and `**kwargs` are skipped. `dest` is the
  parameter's own name, so the function is called by its real signature.
- The flag is `Annotated[..., Field(alias=...)]`'s alias when present, else the parameter
  name, `_` → `-` (`type_` → `--type`). `Field(description=...)` is the help; without one the help is a type label (`text`,
  `integer`, `number`, `path`, `true or false`, `JSON object`, `JSON array`, `JSON value`).
- `T | None` is `T`. Required is "has no default".
- `bool` → a paired `--flag/--no-flag`. `int`, `float`, `Path` are converted; `str` and
  any other scalar stay text.
- Anything else — `list`, `dict`, a `Literal`, a model — is **one JSON flag**. Left out, it
  is left out of the call, so the function's own default applies (a default is never decoded
  as JSON). Given, it is decoded; a type with `model_validate` (a pydantic model) is
  validated. Invalid JSON raises `FlagJsonError` (a `VerbCliError`) naming the flag.

Metadata is read by duck typing (`alias`, `description`, `model_validate`): stdlib only,
pydantic optional.

## Testing the --help tree

`verb_cli.testing.assert_help_tree(parser)` walks `--help` on the parser and every subcommand
(exit 0, a description between usage and arguments, no option or positional without help, every
subcommand listed with text). A subparser added with `help=None` is left out of argparse's listing,
so give `add_parser` both `help=` and `description=` (ADR 0025). Stdlib only.
