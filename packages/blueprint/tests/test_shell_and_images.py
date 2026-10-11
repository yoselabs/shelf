"""The shell and dockerfile stacks: detected from their files, judged by their profiles, scripts in strict mode."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_STRICT = "#!/usr/bin/env bash\n# Deploys a host.\nset -euo pipefail\necho hi\n"
_LONG = "#!/usr/bin/env bash\nset -euo pipefail\n" + "echo line\n" * 12


def _rows(repo: Repo) -> dict[str, tuple[Verdict, str]]:
    repo.commit()
    return {r.id: (r.verdict, r.evidence) for r in run(repo.root, concern="stack", env=repo.env).rows}


def _strict(repo: Repo) -> tuple[Verdict, str]:
    return _rows(repo)["stack.shell.strict-mode"]


def test_two_scripts_make_a_shell_stack(repo: Repo) -> None:
    repo.write("tools/a.sh", _STRICT, executable=True)
    repo.write("tools/b.sh", _STRICT, executable=True)
    rows = _rows(repo)
    assert "tools/a.sh" in rows["stack.shell.profile"][1]
    assert rows["stack.shell.linter"][0] is Verdict.NOT_SET_UP


def test_one_short_wrapper_is_not_a_shell_stack(repo: Repo) -> None:
    repo.write("run.sh", '#!/bin/sh\nexec python -m app "$@"\n', executable=True)
    assert "stack.shell.profile" not in _rows(repo)


def test_one_long_script_is_a_shell_stack(repo: Repo) -> None:
    repo.write("build.sh", _LONG, executable=True)
    assert "stack.shell.profile" in _rows(repo)


def test_bds_hook_shims_are_not_the_repos_scripts(repo: Repo) -> None:
    repo.write(".beads/hooks/pre-commit.sh", _LONG, executable=True)
    assert "stack.shell.profile" not in _rows(repo)


def test_strict_scripts_pass(repo: Repo) -> None:
    repo.write("tools/a.sh", _STRICT, executable=True)
    repo.write("tools/b.sh", "#!/bin/sh\nset -eu\necho hi\n", executable=True)
    assert _strict(repo)[0] is Verdict.PASSING


def test_a_bash_script_without_pipefail_fails_and_is_named(repo: Repo) -> None:
    repo.write("tools/a.sh", _STRICT, executable=True)
    repo.write("tools/loose.sh", "#!/usr/bin/env bash\nset -e\necho hi\n", executable=True)
    verdict, evidence = _strict(repo)
    assert verdict is Verdict.FAILING
    assert "tools/loose.sh" in evidence
    assert "tools/a.sh" not in evidence


def test_long_option_names_count(repo: Repo) -> None:
    repo.write("tools/a.sh", _STRICT, executable=True)
    repo.write("tools/b.sh", "#!/bin/bash\nset -o errexit\nset -o nounset -o pipefail\n", executable=True)
    assert _strict(repo)[0] is Verdict.PASSING


def test_a_probe_may_drop_errexit_with_a_reason(repo: Repo) -> None:
    repo.write("tools/a.sh", _STRICT, executable=True)
    repo.write("tools/probe.sh", "#!/usr/bin/env bash\n# strict: no -e, reports every failing host\nset -uo pipefail\n", executable=True)
    assert _strict(repo)[0] is Verdict.PASSING


def test_a_sourced_library_is_not_judged(repo: Repo) -> None:
    repo.write("tools/a.sh", _STRICT, executable=True)
    repo.write("tools/lib.sh", '# sourced by a.sh\nlog() { echo "$1"; }\n')
    assert _strict(repo)[0] is Verdict.PASSING


def test_a_dockerfile_makes_a_dockerfile_stack_and_its_ignore_file_does_not(repo: Repo) -> None:
    repo.write("scripts/prune/test.Dockerfile", "FROM python:3.12-slim\n")
    repo.write("scripts/prune/test.Dockerfile.dockerignore", "*\n")
    rows = _rows(repo)
    evidence = rows["stack.dockerfile.profile"][1]
    assert "test.Dockerfile" in evidence
    assert "dockerignore" not in evidence
    assert rows["stack.dockerfile.linter"][0] is Verdict.NOT_SET_UP


def test_hadolint_in_the_gate_with_its_config_passes(repo: Repo) -> None:
    repo.write("Dockerfile", "FROM python:3.12-slim\n")
    repo.write(".hadolint.yaml", "ignored: []\n")
    repo.write("justfile", "check: images\nimages:\n    git ls-files '*Dockerfile' | xargs hadolint\n")
    assert _rows(repo)["stack.dockerfile.linter"][0] is Verdict.PASSING
