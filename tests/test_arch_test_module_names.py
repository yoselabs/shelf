"""Two test files with one basename in different packages collide under pytest's default import mode ("import file mismatch").

The collision hid on main for a while: a gate runs only the suites a change reaches, and the two packages were never reached together
until a change to the root pyproject selected every test (2026-11-23: any-frontmatter and any-local-service both had `test_version.py`).
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def test_no_two_packages_share_a_test_file_name() -> None:
    names: dict[str, list[str]] = defaultdict(list)
    for path in sorted(_ROOT.glob("packages/*/tests/**/test_*.py")):
        if not (path.parent / "__init__.py").is_file():
            names[path.name].append(path.relative_to(_ROOT).as_posix())
    clashes = {name: files for name, files in names.items() if len(files) > 1}
    assert not clashes, f"rename one: pytest cannot import two test files with the same name from folders without __init__.py: {clashes}"
