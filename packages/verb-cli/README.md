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
  name, `_` → `-` (`type_` → `--type`). `Field(description=...)` is the help.
- `T | None` is `T`. Required is "has no default".
- `bool` → a paired `--flag/--no-flag`. `int`, `float`, `Path` are converted; `str` and
  any other scalar stay text.
- Anything else — `list`, `dict`, a `Literal`, a model — is **one JSON flag**. Left out, it
  is left out of the call, so the function's own default applies (a default is never decoded
  as JSON). Given, it is decoded; a type with `model_validate` (a pydantic model) is
  validated. Invalid JSON raises `FlagJsonError` (a `VerbCliError`) naming the flag.

Metadata is read by duck typing (`alias`, `description`, `model_validate`): stdlib only,
pydantic optional.
