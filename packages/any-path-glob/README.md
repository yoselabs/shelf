# any-path-glob

Stop copying the glob dialect for repo-relative paths. Stdlib only.

```python
from any_path_glob import Glob, GlobSet

python = Glob("**/*.py")
assert python.matches("main.py")
assert python.matches("src/app/main.py")
assert python.pattern == "**/*.py"
assert python.regex.match("src/app/main.py")

inputs = GlobSet([python, "docs/**", "**/*.py"])
assert len(inputs) == 2
assert inputs.first("main.py") is python
assert "docs/guide.md" in inputs
assert inputs.filter(["main.py", "image.png", "docs/guide.md"]) == ["main.py", "docs/guide.md"]
assert [glob.pattern for glob in inputs] == ["**/*.py", "docs/**"]
```

## Rules

- Matches cover the whole path, case sensitively, using `/` as the separator.
- `**/` crosses zero or more folders; bare `**` crosses `/` too.
- `*` matches zero or more characters within a segment; `?` matches one.
- `{a,b}` matches either alternative. Braces nest; empty alternatives work.
- A comma outside braces is literal. Everything else is literal, including an
  unmatched `}`. An unclosed `{` raises `GlobError`, a `ValueError` subclass.
- An empty pattern matches only the empty path. Dotfiles get no special treatment.
- Historical regex behavior is preserved: `**` and the folder part of `**/`
  do not cross newlines, while `*` and `?` can match a newline inside a segment.
- `Glob` is frozen and compiles once on construction. Compilation is cached
  across instances (512 patterns); each instance retains its compiled regex.
- `GlobSet` accepts an iterable of strings or `Glob` objects and deduplicates by
  pattern, keeping the first object and declaration order. `matches` and membership
  mean any-of; `first` returns that first matching `Glob` or `None`. `filter`
  accepts an iterable and returns a list preserving path order and duplicates.
  An empty set matches nothing. Iteration yields `Glob` objects.

## What it does not do

This is not gitignore: no negation, no `[a-z]` character classes, no filesystem
walk, no path normalization, and no case folding. Pass repo-relative path strings
with `/` separators; backslashes are literal characters.

The candidate contract is in [CONTRACT.md](CONTRACT.md). Extracted from lifesim's
gate inputs and the task-loop matcher; consumers adopt separately.
