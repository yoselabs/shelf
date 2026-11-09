"""The project type gate must check editable sources and keep deliberate exclusions."""

from __future__ import annotations

import json
import subprocess
import sys
import venv
from pathlib import Path


def test_typecheck_reports_editable_source_and_tool_errors(tmp_path: Path) -> None:
    """shelf-j4qq: an editable package must not disappear from the type gate."""
    root = Path(__file__).resolve().parents[1]
    project = tmp_path / "workspace"
    project.mkdir()
    (project / "pyproject.toml").write_text((root / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8")
    source = project / "packages" / "probe" / "src"
    bad_source = source / "coverage_probe" / "__init__.py"
    bad_tool = project / "tools" / "probe.py"
    excluded = project / "packages" / "convert-md" / "bench" / "engines" / "run_docling.py"
    for path in (bad_source, bad_tool, excluded):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('number: int = "wrong"\n', encoding="utf-8")

    # A real .pth makes interpreter discovery see the source as an editable install.
    # No installer, dependency download, or modification of the shared environment.
    environment = project / ".venv"
    venv.EnvBuilder(with_pip=False).create(environment)
    site_packages = next(environment.glob("lib/python*/site-packages"))
    (site_packages / "coverage_probe.pth").write_text(f"{source}\n", encoding="utf-8")
    result = subprocess.run(
        [
            str(Path(sys.prefix) / "bin" / "pyrefly"),
            "check",
            "--python-interpreter-path",
            str(environment / "bin" / "python"),
            "--output-format",
            "json",
        ],
        cwd=project,
        env={},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    errors = json.loads(result.stdout)["errors"]
    found = {(error["path"], error["name"]) for error in errors}
    expected = {(str(path.relative_to(project)), "bad-assignment") for path in (bad_source, bad_tool)}
    assert found == expected, result.stdout + result.stderr
