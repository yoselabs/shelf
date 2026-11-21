"""The API-surface tool: planted before/after packages in a tmp repo with two tags, the breaking-change list and the learning cost."""

import subprocess
import textwrap
from pathlib import Path

import pytest

from tools import api_surface

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false"]


def run(cwd: Path, *args: str) -> None:
    subprocess.run([*GIT, *args], cwd=cwd, check=True, capture_output=True)


def release(repo: Path, tag: str, files: dict[str, str]) -> None:
    """Replace `packages/demo` by `files` (paths relative to it), commit and tag."""
    root = repo / "packages" / "demo"
    for old in sorted(root.rglob("*"), reverse=True) if root.exists() else []:
        old.unlink() if old.is_file() else old.rmdir()
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")
    run(repo, "add", "-A")
    run(repo, "commit", "-q", "--allow-empty", "-m", tag)
    run(repo, "tag", tag)


def init(*versions: dict[str, str], tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    for number, files in enumerate(versions):
        release(repo, f"demo-v{number}", files)
    return repo


def pkg(source: str, **more: str) -> dict[str, str]:
    return {"src/demo/__init__.py": source, **{f"src/demo/{name}.py": text for name, text in more.items()}}


def report(tmp_path: Path, before: dict[str, str], after: dict[str, str]) -> list[str]:
    repo = init(before, after, tmp_path=tmp_path)
    return api_surface.diff_report(repo, "demo", "demo-v0", "demo-v1")


def test_removed_and_added_names_follow_all(tmp_path):
    before = pkg('__all__ = ["gone", "kept"]\ndef gone(): ...\ndef kept(): ...\ndef _private(): ...\n')
    after = pkg('__all__ = ["kept", "fresh"]\ndef kept(): ...\ndef fresh(a, *, b=1) -> int: ...\ndef gone(): ...\n')
    assert report(tmp_path, before, after) == [
        "REMOVED  BREAKING  gone()",
        "ADDED    fresh(a, *, b=...) -> int",
        "1 breaking",
    ]


def test_without_all_the_public_module_level_names_count(tmp_path):
    before = pkg("def a(): ...\ndef _b(): ...\nLIMIT = 3\n")
    after = pkg("def a(): ...\ndef _b(x): ...\ndef c(): ...\n")
    assert report(tmp_path, before, after) == ["REMOVED  BREAKING  LIMIT = 3", "ADDED    c()", "1 breaking"]


def test_signature_changes_a_caller_must_adapt_to_are_breaking(tmp_path):
    before = pkg('__all__ = ["f", "g", "h", "k"]\ndef f(a, b=1): ...\ndef g(a: int) -> int: ...\ndef h(a, b=None): ...\ndef k(a, b): ...\n')
    after = pkg('__all__ = ["f", "g", "h", "k"]\ndef f(a, c, b=1): ...\ndef g(a: str) -> str: ...\ndef h(a, *, b): ...\ndef k(b, a): ...\n')
    assert report(tmp_path, before, after) == [
        "CHANGED  BREAKING  f: new required param: c",
        "CHANGED  BREAKING  g: param a: int -> str; returns int -> str",
        "CHANGED  BREAKING  h: param b: pos-or-kw -> kw; param b: now required",
        "CHANGED  BREAKING  k: positional order changed",
        "4 breaking",
    ]


def test_compatible_changes_are_not_marked(tmp_path):
    before = pkg('__all__ = ["f"]\ndef f(a: int, *, b): ...\n')
    after = pkg('__all__ = ["f"]\ndef f(a: str, *, b, c=0): ...\n')
    assert report(tmp_path, before, after) == [
        "CHANGED  f: new param: c; param a: int -> str",
        "0 breaking",
    ]


def test_a_removed_parameter_and_a_new_typed_exception_are_breaking(tmp_path):
    before = pkg('__all__ = ["f"]\nclass Boom(Exception): ...\ndef f(a, old): raise ValueError()\n')
    after = pkg(
        '__all__ = ["f", "Boom"]\nclass Boom(Exception): ...\ndef f(a):\n    def inner():\n        raise Boom\n    raise Boom("x")\n'
    )
    assert report(tmp_path, before, after) == [
        "CHANGED  BREAKING  f: param removed: old; new raises Boom",
        "ADDED    class Boom(Exception)",
        "1 breaking",
    ]


def test_dataclass_fields_and_methods(tmp_path):
    before = pkg(
        "from dataclasses import dataclass\n"
        '__all__ = ["R", "S"]\n'
        "@dataclass\nclass R:\n    a: int\n    b: str = ''\n    c: int = 0\n"
        "class S:\n    def go(self, x): ...\n    def stop(self): ...\n"
    )
    after = pkg(
        "from dataclasses import dataclass\n"
        '__all__ = ["R", "S"]\n'
        "@dataclass\nclass R:\n    a: int\n    c: int\n    d: int\n"
        "class S:\n    def go(self, x, y): ...\n    @property\n    def size(self) -> int: ...\n"
    )
    assert report(tmp_path, before, after) == [
        "REMOVED  BREAKING  R.b: str = ...",
        "REMOVED  BREAKING  S.stop()",
        "CHANGED  BREAKING  R.c: field now required",
        "CHANGED  BREAKING  S.go: new required param: y",
        "ADDED    BREAKING  R.d: int",
        "ADDED    property S.size() -> int",
        "5 breaking",
    ]


def test_names_reexported_from_a_submodule_are_resolved(tmp_path):
    before = pkg('from demo.impl import f\n__all__ = ["f"]\n', impl="def f(a): ...\n")
    after = pkg('from .impl import f\n__all__ = ["f"]\n', impl="def f(a, b): ...\n")
    assert report(tmp_path, before, after) == ["CHANGED  BREAKING  f: new required param: b", "1 breaking"]


def test_no_change_is_said(tmp_path):
    same = pkg('__all__ = ["f"]\ndef f(a): ...\n')
    assert report(tmp_path, same, same) == ["no public API changes"]


def test_a_missing_tag_or_package_is_an_error_not_a_crash(tmp_path, capsys):
    repo = init(pkg("def a(): ...\n"), tmp_path=tmp_path)
    assert api_surface.main(["--repo", str(repo), "diff", "demo", "demo-v0", "nope"]) == 2
    assert "nope" in capsys.readouterr().err
    assert api_surface.main(["--repo", str(repo), "diff", "other", "demo-v0", "demo-v0"]) == 2


def test_cli_diff_prints_a_header_and_the_lines(tmp_path, capsys):
    repo = init(pkg("def a(): ...\n"), pkg("def a(x): ...\n"), tmp_path=tmp_path)
    assert api_surface.main(["--repo", str(repo), "diff", "demo", "demo-v0", "demo-v1"]) == 0
    assert capsys.readouterr().out.splitlines() == ["demo: demo-v0 -> demo-v1", "CHANGED  BREAKING  a: new required param: x", "1 breaking"]


def test_learning_cost_counts_readme_signatures_and_docstring_first_lines(tmp_path, capsys):
    small = {"README.md": "one two three four five\n", **pkg('__all__ = ["f"]\ndef f(a): ...\n')}
    big = {"README.md": "word " * 100, **pkg('__all__ = ["f"]\ndef f(a, b):\n    """Does a thing.\n\n    More.\n    """\n')}
    repo = init(small, big, tmp_path=tmp_path)
    assert api_surface.main(["--repo", str(repo), "learning-cost", "--rev", "demo-v0"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].split() == ["package", "tokens", "readme", "api", "names"]
    assert out[1].split() == ["demo", "9", "7", "2", "1"]  # ceil(5 * 1.3) + ceil(1 * 1.3)
    assert "words * 1.3" in out[-1]
    assert api_surface.main(["--repo", str(repo), "learning-cost", "--rev", "demo-v1"]) == 0
    row = capsys.readouterr().out.splitlines()[1].split()
    assert row[0:2] == ["demo", "137"]  # ceil(100 * 1.3) + ceil((2 + 3) * 1.3): README, `f(a, b)`, "Does a thing."


def test_learning_cost_table_is_sorted_largest_first(tmp_path, capsys):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    for name, words in (("aa", 5), ("bb", 50), ("cc", 20)):
        path = repo / "packages" / name
        (path / "src" / name).mkdir(parents=True)
        (path / "src" / name / "__init__.py").write_text("")
        (path / "README.md").write_text("w " * words)
    run(repo, "add", "-A")
    run(repo, "commit", "-qm", "x")
    assert api_surface.main(["--repo", str(repo), "learning-cost"]) == 0
    assert [line.split()[0] for line in capsys.readouterr().out.splitlines()[1:4]] == ["bb", "cc", "aa"]


@pytest.mark.parametrize("argv", [[], ["diff", "demo", "a"]])
def test_bad_usage_exits_two(argv):
    with pytest.raises(SystemExit) as raised:
        api_surface.main(argv)
    assert raised.value.code == 2


def test_a_field_annotation_change_is_breaking_like_a_return_type(tmp_path):
    head = "from typing import NamedTuple\n__all__ = ['R']\n"
    before = pkg(head + "class R(NamedTuple):\n    out: str\n")
    after = pkg(head + "class R(NamedTuple):\n    out: bytes\n")
    assert report(tmp_path, before, after) == ["CHANGED  BREAKING  R.out: annotation: str -> bytes", "1 breaking"]
