"""Shared size contract and changed-file enforcement (no baseline or exemptions)."""

import ast
import sys
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "tools"))

import changed  # noqa: E402 -- repository tool path
import preset_drift  # noqa: E402 -- repository tool path
import size_caps  # noqa: E402 -- repository tool path
from onboard.linter_preset import _missing_toml_blocks  # noqa: E402 -- repository tool path


def test_counting_matches_task_loop():
    text = '"""doc\nmore"""\n\n# c\nx = 1\n\ndef f():\n    """d"""\n    return (1,\n            2)\n'
    assert size_caps.sloc_lines(text, ast.parse(text)) == {5, 7, 9, 10}
    decorated = "import x\n\n@x.d\ndef f():\n    def g():\n        return 1\n    return g()\n"
    assert size_caps.measure(decorated) == (6, {"f": 5, "f.g": 2})


def test_planted_over_cap_files_and_functions(tmp_path):
    caps = {"code-file": 400, "test-file": 800, "function": 80}
    paths = ["tools/big.py", "tests/test_big.py", "tools/function.py"]
    for rel, text in zip(paths, ["x = 1\n" * 401, "x = 1\n" * 801, "def f():\n" + "    x = 1\n" * 80], strict=True):
        path = tmp_path / rel
        path.parent.mkdir(exist_ok=True)
        path.write_text(text)
    assert size_caps.problems(tmp_path, paths, caps) == [
        "tools/big.py: 401 SLOC > 400",
        "tests/test_big.py: 801 SLOC > 800",
        "tools/function.py:f: 81 SLOC > 80",
    ]
    (tmp_path / "tests/test_big.py").write_text("x = 1\n" * 800)
    assert size_caps.problems(tmp_path, ["tests/test_big.py"], caps) == []


def test_caps_are_copied_to_consumers():
    copied = tomllib.loads(_missing_toml_blocks(""))
    assert copied["tool"]["shelf-size"] == size_caps.load_caps(_ROOT)


def test_changed_code_and_tests_obey_shared_caps():
    paths = changed.select(_ROOT, ["packages/*/src/*.py", "packages/*/tests/*.py", "tools/*.py", "tests/*.py"])
    assert size_caps.problems(_ROOT, paths, size_caps.load_caps(_ROOT)) == []


def test_size_preset_drift_is_detected():
    reference = {"tool": {"shelf-size": size_caps.load_caps(_ROOT)}}
    assert preset_drift.size_drift(reference, reference) == []
    assert preset_drift.size_drift(reference, {})
    consumer = {"tool": {"shelf-size": {**size_caps.load_caps(_ROOT), "function": 81}}}
    assert preset_drift.size_drift(reference, consumer)


def test_token_lines_and_docstrings_inside_control_flow():
    text = (
        "if True:\n"
        "    async def f():\n"
        '        """doc\n'
        '        more"""\n'
        '        value = """data\n'
        "blank\n"
        'end"""  # comment\n'
        "        return value\n"
    )
    assert size_caps.sloc_lines(text, ast.parse(text)) == {1, 2, 5, 6, 7, 8}
    assert size_caps.measure(text) == (6, {"f": 5})
