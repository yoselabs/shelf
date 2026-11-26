"""Run named tests in one in-process pytest session and record the repository functions each one executes.

pytest runs every requested test (its fixtures and the repository's conftest work), and coverage.py measures each
test's call alone, so collection-time imports never count as behaviour. Executed lines map to the innermost enclosing
function with py-symbols.
"""

import contextlib
import importlib
import io
import sys
import warnings
from collections.abc import Generator, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import coverage
import pytest
from py_symbols import functions, innermost

_PYTEST_ARGS = ("-q", "-p", "no:cacheprovider", "-o", "addopts=", "--import-mode=importlib")


@dataclass(frozen=True)
class Reach:
    """Repository files and `(file, qualified function)` pairs that tests executed, and whether every test passed."""

    files: frozenset[str]
    functions: frozenset[tuple[str, str]]
    passed: bool


@dataclass(eq=False)  # pytest registers the plugin in a set: it must hash by identity
class _PerTest:
    """A pytest plugin: measure each test's call with its own coverage run."""

    root: Path
    wanted: frozenset[str]
    lines: dict[str, dict[str, set[int]]] = field(default_factory=dict)  # test id -> file -> executed lines
    passed: dict[str, bool] = field(default_factory=dict)

    def pytest_collection_modifyitems(self, items: list[pytest.Item], config: pytest.Config) -> None:
        """Run only the requested tests; asking pytest for a missing one by id would stop the whole session."""
        chosen = [item for item in items if item.nodeid in self.wanted]
        config.hook.pytest_deselected(items=[item for item in items if item.nodeid not in self.wanted])
        items[:] = chosen

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_call(self, item: pytest.Item) -> Generator[None, object, object]:
        measure = coverage.Coverage(data_file=None, config_file=False, include=[f"{self.root}/*"])
        measure.start()
        try:
            return (yield)
        finally:
            measure.stop()
            data = measure.get_data()
            self.lines[item.nodeid] = {name: set(data.lines(name) or ()) for name in data.measured_files()}

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.when == "call" or not report.passed:
            self.passed[report.nodeid] = self.passed.get(report.nodeid, True) and report.passed


def _hit(path: Path, lines: set[int]) -> set[str]:
    spans = functions(path.read_text(encoding="utf-8"))
    return {name for line in lines if (name := innermost(spans, line)) is not None}


@contextlib.contextmanager
def _importable(root: Path, folders: Iterable[str]) -> Generator[None]:
    """Put the repository's import roots first and forget its modules before and after, so edits are seen."""
    added = [str(root / folder) for folder in folders]
    sys.path[:0] = added

    def purge() -> None:
        for name, module in list(sys.modules.items()):
            origin = getattr(module, "__file__", None)
            if isinstance(origin, str) and Path(origin).is_relative_to(root):
                del sys.modules[name]

    importlib.invalidate_caches()
    purge()
    try:
        yield
    finally:
        purge()
        for entry in added:
            sys.path.remove(entry)


def run(
    root: Path,
    node_ids: Iterable[str],
    *,
    import_roots: Iterable[str] = ("src",),
    exclude: Iterable[str] = ("tests/",),
) -> dict[str, Reach]:
    """Run `path::name` tests in `root` once each; what each executed, outside the `exclude` prefixes.

    A test that does not exist, or whose file is missing, comes back not passed with nothing reached.
    """
    root = root.resolve()
    wanted = sorted(set(node_ids))
    if not wanted:
        return {}
    plugin = _PerTest(root, frozenset(wanted))
    files = sorted({test.split("::")[0] for test in wanted if (root / test.split("::")[0]).is_file()})
    if files:
        # The measured repository owns its warning policy: the outer session's filters (an "error" among them) must not
        # turn a warning raised while the inner session configures into a failed run of the tests it was asked for.
        with _importable(root, import_roots), contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
            warnings.resetwarnings()
            pytest.main([*_PYTEST_ARGS, "--rootdir", str(root), *(str(root / name) for name in files)], plugins=[plugin])
    skipped = tuple(exclude)
    results: dict[str, Reach] = {}
    for test in wanted:
        hit = {
            (Path(name).relative_to(root).as_posix(), function)
            for name, lines in plugin.lines.get(test, {}).items()
            if Path(name).is_relative_to(root) and not Path(name).relative_to(root).as_posix().startswith(skipped)
            for function in _hit(Path(name), lines)
        }
        results[test] = Reach(frozenset(file for file, _ in hit), frozenset(hit), plugin.passed.get(test, False))
    return results


def union(reaches: Iterable[Reach]) -> Reach:
    """One entry's reach: the union over its tests; it passes when every test passed (and there is at least one)."""
    items = list(reaches)
    return Reach(
        frozenset().union(*(item.files for item in items)),
        frozenset().union(*(item.functions for item in items)),
        bool(items) and all(item.passed for item in items),
    )
