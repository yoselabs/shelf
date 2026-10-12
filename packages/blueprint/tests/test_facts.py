"""Detection reports facts and evidence with where they were read (ADR 0026); it does not yet act on them."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from blueprint.facts import CLAIMS, KINDS, SURFACES, TRAITS, detect_facts
from blueprint.model import Context
from blueprint.profile import detect, load_state
from blueprint.report import as_json, markdown
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_LOGIN = "      - uses: docker/login-action@v3\n"


def _build(push: str) -> str:
    return (
        "on: push\njobs:\n  b:\n    steps:\n"
        f"{_LOGIN}      - uses: docker/build-push-action@v6\n        with:\n          push: {push}\n      - run: echo done\n"
    )


def _detected(repo: Repo) -> tuple[set[tuple[str, str]], set[tuple[str, str, str]]]:
    repo.commit()
    facts, evidence = detect_facts(Context(repo.root, detect(repo.root, load_state(repo.root))))
    return {(f.claim, f.where) for f in facts}, {(e.claim, e.where, e.confidence) for e in evidence}


def test_the_closed_lists_hold_every_claim_once() -> None:
    assert len(CLAIMS) == len(set(CLAIMS)) == len(KINDS) + len(SURFACES) + len(TRAITS)


def test_console_scripts_are_a_cli_fact(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n\n[project.scripts]\nx = "x:main"\n')
    assert ("cli", "pyproject.toml:4") in _detected(repo)[0]


@pytest.mark.parametrize(("push", "ships"), [("true", True), ("false", False)])
def test_a_push_step_with_a_login_ships_an_image(repo: Repo, push: str, ships: bool) -> None:
    repo.write(".github/workflows/img.yml", _build(push))
    assert (("ships-image", ".github/workflows/img.yml:6") in _detected(repo)[0]) is ships


def test_a_push_step_without_a_login_or_with_only_load_ships_nothing(repo: Repo) -> None:
    repo.write(".github/workflows/a.yml", _build("true").replace(_LOGIN, ""))
    repo.write(".github/workflows/b.yml", _build("true").replace("push: true", "load: true"))
    assert not [f for f in _detected(repo)[0] if f[0] == "ships-image"]


def test_a_deploy_key_and_a_deploy_step_is_high_evidence_and_an_access_check_is_not(repo: Repo) -> None:
    key = "      DEPLOY_SSH_KEY: ${{ secrets.DEPLOY_SSH_KEY }}\n"
    repo.write(".github/workflows/deploy.yml", f"jobs:\n  d:\n    steps:\n      - env:\n{key}        run: uv run tools/ci_deploy.py\n")
    repo.write(".github/workflows/check.yml", f"jobs:\n  d:\n    steps:\n      - env:\n{key}        run: ssh -i k deploy@host list\n")
    assert _detected(repo)[1] == {("deployed", ".github/workflows/deploy.yml:6", "high")}


def test_a_cron_schedule_is_a_scheduled_jobs_fact(repo: Repo) -> None:
    repo.write(".github/workflows/s.yml", 'on:\n  schedule:\n    - cron: "0 7 * * 3"\n')
    assert ("scheduled-jobs", ".github/workflows/s.yml:2") in _detected(repo)[0]


@pytest.mark.parametrize(
    ("dep", "claim"), [("fastmcp", "mcp-server"), ("fastapi", "http-server"), ("duckdb", "stores-data"), ("anthropic", "llm-backed")]
)
def test_a_dependency_is_low_confidence_evidence(repo: Repo, dep: str, claim: str) -> None:
    repo.write("pyproject.toml", f'[project]\nname = "x"\ndependencies = [\n  "{dep}>=1",\n]\n')
    assert _detected(repo)[1] == {(claim, "pyproject.toml:4", "low")}


def test_a_compose_named_volume_is_low_stores_data_evidence(repo: Repo) -> None:
    repo.write("compose.yml", "services:\n  db:\n    image: x\nvolumes:\n  data:\n")
    assert ("stores-data", "compose.yml:4", "low") in _detected(repo)[1]


def test_a_sops_rules_file_is_a_holds_secrets_fact(repo: Repo) -> None:
    repo.write(".sops.yaml", "creation_rules: []\n")
    assert ("holds-secrets", ".sops.yaml") in _detected(repo)[0]


def test_the_report_and_the_json_carry_the_section(repo: Repo) -> None:
    repo.write(".sops.yaml", "creation_rules: []\n")
    repo.commit()
    result = run(repo.root, env=repo.env)
    assert "## Facts and evidence\n\n- fact: holds-secrets (`.sops.yaml`)" in markdown(result)
    assert json.loads(as_json(result))["facts_and_evidence"]["facts"] == [{"claim": "holds-secrets", "where": ".sops.yaml"}]
