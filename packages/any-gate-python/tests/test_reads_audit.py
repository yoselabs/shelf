"""The reads map is a claim about what tests read; the audit fails it when a test's text says otherwise."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from any_gate_python import reads_audit

if TYPE_CHECKING:
    from pathlib import Path


def _member(repo: Path, name: str, deps: tuple[str, ...] = (), test: str = "") -> None:
    pkg = repo / "packages" / name
    (pkg / "tests").mkdir(parents=True)
    listed = ", ".join(f'"{d}>=0.1"' for d in deps)
    (pkg / "pyproject.toml").write_text(f'[project]\nname = "{name}"\ndependencies = [{listed}]\n')
    (pkg / "tests" / "test_x.py").write_text(test)


def _repo(tmp_path: Path, reads: str, **tests: str) -> Path:
    (tmp_path / "pyproject.toml").write_text(f"[tool.any-gate.python.reads]\n{reads}")
    for name, text in tests.items():
        _member(tmp_path, name, test=text)
    return tmp_path


def test_a_map_every_naming_test_is_covered_by_passes(tmp_path: Path) -> None:
    repo = _repo(tmp_path, '"ci.yaml" = ["a"]\n', a='open("ci.yaml")', b="print(1)")
    assert reads_audit.audit(repo) == []


def test_a_test_naming_a_mapped_file_its_package_is_not_mapped_for_fails(tmp_path: Path) -> None:
    repo = _repo(tmp_path, '"ci.yaml" = ["a"]\n', a="print(1)", b='Path("ci.yaml").read_text()')
    [problem] = reads_audit.audit(repo)
    assert "ci.yaml" in problem
    assert "packages/b/tests/test_x.py" in problem


def test_a_package_depending_on_a_mapped_one_is_covered_because_the_file_selects_it_anyway(tmp_path: Path) -> None:
    repo = _repo(tmp_path, '"ci.yaml" = ["a"]\n', a="", b='"ci.yaml"')
    (repo / "packages" / "b" / "pyproject.toml").write_text('[project]\nname = "b"\ndependencies = ["a>=0.1"]\n')
    assert reads_audit.audit(repo) == []


def test_a_glob_entry_is_read_through_the_files_it_matches_and_their_folders(tmp_path: Path) -> None:
    (tmp_path / ".cfg").mkdir()
    (tmp_path / ".cfg" / "one.toml").write_text("")
    repo = _repo(tmp_path, '".cfg/*" = ["a"]\n', a="", b='tmp / ".cfg" / "one.toml"', c='(root / ".cfg/one.toml")', d='x = ".cfg-other"')
    problems = reads_audit.audit(repo)
    flagged = {p.split("packages/")[1].split("/")[0] for p in problems}
    assert flagged == {"b", "c"}  # b names the folder; a name built from parts at run time would escape (the documented limit)


@pytest.mark.parametrize("text", ["Path(__file__).resolve().parents[3]", "Path(__file__).parent.parent.parent.parent"])
def test_a_test_that_finds_the_repo_root_needs_its_package_mapped_for_some_file(tmp_path: Path, text: str) -> None:
    repo = _repo(tmp_path, '"ci.yaml" = ["a"]\n', a="", b=text)
    [problem] = reads_audit.audit(repo)
    assert "'b'" in problem
    assert "parents[3]" in problem


def test_a_file_the_root_conftest_or_its_plugins_read_cannot_be_mapped(tmp_path: Path) -> None:
    repo = _repo(tmp_path, '"ci.yaml" = ["a"]\n', a="")
    (repo / "conftest.py").write_text('pytest_plugins = ["tools.fit"]\n')
    (repo / "tools").mkdir()
    (repo / "tools" / "fit.py").write_text('open("ci.yaml")')
    [problem] = reads_audit.audit(repo)
    assert "tools/fit.py" in problem
    assert "every suite" in problem


def test_a_reader_that_is_no_package_fails(tmp_path: Path) -> None:
    repo = _repo(tmp_path, '"ci.yaml" = ["ghost"]\n', a="")
    assert reads_audit.audit(repo) == ["ci.yaml: reader 'ghost' is not a package"]


# --- the repo's own tests: every file keyed, every top-level path it names covered by a pattern of its key ---


def _repo_tests(tmp_path: Path, keys: str, **tests: str) -> Path:
    (tmp_path / "pyproject.toml").write_text(f'[tool.any-gate.python]\nrepo-tests = "tests"\n[tool.any-gate.python.repo-reads]\n{keys}')
    (tmp_path / "tests").mkdir()
    for name in ("docs", "tools", "packages/p/src/p"):
        (tmp_path / name).mkdir(parents=True)
    for name, text in tests.items():
        (tmp_path / "tests" / name).write_text(text)
    return tmp_path


def test_a_repo_test_keyed_for_what_it_names_passes(tmp_path: Path) -> None:
    repo = _repo_tests(tmp_path, '"test_a.py" = ["docs/*", "tools/*"]\n', **{"test_a.py": 'ROOT / "docs"; open("tools/x.py")'})
    assert reads_audit.audit_repo_tests(repo) == []


def test_a_repo_test_no_key_names_is_reported(tmp_path: Path) -> None:
    repo = _repo_tests(tmp_path, '"test_a.py" = []\n', **{"test_a.py": "", "test_b.py": ""})
    assert reads_audit.audit_repo_tests(repo) == ["test_b.py is not keyed in [tool.any-gate.python.repo-reads]: it runs on every change"]


@pytest.mark.parametrize(
    ("text", "named"),
    [
        ('ROOT / "docs" / "adr"', "docs"),
        ("from tools.x import y", "tools"),
        ("import p", "packages"),
        ('"packages/a/tests/x.py"', "packages"),
    ],
)
def test_a_repo_test_naming_a_path_none_of_its_patterns_covers_is_reported(tmp_path: Path, text: str, named: str) -> None:
    repo = _repo_tests(tmp_path, '"test_a.py" = ["nothing/*"]\n', **{"test_a.py": text})
    problems = reads_audit.audit_repo_tests(repo)
    assert problems
    assert all(f"names {named!r}" in p for p in problems)


def test_a_star_key_covers_every_test_and_a_bang_pattern_counts_as_covered(tmp_path: Path) -> None:
    repo = _repo_tests(tmp_path, '"*" = ["docs/*"]\n"test_a.py" = ["!tools/*"]\n', **{"test_a.py": 'x = "docs"; y = "tools"'})
    assert reads_audit.audit_repo_tests(repo) == []


def test_a_package_folder_beside_src_needs_its_own_pattern(tmp_path: Path) -> None:
    repo = _repo_tests(tmp_path, '"test_a.py" = ["packages/*/src/*", "tests/*"]\n', **{"test_a.py": 'p / "packages" / "src"; q = "tests"'})
    [problem] = reads_audit.audit_repo_tests(repo)
    assert "packages/x/tests/x.py" in problem
