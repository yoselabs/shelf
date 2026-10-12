"""The shell and dockerfile stacks: detected from their files, judged by their profiles, scripts in strict mode."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint import templates
from blueprint.model import Verdict
from blueprint.profile import detect, load_state
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


def test_one_script_in_a_python_repo_is_the_shell_stack_with_its_conventions_file(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    repo.write("uv.lock", "")
    repo.write("packaging/macos/build_app.sh", _LONG.replace("set -euo pipefail\n", "set -e\n"), executable=True)
    rows = _rows(repo)
    assert "packaging/macos/build_app.sh" in rows["stack.shell.profile"][1]
    assert rows["stack.shell.strict-mode"][0] is Verdict.FAILING
    assert rows["stack.shell.agent-guidance"][0] is not Verdict.NOT_APPLICABLE
    assert not any(row.startswith("stack.shell-scripts.") for row in rows)
    assert "shell" in templates.required(detect(repo.root, load_state(repo.root)))


_WORKFLOW = "jobs:\n  image:\n    steps:\n      - uses: docker/build-push-action@abc # v7\n      - run: docker run --rm app:ci app --help\n"


def test_a_ci_job_that_builds_and_runs_the_image_passes_the_tests_row(repo: Repo) -> None:
    repo.write("Dockerfile", "FROM python:3.12-slim\n")
    assert _rows(repo)["stack.dockerfile.tests"][0] is Verdict.NOT_SET_UP
    repo.write(".github/workflows/image.yml", _WORKFLOW)
    assert _rows(repo)["stack.dockerfile.tests"][0] is Verdict.PASSING


def test_a_test_image_the_gate_builds_passes_the_tests_row_without_ci(repo: Repo) -> None:
    repo.write("scripts/prune/test.Dockerfile", "FROM python:3.12-slim\n")
    repo.write("justfile", "check: test-image\ntest-image:\n    docker build -q -f scripts/prune/test.Dockerfile .\n")
    assert _rows(repo)["stack.dockerfile.tests"][0] is Verdict.PASSING


def test_an_image_nothing_builds_fails_the_tests_row_by_name(repo: Repo) -> None:
    repo.write("Dockerfile", "FROM python:3.12-slim\n")
    repo.write(".github/workflows/image.yml", _WORKFLOW)
    repo.write("images/worker/Dockerfile", "FROM python:3.12-slim\n")
    verdict, evidence = _rows(repo)["stack.dockerfile.tests"]
    assert verdict is Verdict.NOT_SET_UP
    assert "nothing builds images/worker/Dockerfile" in evidence
    assert "nothing builds Dockerfile" not in evidence


def test_ci_that_builds_an_image_without_running_it_does_not_pass(repo: Repo) -> None:
    repo.write("Dockerfile", "FROM python:3.12-slim\n")
    repo.write(".github/workflows/image.yml", "jobs:\n  image:\n    steps:\n      - uses: docker/build-push-action@abc\n")
    assert _rows(repo)["stack.dockerfile.tests"][0] is Verdict.NOT_SET_UP


def test_ci_names_a_nested_image_by_its_file(repo: Repo) -> None:
    repo.write("images/worker/Dockerfile", "FROM python:3.12-slim\n")
    named = "# v7\n        with:\n          file: images/worker/Dockerfile\n"
    repo.write(".github/workflows/image.yml", _WORKFLOW.replace("# v7\n", named))
    assert _rows(repo)["stack.dockerfile.tests"][0] is Verdict.PASSING


def test_a_matrix_ci_job_builds_each_image_its_template_matches(repo: Repo) -> None:
    repo.write("images/devbox/Dockerfile", "FROM ubuntu:24.04\n")
    repo.write("images/frigate/Dockerfile", "FROM ubuntu:24.04\n")
    repo.write("tools/x.Dockerfile", "FROM ubuntu:24.04\n")
    matrix = "        with:\n          file: images/${{ matrix.image }}/Dockerfile\n"
    repo.write(".github/workflows/image.yml", _WORKFLOW.replace("# v7\n", "# v7\n" + matrix))
    verdict, evidence = _rows(repo)["stack.dockerfile.tests"]
    assert verdict is Verdict.NOT_SET_UP
    assert evidence.endswith("(missing nothing builds tools/x.Dockerfile)")


def test_bats_tests_run_by_the_gate_pass_the_shell_tests_row(repo: Repo) -> None:
    repo.write("tools/a.sh", _STRICT, executable=True)
    repo.write("tools/b.sh", _STRICT, executable=True)
    assert _rows(repo)["stack.shell.tests"][0] is Verdict.NOT_SET_UP
    repo.write("tests/shell/a.bats", "@test 'a' { true; }\n")
    repo.write("mise.toml", '[tools]\nbats = "1.14.0"\n')
    repo.write("justfile", "check: shell-test\nshell-test:\n    bats tests/shell\n")
    rows = _rows(repo)
    assert rows["stack.shell.tests"][0] is Verdict.PASSING
    assert rows["stack.shell.coverage"][0] is Verdict.NOT_APPLICABLE


def test_the_compose_policy_in_the_gate_passes_architecture_and_tests(repo: Repo) -> None:
    repo.write("stacks/web/compose.yml", "services: {}\n")
    repo.write("policy/compose.rego", "package main\ndeny contains msg if { false }\n# healthcheck\n")
    repo.write("justfile", "check: policy\npolicy:\n    conftest test --policy policy stacks/*/compose.yml\n")
    rows = _rows(repo)
    assert rows["stack.compose.architecture"][0] is Verdict.PASSING
    assert rows["stack.compose.tests"][0] is Verdict.PASSING


def test_nix_eval_tests_in_the_gate_pass_the_nix_tests_row(repo: Repo) -> None:
    repo.write("hosts/bee/flake.nix", "{ }")
    repo.write("tests/nix/udev.nix", "assert true; true\n")
    repo.write("justfile", "check: nix-test\nnix-test:\n    for t in tests/nix/*.nix; do nix eval --impure --raw --file $t; done\n")
    assert _rows(repo)["stack.nix.tests"][0] is Verdict.PASSING


# ADR 0026: a technology in use turns on all of its checkpoints, whatever the count of files.
def _python(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    repo.write("uv.lock", "")


def test_one_dockerfile_in_a_python_repo_is_the_full_dockerfile_stack(repo: Repo) -> None:
    _python(repo)
    repo.write("tools/gate.Dockerfile", "FROM python:3.12-slim\n")
    rows = _rows(repo)
    assert "tools/gate.Dockerfile" in rows["stack.dockerfile.profile"][1]
    assert rows["stack.dockerfile.formatter"][0] is not Verdict.NOT_APPLICABLE
    assert rows["stack.dockerfile.linter"][0] is Verdict.NOT_SET_UP
    assert not any(row.startswith("stack.dockerfile-lite.") for row in rows)


def test_one_compose_file_in_a_python_repo_is_the_full_compose_stack(repo: Repo) -> None:
    _python(repo)
    repo.write("compose.yml", "services:\n  db:\n    image: postgres:17\n")
    rows = _rows(repo)
    assert "stack.compose.profile" in rows
    assert not any(row.startswith("stack.compose-lite.") for row in rows)
    assert "compose" in templates.required(detect(repo.root, load_state(repo.root)))
