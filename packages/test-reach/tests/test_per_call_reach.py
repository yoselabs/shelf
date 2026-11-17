"""The functions a named test executes: per call, repository code only, fixtures working."""

from pathlib import Path

from test_reach import Reach, run, union


def write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)


def test_reach_names_executed_functions_not_imports_or_tests(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "src/app/fee.py": "def late_fee(days):\n    return days * 2\n\n\ndef unused():\n    return 0\n",
            "tests/test_fee.py": "from app.fee import late_fee\n\n\ndef test_late_fee():\n    assert late_fee(3) == 6\n",
        },
    )
    ran = run(tmp_path, ["tests/test_fee.py::test_late_fee", "tests/test_none.py::test_missing"])
    fee = "src/app/fee.py"
    assert ran["tests/test_fee.py::test_late_fee"] == Reach(frozenset({fee}), frozenset({(fee, "late_fee")}), True)
    assert not ran["tests/test_none.py::test_missing"].passed


def test_a_test_may_use_pytest_fixtures(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "src/notes.py": "def write(folder):\n    (folder / 'n.txt').write_text('x')\n",
            "tests/test_notes.py": "import notes\n\n\ndef test_write(tmp_path):\n    notes.write(tmp_path)\n",
        },
    )
    ran = run(tmp_path, ["tests/test_notes.py::test_write"])
    assert ran["tests/test_notes.py::test_write"] == Reach(frozenset({"src/notes.py"}), frozenset({("src/notes.py", "write")}), True)


def test_each_test_is_measured_alone_and_a_failure_is_reported(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "lib/m.py": "class K:\n    def a(self):\n        return 1\n\n    def b(self):\n        return 2\n",
            "tests/test_m.py": (
                "from m import K\n\n\ndef test_a():\n    assert K().a() == 1\n\n\ndef test_b():\n    assert K().b() == 3\n"
            ),
        },
    )
    ran = run(tmp_path, ["tests/test_m.py::test_a", "tests/test_m.py::test_b"], import_roots=("lib",))
    assert ran["tests/test_m.py::test_a"] == Reach(frozenset({"lib/m.py"}), frozenset({("lib/m.py", "K.a")}), True)
    assert ran["tests/test_m.py::test_b"] == Reach(frozenset({"lib/m.py"}), frozenset({("lib/m.py", "K.b")}), False)


def test_union_passes_only_when_every_test_passed() -> None:
    one = Reach(frozenset({"a.py"}), frozenset({("a.py", "f")}), True)
    two = Reach(frozenset({"b.py"}), frozenset({("b.py", "g")}), False)
    assert union([one, one]).passed
    assert union([one, two]) == Reach(frozenset({"a.py", "b.py"}), frozenset({("a.py", "f"), ("b.py", "g")}), False)
    assert not union([]).passed
