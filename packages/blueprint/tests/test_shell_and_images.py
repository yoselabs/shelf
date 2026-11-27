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
    repo.write_executable("tools/a.sh", _STRICT)
    repo.write_executable("tools/b.sh", _STRICT)
    rows = _rows(repo)
    assert "tools/a.sh" in rows["stack.shell.profile"][1]
    assert rows["stack.shell.linter"][0] is Verdict.NOT_SET_UP


def test_one_short_wrapper_is_not_a_shell_stack(repo: Repo) -> None:
    repo.write_executable("run.sh", '#!/bin/sh\nexec python -m app "$@"\n')
    assert "stack.shell.profile" not in _rows(repo)


def test_one_long_script_is_a_shell_stack(repo: Repo) -> None:
    repo.write_executable("build.sh", _LONG)
    assert "stack.shell.profile" in _rows(repo)


def test_bds_hook_shims_are_not_the_repos_scripts(repo: Repo) -> None:
    repo.write_executable(".beads/hooks/pre-commit.sh", _LONG)
    assert "stack.shell.profile" not in _rows(repo)


def test_strict_scripts_pass(repo: Repo) -> None:
    repo.write_executable("tools/a.sh", _STRICT)
    repo.write_executable("tools/b.sh", "#!/bin/sh\nset -eu\necho hi\n")
    assert _strict(repo)[0] is Verdict.PASSING


def test_a_bash_script_without_pipefail_fails_and_is_named(repo: Repo) -> None:
    repo.write_executable("tools/a.sh", _STRICT)
    repo.write_executable("tools/loose.sh", "#!/usr/bin/env bash\nset -e\necho hi\n")
    verdict, evidence = _strict(repo)
    assert verdict is Verdict.FAILING
    assert "tools/loose.sh" in evidence
    assert "tools/a.sh" not in evidence


def test_long_option_names_count(repo: Repo) -> None:
    repo.write_executable("tools/a.sh", _STRICT)
    repo.write_executable("tools/b.sh", "#!/bin/bash\nset -o errexit\nset -o nounset -o pipefail\n")
    assert _strict(repo)[0] is Verdict.PASSING


_PROBE = "#!/usr/bin/env bash\nset -uo pipefail\necho probing\n"


def _strict_override(repo: Repo, scope: str, fields: str = "expires = 2099-01-01\n") -> None:
    repo.write(
        "docs/blueprint/blueprint.toml",
        f'[[override]]\nid = "stack.shell.strict-mode"\nscope = "{scope}"\nreason = "reports every failing host"\n{fields}',
    )


def test_a_probe_may_drop_errexit_with_a_scoped_override(repo: Repo) -> None:
    repo.write_executable("tools/a.sh", _STRICT)
    repo.write_executable("tools/probe.sh", _PROBE)
    _strict_override(repo, "tools/probe.sh")
    verdict, evidence = _strict(repo)
    assert verdict is Verdict.PASSING
    assert "reports every failing host" in evidence


def test_an_override_for_one_script_excuses_no_other(repo: Repo) -> None:
    repo.write_executable("tools/a.sh", _STRICT)
    repo.write_executable("tools/probe.sh", _PROBE)
    repo.write_executable("tools/other.sh", _PROBE)
    _strict_override(repo, "tools/probe.sh")
    verdict, evidence = _strict(repo)
    assert verdict is Verdict.FAILING
    assert "tools/other.sh" in evidence
    assert "tools/probe.sh (" not in evidence


def test_an_unjustified_strict_override_excuses_nothing(repo: Repo) -> None:
    repo.write_executable("tools/a.sh", _STRICT)
    repo.write_executable("tools/probe.sh", _PROBE)
    _strict_override(repo, "tools/probe.sh", fields="")
    assert _strict(repo)[0] is Verdict.FAILING


def test_a_strict_marker_is_still_honoured_and_notices_the_override_to_write(repo: Repo) -> None:
    repo.write_executable("tools/a.sh", _STRICT)
    repo.write_executable("tools/probe.sh", "#!/usr/bin/env bash\n# strict: no -e, reports every failing host\nset -uo pipefail\n")
    assert _strict(repo)[0] is Verdict.PASSING
    (notice,) = run(repo.root, concern="stack", env=repo.env).notices
    assert "move this to an [[override]] in docs/blueprint/blueprint.toml" in notice
    assert 'id = "stack.shell.strict-mode"' in notice
    assert 'scope = "tools/probe.sh"' in notice
    assert 'reason = "reports every failing host"' in notice


def test_a_strict_marker_still_needs_u_and_pipefail(repo: Repo) -> None:
    repo.write_executable("tools/a.sh", _STRICT)
    repo.write_executable("tools/probe.sh", "#!/usr/bin/env bash\n# strict: no -e, probe\nset -u\n")
    verdict, evidence = _strict(repo)
    assert verdict is Verdict.FAILING
    assert "tools/probe.sh (no pipefail)" in evidence


