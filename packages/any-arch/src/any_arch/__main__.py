"""`python -m any_arch <test file>...`: print the debt report of every Rule a test module defines at its top level."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from any_arch.debt import debt_text
from any_arch.rule import Rule


def main(paths: list[str]) -> int:
    rules: list[Rule] = []
    for path in paths:
        spec = importlib.util.spec_from_file_location(Path(path).stem, path)
        if spec is None or spec.loader is None:
            message = f"cannot load {path}"
            raise SystemExit(message)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rules.extend(value for value in vars(module).values() if isinstance(value, Rule))
    print(debt_text(*rules))  # noqa: T201 -- this command's whole output
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
