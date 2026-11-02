"""Consumers match paths using the extracted dialect, without oracle drift."""

from __future__ import annotations

import random
import re
from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest

from any_path_glob import Glob, GlobError


def reference_glob_re(glob: str) -> re.Pattern[str]:
    out, i, depth = "", 0, 0
    while i < len(glob):
        c = glob[i]
        if glob.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
            continue
        if c == "*":
            out, i = (
                out + (".*" if glob.startswith("**", i) else "[^/]*"),
                i + (2 if glob.startswith("**", i) else 1),
            )
            continue
        if c == "{":
            out, depth = out + "(?:", depth + 1
        elif c == "}" and depth:
            out, depth = out + ")", depth - 1
        elif c == "," and depth:
            out += "|"
        else:
            out += "[^/]" if c == "?" else re.escape(c)
        i += 1
    return re.compile(out + r"\Z")


@pytest.mark.parametrize(
    "pattern",
    [
        "",
        "*",
        "?",
        "**",
        "**/",
        "**/*.py",
        "src/*",
        "src/?",
        "{a,b}",
        "{a,{b,c}}",
        "a,b",
        "a}",
        "[a-z]",
        "!a",
        "{,a}",
        "a/**/b",
    ],
)
@pytest.mark.parametrize("path", ["", "a", "a/b", "src/x.py", "a/b/c.py"])
def test_differential_table(pattern: str, path: str) -> None:
    # 16 patterns x 5 paths = 80 fixed pairs, including empty inputs and nested braces.
    assert Glob(pattern).matches(path) == bool(reference_glob_re(pattern).match(path))


def test_seeded_differential_sweep() -> None:
    rng = random.Random(20261101)
    atoms = ["a", "b", "/", "*", "?", "**", "**/", "{a,b}", "{,{a,b}}", "}", ",", ".", "[a-z]", "\\", "\n", "é"]
    for _ in range(3000):
        pattern = "".join(rng.choices(atoms, k=rng.randrange(9)))
        compiled = reference_glob_re(pattern)
        glob = Glob(pattern)
        for path in ("".join(rng.choices("ab/.,}\\\né", k=rng.randrange(14))), pattern, "", "a/b"):
            assert glob.matches(path) == bool(compiled.match(path)), (pattern, path)


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("**/x", "x", True),
        ("**/x", "a/b/x", True),
        ("a/**/b", "a/b", True),
        ("**", "a/b", True),
        ("*", "a/b", False),
        ("?", "/", False),
        ("?", "é", True),
        ("*", "", True),
        ("{a,{b,c}}", "c", True),
        ("a,b", "a,b", True),
        ("a}", "a}", True),
        ("[a-z]", "a", False),
        ("[a-z]", "[a-z]", True),
        ("!a", "!a", True),
        ("a.b", "axb", False),
        ("README", "readme", False),
        ("a", "ba", False),
        ("a", "a\n", False),
        ("", "", True),
        ("", "a", False),
        ("**", "\n", False),
        ("*", "\n", True),
    ],
)
def test_dialect_rules(pattern: str, path: str, *, expected: bool) -> None:
    assert Glob(pattern).matches(path) is expected


@pytest.mark.parametrize("pattern", ["{", "a{b", "{a,{b,c}", "}{"])
def test_unclosed_brace_is_a_glob_error(pattern: str) -> None:
    with pytest.raises(GlobError, match="unclosed"):
        Glob(pattern)


def test_glob_is_frozen_and_retains_its_compiled_pattern() -> None:
    glob = Glob("src/*.py")
    assert glob.pattern == "src/*.py"
    assert glob.regex.match("src/x.py") is not None
    with pytest.raises(FrozenInstanceError):
        glob.__setattr__("pattern", "other")


def test_compilation_is_cached_across_instances_and_matches() -> None:
    with patch("re.compile", wraps=re.compile) as compile_pattern:
        first = Glob("cache-test-unique/**/*.py")
        second = Glob(first.pattern)
        for path in ["cache-test-unique/x.py", "cache-test-unique/a/b.py"]:
            assert first.matches(path)
            assert second.matches(path)
        assert first.regex is second.regex
        compile_pattern.assert_called_once()
