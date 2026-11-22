"""What the repo says about its own paths, read from `[tool.any-gate.python]` in the root `pyproject.toml`.

```toml
[tool.any-gate.python]
no-effect = ["docs/", "README.md"]    # paths no package test can observe
repo-tests = "tests"                   # whole-repo tests that always run (the fitness tests)

[tool.any-gate.python.gated]           # repo tests that run only when something they read changed
tests = ["test_onboard_*"]             # file-name globs under `repo-tests`
inputs = ["tools/onboard/", "justfile"]
[tool.any-gate.python.gated.reads]     # what one gated test reads beyond `inputs`
"test_onboard_beads.py" = ["packages/blueprint/src/blueprint/concerns/beads/backlog.py"]
```

A path entry is a file (`justfile`) or, with a trailing `/`, a directory prefix.
With no config every path outside `packages/` selects every package.
"""

from __future__ import annotations

import fnmatch
import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


def matches(path: str, entries: tuple[str, ...]) -> bool:
    """`path` is an entry, or below a directory entry (one ending in `/`)."""
    return any(path == e or (e.endswith("/") and path.startswith(e)) for e in entries)


@dataclass(frozen=True)
class Rules:
    no_effect: tuple[str, ...] = ()
    repo_tests: str = ""
    gated_tests: tuple[str, ...] = ()
    gated_inputs: tuple[str, ...] = ()
    gated_reads: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @classmethod
    def load(cls, repo: Path) -> Rules:
        manifest = repo / "pyproject.toml"
        data: dict[str, Any] = tomllib.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
        section: dict[str, Any] = data.get("tool", {}).get("any-gate", {}).get("python", {})
        gated: dict[str, Any] = section.get("gated", {})
        return cls(
            no_effect=tuple(section.get("no-effect", ())),
            repo_tests=section.get("repo-tests", ""),
            gated_tests=tuple(gated.get("tests", ())),
            gated_inputs=tuple(gated.get("inputs", ())),
            gated_reads={name: tuple(paths) for name, paths in gated.get("reads", {}).items()},
        )

    def observable(self, path: str) -> bool:
        """False when no package test can see a change to `path`."""
        return not matches(path, self.no_effect)

    def is_gated(self, name: str) -> bool:
        return any(fnmatch.fnmatchcase(name, g) for g in self.gated_tests)
