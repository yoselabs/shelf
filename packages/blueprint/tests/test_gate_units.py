"""Test units for a non-workspace repo: keys that follow what a unit reaches, cached coverage, the shadowed-recipe checkpoint."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from blueprint import gate_test, gate_units, unit_runner
from blueprint.__main__ import main
from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from pathlib import Path

    from blueprint.testing import Repo

_PYPROJECT = """\
[project]
name = "app"
version = "0"

[tool.blueprint.test]
coverage = "coverage"
floor = 50

[tool.blueprint.test.units.core]
paths = ["tests/core"]

[tool.blueprint.test.units.ui]
paths = ["tests/ui"]
reads = ["src/app/ui/*.js"]

[tool.coverage.run]
source = ["src/app"]
"""


def _app(repo: Repo) -> None:
    repo.write("pyproject.toml", _PYPROJECT)
    repo.write("src/app/__init__.py", "")
    repo.write("src/app/core.py", "def add(a, b):\n    return a + b\n")
    repo.write("src/app/ui/__init__.py", "")
    repo.write("src/app/ui/view.py", "from app.core import add\n\ndef show():\n    return add(1, 1)\n")
    repo.write("src/app/ui/view.js", "export const x = 1\n")
    repo.write("tests/core/test_core.py", "from app.core import add\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    repo.write("tests/ui/test_view.py", "from app.ui import view\n\ndef test_show():\n    assert view.show() == 2\n")
    repo.write("conftest.py", "import sys\nsys.path.insert(0, 'src')\n")


def _keys(repo: Repo) -> dict[str, str]:
    config = gate_units.load(repo.root)
    assert config is not None
    return {u.name: gate_units.key(repo.root, u) for u in config.units}


def test_a_repo_with_no_declared_units_has_none(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    assert gate_units.load(repo.root) is None


@pytest.mark.parametrize("paths", ['path = ["tests/core"]', "paths = []", 'paths = "tests/core"'])
def test_gate_test_refuses_invalid_unit_paths(repo: Repo, capsys: pytest.CaptureFixture[str], paths: str) -> None:
    repo.write("pyproject.toml", f"[tool.blueprint.test.units.broken]\n{paths}\n")
    assert main(["gate", "test", "--repo", str(repo.root)]) == 2
    assert "broken" in capsys.readouterr().err


@pytest.mark.parametrize("root", ["tests", "scenarios"])
def test_gate_test_refuses_test_folders_outside_units(repo: Repo, capsys: pytest.CaptureFixture[str], root: str) -> None:
    _app(repo)
    repo.write("pyproject.toml", _PYPROJECT + f'\n[tool.pytest.ini_options]\ntestpaths = ["{root}"]\n')
    repo.write(f"{root}/forgotten/example_test.py", "def test_forgotten():\n    assert False\n")
    assert main(["gate", "test", "--repo", str(repo.root)]) == 2
    assert f"{root}/forgotten" in capsys.readouterr().err


@pytest.mark.parametrize("file", ["pytest.ini", ".coveragerc", "setup.cfg", "tox.ini", ".python-version", "tests/__init__.py"])
def test_test_configuration_and_parent_initializers_invalidate_keys(repo: Repo, file: str) -> None:
    _app(repo)
    repo.write(file, "# before\n")
    before = _keys(repo)
    repo.write(file, "# after\n")
    assert all(_keys(repo)[name] != before[name] for name in before)


def test_filtered_run_cannot_supply_a_plain_runs_coverage(repo: Repo, tmp_path: Path) -> None:
    _app(repo)
    repo.write("tests/core/test_core.py", "def test_ok():\n    assert True\n\ndef test_bad():\n    assert False\n")

    def filtered_go(args: str) -> int:
        return gate_test.run(
            repo.root,
            whole=False,
            receipts=tmp_path / "r",
            lease_root=tmp_path / "leases",
            cache=tmp_path / "cache",
            env=repo.env,
            pytest_args=args,
        )

    assert filtered_go("--deselect=tests/core/test_core.py::test_bad") == 0
    assert not list((tmp_path / "cache").glob("*.cov"))
    assert filtered_go("") != 0


@pytest.mark.parametrize(
    ("setting", "attribute", "expected"),
    [
        ('pytest-args = ["-n", "auto", "--dist", "loadgroup", "-q"]', "pytest_args", ("-n", "auto", "--dist", "loadgroup", "-q")),
        ('env = { COVERAGE_CORE = "sysmon" }', "env", {"COVERAGE_CORE": "sysmon"}),
        ('marks = "not slow"', "marks", "not slow"),
        ('pytest-args = "-q"', "pytest_args", ()),
        ('pytest-args = ["-q", 1]', "pytest_args", ()),
        ('env = "wrong"', "env", {}),
        ("env = { COUNT = 1 }", "env", {}),
        ('marks = ["slow"]', "marks", ""),
    ],
)
def test_test_settings_load_valid_values_and_ignore_wrong_types(repo: Repo, setting: str, attribute: str, expected: object) -> None:
    _app(repo)
    repo.write("pyproject.toml", _PYPROJECT.replace("floor = 50", "floor = 50\n" + setting))
    config = gate_units.load(repo.root)
    assert config is not None
    assert config.coverage == "coverage"
    assert config.floor == 50
    assert len(config.units) == 2
    assert getattr(config, attribute) == expected


@pytest.mark.parametrize("setting", ['pytest-args = ["-q"]', 'env = { COVERAGE_CORE = "sysmon" }', 'marks = "not slow"'])
def test_test_settings_change_every_units_key(repo: Repo, setting: str) -> None:
    _app(repo)
    before = _keys(repo)
    repo.write("pyproject.toml", _PYPROJECT.replace("floor = 50", "floor = 50\n" + setting))
    after = _keys(repo)
    assert all(after[name] != before[name] for name in before)


@pytest.mark.parametrize("mode", ["coverage", "pytest-cov", ""])
def test_test_processes_honor_configured_args_marks_and_environment(repo: Repo, tmp_path: Path, mode: str) -> None:
    _app(repo)
    settings = '\npytest-args = ["-q", "--override-ini=markers=skipme: excluded"]\nmarks = "not skipme"'
    settings += '\nenv = { BLUEPRINT_TEST_VALUE = "configured", COVERAGE_FILE = "wrong.cov" }'
    manifest = _PYPROJECT.replace('coverage = "coverage"', f'coverage = "{mode}"').replace("floor = 50", "floor = 50" + settings)
    repo.write("pyproject.toml", manifest)
    repo.write(
        "tests/core/test_core.py",
        "import os\nimport pytest\nfrom app.core import add\n\n"
        "def test_environment():\n    assert os.environ['BLUEPRINT_TEST_VALUE'] == 'configured'\n    assert add(1, 2) == 3\n\n"
        "@pytest.mark.skipme\ndef test_excluded():\n    assert False\n",
    )
    assert (
        gate_test.run(
            repo.root, whole=False, receipts=tmp_path / "r.json", lease_root=tmp_path / "leases", cache=tmp_path / "cache", env=repo.env
        )
        == 0
    )
    assert not (repo.root / "wrong.cov").exists()


def test_noncoverage_command_puts_configured_arguments_before_cli_arguments(repo: Repo) -> None:
    _app(repo)
    manifest = _PYPROJECT.replace('coverage = "coverage"', 'pytest-args = ["-q"]\nmarks = "not slow"')
    repo.write("pyproject.toml", manifest)
    _, command = gate_test.commands(repo.root, whole=False, receipts=None, lease_root=None, pytest_args="-v")
    assert command[-1] == "--pytest-args=-q -m 'not slow' -v"


def test_the_plan_is_one_line_per_unit_path_with_the_units_key(repo: Repo) -> None:
    _app(repo)
    config = gate_units.load(repo.root)
    assert config is not None
    keys = _keys(repo)
    assert gate_units.plan(repo.root, config) == f"tests/core\t{keys['core']}\ntests/ui\t{keys['ui']}\n"


def test_a_change_to_shared_code_reruns_every_unit_that_reaches_it(repo: Repo) -> None:
    _app(repo)
    before = _keys(repo)
    repo.write("src/app/core.py", "def add(a, b):\n    return b + a\n")
    after = _keys(repo)
    assert after["core"] != before["core"]
    assert after["ui"] != before["ui"]  # ui imports core through view


def test_a_ui_only_change_reruns_only_the_ui_unit(repo: Repo) -> None:
    _app(repo)
    before = _keys(repo)
    repo.write("src/app/ui/view.py", "from app.core import add\n\ndef show():\n    return add(2, 0)\n")
    after = _keys(repo)
    assert after["ui"] != before["ui"]
    assert after["core"] == before["core"]


def test_a_file_named_in_reads_changes_the_key_though_no_import_names_it(repo: Repo) -> None:
    _app(repo)
    before = _keys(repo)
    repo.write("src/app/ui/view.js", "export const x = 2\n")
    assert _keys(repo)["ui"] != before["ui"]
    assert _keys(repo)["core"] == before["core"]


def test_the_lock_and_the_dependencies_change_every_key_but_lint_config_does_not(repo: Repo) -> None:
    _app(repo)
    before = _keys(repo)
    repo.write("pyproject.toml", _PYPROJECT + "\n[tool.ruff]\nline-length = 99\n")
    assert _keys(repo) == before
    repo.write("uv.lock", "version = 1\n")
    assert all(_keys(repo)[n] != before[n] for n in before)


def test_a_unit_with_cached_coverage_is_left_out_and_one_without_runs_keyless(repo: Repo) -> None:
    _app(repo)
    config = gate_units.load(repo.root)
    assert config is not None
    assert gate_units.plan(repo.root, config, cached={f"core:{_keys(repo)['core']}"}) == "tests/ui\t\n"


def test_the_cache_lives_in_the_shared_git_directory_one_folder_per_checkout(repo: Repo) -> None:
    where = gate_test.cache_dir(repo.root)
    assert where.parent == repo.root / ".git" / "gate-coverage"
    assert where.name != "gate-coverage"


def test_units_with_coverage_run_through_the_unit_runner(repo: Repo) -> None:
    _app(repo)
    _, test = gate_test.commands(repo.root, whole=False, receipts=None, lease_root=None, pytest_args="", cache=repo.root / "c")
    assert test[test.index("--") + 1 :][1:3] == ["-m", "blueprint.unit_runner"]


def test_a_green_run_caches_each_units_data_and_combines_it_whole_repo(repo: Repo, tmp_path: Path) -> None:
    _app(repo)
    config = gate_units.load(repo.root)
    assert config is not None
    cache = tmp_path / "cache"
    assert unit_runner.run_units(repo.root, cache, config, ["tests/core", "tests/ui"], [], marks=True) == 0
    assert unit_runner.cached(cache, config, _keys(repo)) == {f"{n}:{k}" for n, k in _keys(repo).items()}
    assert unit_runner.combine(repo.root, cache, config) == 0


def test_a_skipped_unit_still_counts_toward_the_floor(repo: Repo, tmp_path: Path) -> None:
    _app(repo)
    config = gate_units.load(repo.root)
    assert config is not None
    cache = tmp_path / "cache"
    assert unit_runner.run_units(repo.root, cache, config, ["tests/core", "tests/ui"], [], marks=True) == 0
    repo.write("src/app/ui/view.py", "from app.core import add\n\ndef show():\n    return add(1, 1)\n# edit\n")
    assert (
        unit_runner.run_units(repo.root, cache, config, ["tests/ui"], [], marks=True) == 0
    )  # core is skipped: its data comes from the cache
    out = subprocess.run(
        [sys.executable, "-m", "coverage", "report", "--data-file", str(next(cache.glob("core-*.cov")))],
        cwd=repo.root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "core.py" in out.stdout
    assert unit_runner.combine(repo.root, cache, config) == 0


def test_a_failing_unit_caches_nothing_and_stops_the_run(repo: Repo, tmp_path: Path) -> None:
    _app(repo)
    repo.write("tests/core/test_core.py", "def test_bad():\n    assert False\n")
    config = gate_units.load(repo.root)
    assert config is not None
    cache = tmp_path / "cache"
    assert unit_runner.run_units(repo.root, cache, config, ["tests/core", "tests/ui"], [], marks=True) != 0
    assert not list(cache.glob("*.cov"))


def test_the_floor_fails_when_the_combined_coverage_is_under_it(repo: Repo, tmp_path: Path) -> None:
    _app(repo)
    repo.write("pyproject.toml", _PYPROJECT.replace("floor = 50", "floor = 100"))
    repo.write("src/app/dead.py", "def never():\n    return 1\n")
    config = gate_units.load(repo.root)
    assert config is not None
    cache = tmp_path / "cache"
    assert unit_runner.run_units(repo.root, cache, config, ["tests/core", "tests/ui"], [], marks=True) == 0
    assert unit_runner.combine(repo.root, cache, config) == 1


def test_combine_refuses_when_a_unit_has_no_data(repo: Repo, tmp_path: Path) -> None:
    _app(repo)
    config = gate_units.load(repo.root)
    assert config is not None
    assert unit_runner.combine(repo.root, tmp_path / "empty", config) == 1


# --- gate.recipe-shadowing ---------------------------------------------------------------------


def _gate(repo: Repo, justfile: str) -> tuple[Verdict, str]:
    repo.write(".blueprint/base.just", "check:\n    true\n\n[private]\ncheck-extra:\n    @:\n")
    repo.write(".blueprint/python.just", "[group('gate')]\ntest:\n    uv run blueprint gate test\n\nlint:\n    true\n")
    repo.write("justfile", "set allow-duplicate-recipes\n" + justfile.removeprefix("set allow-duplicate-recipes\n"))
    rows = {r.id: r for r in run(repo.root, concern="gate", env=repo.env).rows}
    return rows["gate.recipe-shadowing"].verdict, rows["gate.recipe-shadowing"].evidence


def test_a_justfile_that_redefines_a_rendered_recipe_fails_naming_it(repo: Repo) -> None:
    verdict, evidence = _gate(repo, "import '.blueprint/base.just'\nimport '.blueprint/python.just'\n\ntest:\n    pytest\n")
    assert verdict is Verdict.FAILING
    assert "test" in evidence


@pytest.mark.parametrize("header", ['lint path=".":', 'test x="a:b":'])
@pytest.mark.parametrize("location", ["justfile", "local.just"])
def test_defaulted_and_imported_recipe_shadows_are_reported(repo: Repo, header: str, location: str) -> None:
    own = header + "\n    true\n"
    if location != "justfile":
        repo.write(location, own)
        own = f"import '{location}'\n"
    verdict, evidence = _gate(repo, "set allow-duplicate-recipes\nimport '.blueprint/base.just'\nimport '.blueprint/python.just'\n" + own)
    assert verdict is Verdict.FAILING
    assert header.split(maxsplit=1)[0] in evidence


def test_check_extra_is_the_declared_extension_point_and_is_not_shadowing(repo: Repo) -> None:
    verdict, _ = _gate(repo, "import '.blueprint/base.just'\nimport '.blueprint/python.just'\n\ncheck-extra:\n    true\n\nown:\n    true\n")
    assert verdict is Verdict.PASSING


def test_a_declared_override_for_the_recipe_passes_and_says_why(repo: Repo) -> None:
    repo.write(
        "docs/blueprint/blueprint.toml",
        '[[override]]\nid = "gate.recipe-shadowing"\nscope = "test"\nreason = "runs the duckdb-safe coverage form"\nexpires = 2099-01-01\n',
    )
    verdict, evidence = _gate(repo, "import '.blueprint/base.just'\nimport '.blueprint/python.just'\n\ntest:\n    pytest\n")
    assert verdict is Verdict.PASSING
    assert "test" in evidence


def test_a_repo_without_rendered_parts_has_nothing_to_shadow(repo: Repo) -> None:
    repo.write("justfile", "test:\n    true\ncheck:\n    true\n")
    rows = {r.id: r for r in run(repo.root, concern="gate", env=repo.env).rows}
    assert rows["gate.recipe-shadowing"].verdict is Verdict.NOT_APPLICABLE


# --- fail closed, parallel data, and the second run ---------------------------------------------


def test_a_file_beside_reached_code_changes_the_key(repo: Repo) -> None:
    _app(repo)
    repo.write("src/app/query.sql", "select 1\n")
    before = _keys(repo)
    repo.write("src/app/query.sql", "select 2\n")
    assert _keys(repo)["core"] != before["core"]  # core.py sits in src/app beside it


@pytest.mark.parametrize("junk", [".DS_Store", "core.cpython-312.pyc", "notes.swp"])
def test_editor_and_interpreter_litter_beside_reached_code_does_not_change_the_key(repo: Repo, junk: str) -> None:
    _app(repo)
    before = _keys(repo)
    repo.write(f"src/app/{junk}", "x")
    assert _keys(repo) == before


def test_a_module_imported_by_a_computed_name_widens_the_key_to_its_package(repo: Repo) -> None:
    _app(repo)
    repo.write("src/app/loader.py", "import importlib\n\ndef load(name):\n    return importlib.import_module(name)\n")
    repo.write("src/app/other/__init__.py", "")
    repo.write("src/app/other/thing.py", "X = 1\n")
    repo.write(
        "tests/core/test_core.py", "from app import loader\nfrom app.core import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    before = _keys(repo)
    repo.write("src/app/other/thing.py", "X = 2\n")
    assert _keys(repo)["core"] != before["core"]
    assert _keys(repo)["ui"] == before["ui"]


def test_parallel_coverage_data_is_joined_into_the_units_one_file(repo: Repo, tmp_path: Path) -> None:
    _app(repo)
    repo.write("pyproject.toml", _PYPROJECT + "parallel = true\n")
    config = gate_units.load(repo.root)
    assert config is not None
    cache = tmp_path / "cache"
    assert unit_runner.run_units(repo.root, cache, config, ["tests/core", "tests/ui"], [], marks=True) == 0
    assert unit_runner.combine(repo.root, cache, config) == 0


@pytest.mark.slow(
    budget=60,
    reason="three real gate runs, one pytest process per unit each: 11 s alone, 26 s beside a gate; a fake runner proves nothing",
)
def test_a_second_run_starts_no_test_process(repo: Repo, tmp_path: Path) -> None:
    _app(repo)
    count = tmp_path / "count"
    probe = f"from pathlib import Path\n\ndef test_ran():\n    Path({str(count)!r}).open('a').write('%s')\n"
    repo.write("tests/core/test_core.py", "from app.core import add\n" + probe % "x" + "    assert add(1, 2) == 3\n")
    repo.write("tests/ui/test_view.py", "from app.ui import view\n" + probe % "y" + "    assert view.show() == 2\n")

    def go() -> int:
        return gate_test.run(
            repo.root,
            whole=False,
            receipts=tmp_path / "r.json",
            lease_root=tmp_path / "leases",
            pytest_args="",
            cache=tmp_path / "cache",
            env=repo.env,
        )

    assert go() == 0
    assert count.read_text() == "xy"
    assert go() == 0
    assert count.read_text() == "xy"  # nothing ran: the cached data is the receipt
    repo.write("src/app/ui/view.py", "from app.core import add\n\ndef show():\n    return add(1, 1)\n# edit\n")
    assert go() == 0
    assert count.read_text() == "xyy"  # only the ui unit


def test_a_pytest_cov_unit_never_fails_alone_on_the_whole_repo_floor() -> None:
    # `fail_under` in [tool.coverage.report] is the whole repo's floor, applied once by `combine`, not per unit.
    command = unit_runner._command("pytest-cov", [], ("tests/a",))
    assert "--cov-fail-under=0" in command
    assert command.index("--cov-fail-under=0") < command.index("tests/a")


def _golden_app(repo: Repo) -> None:
    """`_app` plus every way the key reaches a file: a relative import, a data file beside code, a computed import, `reads`, a lock."""
    _app(repo)
    repo.write("src/app/ui/rel.py", "from . import view\nfrom .. import core\n")
    repo.write("src/app/ui/page.html", "<p>x</p>\n")
    repo.write("src/app/plug/__init__.py", "import importlib\n\ndef load(name):\n    return importlib.import_module(name)\n")
    repo.write("src/app/plug/a.py", "A = 1\n")
    repo.write("src/app/plug/data.sql", "select 1;\n")
    repo.write("tests/ui/test_rel.py", "from app.ui import rel\nfrom app import plug\n\ndef test_rel():\n    assert rel and plug\n")
    repo.write("uv.lock", "version = 1\n")


# Frozen from the keys the code produced before they were computed once per run (shelf-8r18): a faster key must be the same key, or
# every receipt and every cached coverage file in every consumer is orphaned.
_GOLDEN_KEYS = {"core": "978a12d6328662c03aedd39746ecf0f1", "ui": "0785155ef09e26e4c14748ce64fbed46"}


def test_a_unit_key_is_the_one_it_has_always_been(repo: Repo) -> None:
    _golden_app(repo)
    assert _keys(repo) == _GOLDEN_KEYS


# ── keys are computed once per run, each file read once (shelf-8r18) ─────────────────────────────────────────────────────────────────


def _count_reads(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Every file `Path.read_bytes` / `read_text` opens, by name, counted."""
    from pathlib import Path as RealPath  # noqa: PLC0415

    seen: dict[str, int] = {}
    read_bytes, read_text = RealPath.read_bytes, RealPath.read_text

    def bytes_(self: Path) -> bytes:
        seen[str(self)] = seen.get(str(self), 0) + 1
        return read_bytes(self)

    def text(self: Path, *args: object, **kwargs: object) -> str:
        seen[str(self)] = seen.get(str(self), 0) + 1
        return read_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(RealPath, "read_bytes", bytes_)
    monkeypatch.setattr(RealPath, "read_text", text)
    return seen