def test_a_sourced_library_is_not_judged(repo: Repo) -> None:
    repo.write_executable("tools/a.sh", _STRICT)
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
    repo.write_executable("packaging/macos/build_app.sh", _LONG.replace("set -euo pipefail\n", "set -e\n"))
    rows = _rows(repo)
    assert "packaging/macos/build_app.sh" in rows["stack.shell.profile"][1]
    assert rows["stack.shell.strict-mode"][0] is Verdict.FAILING
    assert "stack.shell.agent-guidance" not in rows
    assert not any(row.startswith("stack.shell-scripts.") for row in rows)


def test_an_image_nothing_in_the_gate_builds_fails_the_tests_row(repo: Repo) -> None:
    repo.write("Dockerfile", "FROM python:3.12-slim\n")
    assert _rows(repo)["stack.dockerfile.tests"][0] is Verdict.NOT_SET_UP


def test_a_workflow_that_builds_an_image_does_not_count_as_a_build(repo: Repo) -> None:
    repo.write("Dockerfile", "FROM python:3.12-slim\n")
    repo.write(".github/workflows/image.yml", "jobs:\n  image:\n    steps:\n      - uses: docker/build-push-action@abc\n")
    assert _rows(repo)["stack.dockerfile.tests"][0] is Verdict.NOT_SET_UP


def test_a_test_image_the_gate_builds_passes_the_tests_row(repo: Repo) -> None:
    repo.write("scripts/prune/test.Dockerfile", "FROM python:3.12-slim\n")
    repo.write("justfile", "check: test-image\ntest-image:\n    docker build -q -f scripts/prune/test.Dockerfile .\n")
    assert _rows(repo)["stack.dockerfile.tests"][0] is Verdict.PASSING


def test_an_image_nothing_builds_fails_the_tests_row_by_name(repo: Repo) -> None:
    repo.write("Dockerfile", "FROM python:3.12-slim\n")
    repo.write("images/worker/Dockerfile", "FROM python:3.12-slim\n")
    repo.write("justfile", "check: img\nimg:\n    docker build -q -f Dockerfile .\n")
    verdict, evidence = _rows(repo)["stack.dockerfile.tests"]
    assert verdict is Verdict.NOT_SET_UP
    assert "nothing builds images/worker/Dockerfile" in evidence
    assert "nothing builds Dockerfile" not in evidence


def test_bats_tests_run_by_the_gate_pass_the_shell_tests_row(repo: Repo) -> None:
    repo.write_executable("tools/a.sh", _STRICT)
    repo.write_executable("tools/b.sh", _STRICT)
    assert _rows(repo)["stack.shell.tests"][0] is Verdict.NOT_SET_UP
    repo.write("tests/shell/a.bats", "@test 'a' { true; }\n")
    repo.write("mise.toml", '[tools]\nbats = "1.14.0"\n')
    repo.write("justfile", "check: shell-test\nshell-test:\n    bats tests/shell\n")
    rows = _rows(repo)
    assert rows["stack.shell.tests"][0] is Verdict.PASSING
    assert "stack.shell.coverage" not in rows  # na for the stack: not a checkpoint


def test_the_compose_policy_in_the_gate_passes_architecture_and_tests(repo: Repo) -> None:
    repo.write("stacks/web/compose.yml", "services: {}\n")
    repo.write("policy/compose.rego", "package main\ndeny contains msg if { false }\n# healthcheck\n")
    repo.write("docs/blueprint/blueprint.toml", '[profile]\nkind = "infrastructure"\ntraits = ["deployed"]\n')
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


def test_an_ignored_script_is_not_a_shell_stack(repo: Repo) -> None:
    # a2kay 2026-10-12: two macOS-only, hand-run scripts; an ignore naming a file (not a folder) must hold.
    repo.write_executable("packaging/macos/build_app.sh", _LONG)
    reason = 'reason = "macOS-only tool the owner runs by hand"\nexpires = 2099-01-01\n'
    repo.write("docs/blueprint/blueprint.toml", f'[[profile.ignore]]\npath = "packaging/macos/build_app.sh"\n{reason}')
    assert "stack.shell.profile" not in _rows(repo)


# ADR 0026: what the repo does adds checkpoints. A repo classified as shipping an image needs a base-image updater;
# a deployed stack needs the compose healthcheck and architecture policy. No repository has CI, so no workflow shows either.
_SHIPS = '[profile]\nkind = "application"\ntraits = ["ships-image"]\n'


def _images(repo: Repo, *, ships: bool = True) -> None:
    repo.write("images/a/Dockerfile", "FROM python:3.12-slim\n")
    repo.write("justfile", "check: img\nimg:\n    docker build -q -f images/a/Dockerfile .\n")
    if ships:
        repo.write("docs/blueprint/blueprint.toml", _SHIPS)


