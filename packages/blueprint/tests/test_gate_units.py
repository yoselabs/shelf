"""Test units for a non-workspace repo: keys that follow what a unit reaches, cached coverage, the shadowed-recipe checkpoint."""

from __future__ import annotations

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
            repo.root, receipts=tmp_path / "r", lease_root=tmp_path / "leases", cache=tmp_path / "cache", env=repo.env, pytest_args=args
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
    settings = '\npytest-args = ["-q", "--override-ini=markers=slow: excluded"]\nmarks = "not slow"'
    settings += '\nenv = { BLUEPRINT_TEST_VALUE = "configured", COVERAGE_FILE = "wrong.cov" }'
    manifest = _PYPROJECT.replace('coverage = "coverage"', f'coverage = "{mode}"').replace("floor = 50", "floor = 50" + settings)
    repo.write("pyproject.toml", manifest)
    repo.write(
        "tests/core/test_core.py",
        "import os\nimport pytest\nfrom app.core import add\n\n"
        "def test_environment():\n    assert os.environ['BLUEPRINT_TEST_VALUE'] == 'configured'\n    assert add(1, 2) == 3\n\n"
        "@pytest.mark.slow\ndef test_excluded():\n    assert False\n",
    )
    assert (
        gate_test.run(repo.root, receipts=tmp_path / "r.json", lease_root=tmp_path / "leases", cache=tmp_path / "cache", env=repo.env) == 0
    )
    assert not (repo.root / "wrong.cov").exists()


def test_noncoverage_command_puts_configured_arguments_before_cli_arguments(repo: Repo) -> None:
    _app(repo)
    manifest = _PYPROJECT.replace('coverage = "coverage"', 'pytest-args = ["-q"]\nmarks = "not slow"')
    repo.write("pyproject.toml", manifest)
    _, command = gate_test.commands(repo.root, receipts=None, lease_root=None, pytest_args="-v")
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
    _, test = gate_test.commands(repo.root, receipts=None, lease_root=None, pytest_args="", cache=repo.root / "c")
    assert test[test.index("--") + 1 :][1:3] == ["-m", "blueprint.unit_runner"]


def test_a_green_run_caches_each_units_data_and_combines_it_whole_repo(repo: Repo, tmp_path: Path) -> None:
    _app(repo)
    config = gate_units.load(repo.root)
    assert config is not None
    cache = tmp_path / "cache"
    assert unit_runner.run_units(repo.root, cache, config, ["tests/core", "tests/ui"], []) == 0
    assert unit_runner.cached(cache, config, repo.root) == {f"{n}:{k}" for n, k in _keys(repo).items()}
    assert unit_runner.combine(repo.root, cache, config) == 0


def test_a_skipped_unit_still_counts_toward_the_floor(repo: Repo, tmp_path: Path) -> None:
    _app(repo)
    config = gate_units.load(repo.root)
    assert config is not None
    cache = tmp_path / "cache"
    assert unit_runner.run_units(repo.root, cache, config, ["tests/core", "tests/ui"], []) == 0
    repo.write("src/app/ui/view.py", "from app.core import add\n\ndef show():\n    return add(1, 1)\n# edit\n")
    assert unit_runner.run_units(repo.root, cache, config, ["tests/ui"], []) == 0  # core is skipped: its data comes from the cache
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
    assert unit_runner.run_units(repo.root, cache, config, ["tests/core", "tests/ui"], []) != 0
    assert not list(cache.glob("*.cov"))


def test_the_floor_fails_when_the_combined_coverage_is_under_it(repo: Repo, tmp_path: Path) -> None:
    _app(repo)
    repo.write("pyproject.toml", _PYPROJECT.replace("floor = 50", "floor = 100"))
    repo.write("src/app/dead.py", "def never():\n    return 1\n")
    config = gate_units.load(repo.root)
    assert config is not None
    cache = tmp_path / "cache"
    assert unit_runner.run_units(repo.root, cache, config, ["tests/core", "tests/ui"], []) == 0
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
    assert unit_runner.run_units(repo.root, cache, config, ["tests/core", "tests/ui"], []) == 0
    assert unit_runner.combine(repo.root, cache, config) == 0


def test_a_second_run_starts_no_test_process(repo: Repo, tmp_path: Path) -> None:
    _app(repo)
    count = tmp_path / "count"
    probe = f"from pathlib import Path\n\ndef test_ran():\n    Path({str(count)!r}).open('a').write('%s')\n"
    repo.write("tests/core/test_core.py", "from app.core import add\n" + probe % "x" + "    assert add(1, 2) == 3\n")
    repo.write("tests/ui/test_view.py", "from app.ui import view\n" + probe % "y" + "    assert view.show() == 2\n")

    def go() -> int:
        return gate_test.run(
            repo.root, receipts=tmp_path / "r.json", lease_root=tmp_path / "leases", pytest_args="", cache=tmp_path / "cache", env=repo.env
        )

    assert go() == 0
    assert count.read_text() == "xy"
    assert go() == 0
    assert count.read_text() == "xy"  # nothing ran: the cached data is the receipt
    repo.write("src/app/ui/view.py", "from app.core import add\n\ndef show():\n    return add(1, 1)\n# edit\n")
    assert go() == 0
    assert count.read_text() == "xyy"  # only the ui unit
