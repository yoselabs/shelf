"""The extracted repo-relative glob dialect."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache


class GlobError(ValueError):
    """A glob contains an unclosed opening brace."""


@lru_cache(maxsize=512)
def _compile(pattern: str) -> re.Pattern[str]:
    parts: list[str] = []
    index, depth = 0, 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
            continue
        if char == "*":
            double = pattern.startswith("**", index)
            parts.append(".*" if double else "[^/]*")
            index += 2 if double else 1
            continue
        if char == "{":
            parts.append("(?:")
            depth += 1
        elif char == "}" and depth:
            parts.append(")")
            depth -= 1
        elif char == "," and depth:
            parts.append("|")
        else:
            parts.append("[^/]" if char == "?" else re.escape(char))
        index += 1
    if depth:
        message = f"unclosed opening brace in glob: {pattern!r}"
        raise GlobError(message)
    return re.compile("".join(parts) + r"\Z")


@dataclass(frozen=True)
class Glob:
    """An immutable pattern holding its cached, case-sensitive compiled regex."""

    pattern: str
    regex: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "regex", _compile(self.pattern))

    def matches(self, path: str) -> bool:
        return self.regex.match(path) is not None