def test_every_unit_key_of_a_run_is_computed_with_each_file_read_once(repo: Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    _golden_app(repo)
    config = gate_units.load(repo.root)
    assert config is not None
    seen = _count_reads(monkeypatch)
    keys = gate_units.keys(repo.root, config)
    assert keys == _GOLDEN_KEYS
    assert seen, "the keys read files"
    assert {name: n for name, n in seen.items() if n > 1} == {}  # a file two units share, or a parse and a hash, is still one read


def test_a_no_op_run_reads_each_file_once_and_hands_the_runner_the_keys(
    repo: Repo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _golden_app(repo)
    repo.write("pyproject.toml", _PYPROJECT.replace("floor = 50\n", ""))  # no floor: nothing to combine
    cache = tmp_path / "cache"
    config = gate_units.load(repo.root)
    assert config is not None
    for unit in config.units:
        unit_runner.data_file(cache, unit.name, _GOLDEN_KEYS[unit.name]).parent.mkdir(parents=True, exist_ok=True)
        unit_runner.data_file(cache, unit.name, _GOLDEN_KEYS[unit.name]).write_bytes(b"")
    seen = _count_reads(monkeypatch)
    ran: list[list[str]] = []

    def execute(cmd: list[str], *, cwd: Path, stdin: str | None, env: dict[str, str]) -> tuple[int, str]:
        ran.append(cmd)
        return 0, ""

    code = gate_test.run(repo.root, whole=False, receipts=None, lease_root=None, cache=cache, execute=execute, env=repo.env)
    assert code == 0
    key_reads = {name: n for name, n in seen.items() if not name.endswith("pyproject.toml")}
    assert {name: n for name, n in key_reads.items() if n > 1} == {}
    assert "--keys=" + json.dumps(_GOLDEN_KEYS, sort_keys=True) in ran[-1]


def test_a_repo_with_no_floor_skips_combine(repo: Repo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _golden_app(repo)
    repo.write("pyproject.toml", _PYPROJECT.replace("floor = 50\n", ""))
    called: list[str] = []
    monkeypatch.setattr(unit_runner, "combine", lambda *a, **k: called.append("combine") or 1)
    code = gate_test.run(
        repo.root, whole=False, receipts=None, lease_root=None, cache=tmp_path / "c", env=repo.env, execute=lambda *a, **k: (0, "")
    )
    assert code == 0
    assert called == []


# ── globs in `paths` and the `rest` unit ─────────────────────────────────────────────────────────────────────────────────────────────

_ROOT_FILES = ("tests/test_a.py", "tests/test_b.py", "tests/b_test.py")


def _loose(repo: Repo, units: str) -> gate_units.Config:
    """`_app` plus loose test files under `tests/`, with `units` as the repo's unit table."""
    _app(repo)
    for path in _ROOT_FILES:
        repo.write(path, "from app.core import add\n\ndef test_x():\n    assert add(1, 1) == 2\n")
    repo.write("tests/helpers.py", "X = 1\n")
    repo.write(
        "pyproject.toml",
        _PYPROJECT.split("[tool.blueprint.test.units.core]", maxsplit=1)[0] + units + "\n[tool.coverage.run]\nsource = ['src/app']\n",
    )
    config = gate_units.load(repo.root)
    assert config is not None
    return config


def test_a_glob_in_paths_names_every_match_sorted(repo: Repo) -> None:
    config = _loose(repo, '[tool.blueprint.test.units.root]\npaths = ["tests/test_*.py", "tests/*_test.py"]\n')
    assert config.problems == ()
    assert config.units[0].paths == ("tests/b_test.py", "tests/test_a.py", "tests/test_b.py")


def test_a_globbed_unit_has_the_key_of_the_hand_listed_one(repo: Repo) -> None:
    globbed = _loose(repo, '[tool.blueprint.test.units.root]\npaths = ["tests/test_*.py", "tests/*_test.py"]\n')
    by_glob = gate_units.keys(repo.root, globbed)
    listed = _loose(repo, '[tool.blueprint.test.units.root]\npaths = ["tests/b_test.py", "tests/test_a.py", "tests/test_b.py"]\n')
    assert gate_units.keys(repo.root, listed) == by_glob


def test_a_glob_that_matches_nothing_is_a_problem_not_an_empty_unit(repo: Repo) -> None:
    config = _loose(repo, '[tool.blueprint.test.units.root]\npaths = ["tests/nothing_*.py"]\n')
    assert any("matches nothing" in p and "root" in p for p in config.problems)


def test_the_rest_unit_is_every_test_file_no_other_unit_claims(repo: Repo) -> None:
    config = _loose(
        repo,
        '[tool.blueprint.test.units.core]\npaths = ["tests/core"]\n[tool.blueprint.test.units.rest]\nrest = true\n'
        '[tool.blueprint.test.units.ui]\npaths = ["tests/ui", "tests/test_b.py"]\n',
    )
    assert config.problems == ()
    rest = next(u for u in config.units if u.name == "rest")
    assert rest.paths == ("tests/b_test.py", "tests/test_a.py")  # the folders and the file other units name are not in it
    assert gate_units.uncovered_test_folders(repo.root, config) == []


def test_a_new_test_file_joins_the_rest_unit_and_changes_only_its_key(repo: Repo) -> None:
    units = (
        '[tool.blueprint.test.units.core]\npaths = ["tests/core"]\n[tool.blueprint.test.units.rest]\nrest = true\n'
        '[tool.blueprint.test.units.ui]\npaths = ["tests/ui"]\n'
    )
    config = _loose(repo, units)
    before = gate_units.keys(repo.root, config)
    repo.write("tests/test_new.py", "def test_new():\n    assert True\n")
    after_config = gate_units.load(repo.root)
    assert after_config is not None
    after = gate_units.keys(repo.root, after_config)
    assert "tests/test_new.py" in next(u for u in after_config.units if u.name == "rest").paths
    assert after["rest"] != before["rest"]
    assert (after["core"], after["ui"]) == (before["core"], before["ui"])


def test_a_rest_unit_whose_files_are_all_claimed_is_no_unit(repo: Repo) -> None:
    config = _loose(repo, '[tool.blueprint.test.units.all]\npaths = ["tests"]\n[tool.blueprint.test.units.rest]\nrest = true\n')
    assert [u.name for u in config.units] == ["all"]


def test_only_one_rest_unit_is_allowed(repo: Repo) -> None:
    config = _loose(repo, "[tool.blueprint.test.units.a]\nrest = true\n[tool.blueprint.test.units.b]\nrest = true\n")
    assert any("rest" in p for p in config.problems)