def test_a_shipped_image_needs_an_updater_and_names_the_file(repo: Repo) -> None:
    _images(repo)
    verdict, evidence = _rows(repo)["stack.dockerfile.ship-updater"]
    assert verdict is Verdict.NOT_SET_UP
    assert "images/a/Dockerfile" in evidence


def test_a_shipped_image_with_an_updater_passes(repo: Repo) -> None:
    _images(repo)
    repo.write(".github/dependabot.yml", "updates:\n  - package-ecosystem: docker\n    directory: /images/a\n")
    assert _rows(repo)["stack.dockerfile.ship-updater"][0] is Verdict.PASSING


def test_an_image_nobody_classified_as_shipped_needs_no_updater(repo: Repo) -> None:
    _images(repo, ships=False)
    rows = _rows(repo)
    assert rows["stack.dockerfile.ship-updater"][0] is Verdict.NOT_APPLICABLE
    assert "ships-image" in rows["stack.dockerfile.ship-updater"][1]
    assert "stack.dockerfile.ship-smoke" not in rows


_COMPOSE_ROWS = ("stack.compose.tests", "stack.compose.architecture")


def test_a_compose_file_nothing_deploys_needs_no_healthcheck_or_architecture_policy(repo: Repo) -> None:
    repo.write("compose.yml", "services:\n  db:\n    image: postgres:17\n")
    rows = _rows(repo)
    for row in _COMPOSE_ROWS:
        assert rows[row][0] is Verdict.NOT_APPLICABLE
        assert "deployed" in rows[row][1]
    assert rows["stack.compose.linter"][0] is not Verdict.NOT_APPLICABLE


def test_a_declared_deployed_trait_makes_the_compose_policy_needed(repo: Repo) -> None:
    repo.write("compose.yml", "services:\n  db:\n    image: postgres:17\n")
    repo.write("docs/blueprint/blueprint.toml", '[profile]\nkind = "infrastructure"\ntraits = ["deployed"]\n')
    rows = _rows(repo)
    for row in _COMPOSE_ROWS:
        assert rows[row][0] is Verdict.NOT_SET_UP


def test_a_classified_deployed_claim_makes_the_compose_policy_needed(repo: Repo) -> None:
    repo.write("compose.yml", "services:\n  db:\n    image: postgres:17\n")
    repo.write(
        "docs/blueprint/blueprint.toml",
        '[profile]\nkind = "infrastructure"\n\n[[profile.classified]]\n'
        'claim = "deployed"\ndecided_by = "agent"\nreason = "a host pulls it"\n',
    )
    rows = _rows(repo)
    for row in _COMPOSE_ROWS:
        assert rows[row][0] is Verdict.NOT_SET_UP


def test_a_path_in_an_echo_or_a_comment_is_not_a_build(repo: Repo) -> None:
    repo.write("images/worker/Dockerfile", "FROM python:3.12-slim\n")
    repo.write("justfile", "check: img\nimg:\n    # images/worker/Dockerfile\n    echo images/worker/Dockerfile\n")
    verdict, evidence = _rows(repo)["stack.dockerfile.tests"]
    assert verdict is Verdict.NOT_SET_UP
    assert "nothing builds images/worker/Dockerfile" in evidence


def test_docker_build_check_counts_as_building_and_the_row_says_so(repo: Repo) -> None:
    repo.write("images/worker/Dockerfile", "FROM python:3.12-slim\n")
    repo.write("justfile", "check: img\nimg:\n    docker build --check -f images/worker/Dockerfile images/worker\n")
    assert _rows(repo)["stack.dockerfile.tests"][0] is Verdict.PASSING


def test_a_build_continued_over_lines_and_a_buildx_build_count(repo: Repo) -> None:
    repo.write("a/Dockerfile", "FROM python:3.12-slim\n")
    repo.write("b/Dockerfile", "FROM python:3.12-slim\n")
    repo.write("justfile", "check: img\nimg:\n    docker build -q \\\n      -f a/Dockerfile .\n    docker buildx build -f b/Dockerfile b\n")
    assert _rows(repo)["stack.dockerfile.tests"][0] is Verdict.PASSING


def test_the_compose_spelling_row_accepts_codespell(repo: Repo) -> None:
    repo.write("compose.yml", "services:\n  db:\n    image: postgres:17\n")
    repo.write(".codespellrc", "[codespell]\nskip = x\n")
    repo.write("justfile", "check: spell\nspell:\n    codespell compose.yml\n")
    assert _rows(repo)["stack.compose.spelling"][0] is Verdict.PASSING


def test_the_compose_spelling_row_still_accepts_typos(repo: Repo) -> None:
    repo.write("compose.yml", "services:\n  db:\n    image: postgres:17\n")
    repo.write("typos.toml", "[default]\n")
    repo.write("justfile", "check: spell\nspell:\n    typos\n")
    assert _rows(repo)["stack.compose.spelling"][0] is Verdict.PASSING
