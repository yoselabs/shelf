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

[tool.any-gate.python.repo-reads]      # what each repo test file reads (fnmatch on the file name -> path globs); `*` applies to all
"test_arch_*.py" = ["packages/*/src/*"]
"*" = ["conftest.py", "pyproject.toml"]

[tool.any-gate.python.reads]           # a root file -> the packages whose tests read it (fnmatch, `*` crosses `/`)
".pre-commit-config.yaml" = ["blueprint"]
".blueprint/*" = ["blueprint", "any-gate"]
```

A path entry is a file (`justfile`) or, with a trailing `/`, a directory prefix.
With no config every path outside `packages/` selects every package. A root file named in `reads` selects only the packages listed
(and, through the graph, their dependents); an empty list says no suite reads it. A name that is no package selects every package.
The reads map is a claim about the tests: `reads_audit` fails the gate when a test names a mapped file its package is not mapped for.
"""

from __future__ import annotations

import fnmatch
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SKIPPED_DIRS = frozenset(
    {".git", ".venv", ".pytest_cache", ".ruff_cache", ".hypothesis", ".import_linter_cache", "node_modules", "__pycache__"}
)


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
    reads: dict[str, tuple[str, ...]] = field(default_factory=dict)
    repo_reads: dict[str, tuple[str, ...]] = field(default_factory=dict)

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
            reads={pattern: tuple(names) for pattern, names in section.get("reads", {}).items()},
            repo_reads={name: tuple(paths) for name, paths in section.get("repo-reads", {}).items()},
        )

    def observable(self, path: str) -> bool:
        """False when no package test can see a change to `path`."""
        return not matches(path, self.no_effect)

    def keyed(self, name: str) -> bool:
        """Whether a `repo-reads` entry (other than `*`) names the repo test file `name`: an unkeyed test runs on every change."""
        return any(key != "*" and fnmatch.fnmatchcase(name, key) for key in self.repo_reads)

    # A pattern written `!path/*` says the test names that path without reading it (a skip list): the audit counts it as covered,
    # a change to it does not run the test.
    def reads_changed(self, name: str, own: str, changed: list[str]) -> bool:
        """Whether a keyed repo test must run: it changed, or a path it (or every keyed test, `*`) reads did."""
        patterns = [
            p
            for key, paths in self.repo_reads.items()
            if key == "*" or fnmatch.fnmatchcase(name, key)
            for p in paths
            if not p.startswith("!")
        ]
        return any(path == own or any(_glob(path, p) for p in patterns) for path in changed)

    def star_covers(self, path: str) -> bool:
        """Whether a `*` repo-reads entry names `path`: a change to it runs the keyed tests, which is the whole claim about a helper."""
        return any(_glob(path, p) for p in self.repo_reads.get("*", ()) if not p.startswith("!"))

    def is_gated(self, name: str) -> bool:
        return any(fnmatch.fnmatchcase(name, g) for g in self.gated_tests)

    def readers(self, path: str) -> set[str] | None:
        """The packages whose tests read root `path`, the union over every entry it matches; None when no entry names it."""
        hit = [names for pattern, names in self.reads.items() if _glob(path, pattern)]
        return {n for names in hit for n in names} if hit else None

    def read_files(self, repo: Path, package: str) -> list[str]:
        """The root files `package`'s tests read, as sorted repo-relative paths: what its key must hash."""
        found: set[str] = set()
        for pattern, names in self.reads.items():
            if package not in names:
                continue
            if not any(c in pattern for c in "*?["):
                if (repo / pattern.rstrip("/")).is_file():
                    found.add(pattern)
                elif pattern.endswith("/"):
                    found.update(_walk(repo, pattern.rstrip("/"), pattern))
                continue
            literal = pattern.split("*")[0].split("?")[0].split("[")[0]
            found.update(_walk(repo, literal.rpartition("/")[0], pattern))
        return sorted(found)


def _glob(path: str, pattern: str) -> bool:
    return path.startswith(pattern) if pattern.endswith("/") else fnmatch.fnmatchcase(path, pattern)


def _walk(repo: Path, base: str, pattern: str) -> list[str]:
    """The files under `base` (repo-relative) `pattern` matches; never the virtualenv, git or cache folders."""
    start = repo / base if base else repo
    if not start.is_dir():
        return []
    found: list[str] = []
    for folder, dirs, names in os.walk(start):
        dirs[:] = sorted(d for d in dirs if d not in SKIPPED_DIRS)
        found += [rel for n in sorted(names) if _glob(rel := (Path(folder) / n).relative_to(repo).as_posix(), pattern)]
    return found
