"""Secrets: a sealed file really is sealed, a sops rule covers it, and a scanner in the gate guards the rest."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_SEALED = (
    "TOKEN=ENC[AES256_GCM,data:abc,iv:def,tag:ghi,type:str]\n"
    "sops_age__list_0__map_recipient=age1xyz\n"
    "sops_mac=ENC[AES256_GCM,data:mac,iv:x,tag:y,type:str]\n"
    "sops_version=3.13.3\n"
)
_RULES = "creation_rules:\n  - path_regex: hosts/[^/]+/stacks/.*\\.sops$\n    age: age1xyz\n"
_GATE = "check: secrets\nsecrets:\n    gitleaks git --no-banner --redact\n"


def _rows(repo: Repo) -> dict[str, tuple[Verdict, str]]:
    repo.commit()
    return {r.id: (r.verdict, r.evidence) for r in run(repo.root, concern="secrets", env=repo.env).rows}


def _sops_repo(repo: Repo) -> None:
    repo.write("justfile", _GATE)
    repo.write(".sops.yaml", _RULES)
    repo.write("hosts/bee/stacks/web.secrets.env.sops", _SEALED)


def test_a_sealed_and_covered_repo_with_a_scanner_passes(repo: Repo) -> None:
    _sops_repo(repo)
    assert {v for v, _ in _rows(repo).values()} == {Verdict.PASSING}


def test_a_repo_without_sops_is_judged_only_for_the_scanner(repo: Repo) -> None:
    repo.write("justfile", _GATE)
    rows = _rows(repo)
    assert rows["secrets.encrypted"][0] is Verdict.NOT_APPLICABLE
    assert rows["secrets.rule-coverage"][0] is Verdict.NOT_APPLICABLE
    assert rows["secrets.scanner"][0] is Verdict.PASSING


def test_a_plaintext_file_under_a_sops_name_fails(repo: Repo) -> None:
    _sops_repo(repo)
    repo.write("hosts/bee/stacks/db.secrets.env.sops", "PASSWORD=hunter2\n")
    verdict, evidence = _rows(repo)["secrets.encrypted"]
    assert verdict is Verdict.FAILING
    assert "db.secrets.env.sops" in evidence
    assert "web.secrets.env.sops" not in evidence


def test_one_plaintext_line_in_a_sealed_file_fails(repo: Repo) -> None:
    _sops_repo(repo)
    repo.write("hosts/bee/stacks/web.secrets.env.sops", _SEALED + "DEBUG_TOKEN=plain\n")
    assert _rows(repo)["secrets.encrypted"][0] is Verdict.FAILING


def test_a_sealed_yaml_file_passes(repo: Repo) -> None:
    _sops_repo(repo)
    repo.write(".sops.yaml", _RULES + "  - path_regex: \\.sops\\.yaml$\n    age: age1xyz\n")
    repo.write("conf/app.sops.yaml", "key: ENC[AES256_GCM,data:a,iv:b,tag:c,type:str]\nsops:\n    mac: ENC[AES256_GCM,data:m]\n")
    assert _rows(repo)["secrets.encrypted"][0] is Verdict.PASSING


def test_the_rules_file_is_not_taken_for_a_secret(repo: Repo) -> None:
    _sops_repo(repo)
    evidence = _rows(repo)["secrets.encrypted"][1]
    assert ".sops.yaml" not in evidence
    assert "1 sops file" in evidence


def test_a_file_no_rule_covers_fails(repo: Repo) -> None:
    _sops_repo(repo)
    repo.write("other/new.secrets.env.sops", _SEALED)
    verdict, evidence = _rows(repo)["secrets.rule-coverage"]
    assert verdict is Verdict.FAILING
    assert "other/new.secrets.env.sops" in evidence


def test_sops_files_without_rules_are_not_set_up(repo: Repo) -> None:
    _sops_repo(repo)
    (repo.root / ".sops.yaml").unlink()
    assert _rows(repo)["secrets.rule-coverage"][0] is Verdict.NOT_SET_UP


def test_no_scanner_in_the_gate_is_not_set_up(repo: Repo) -> None:
    repo.write("justfile", "check:\n    true\n")
    verdict, _ = _rows(repo)["secrets.scanner"]
    assert verdict is Verdict.NOT_SET_UP


def test_a_scanner_only_in_the_hooks_fails_because_the_gate_never_runs_it(repo: Repo) -> None:
    repo.write("justfile", "check:\n    true\n")
    repo.write(".pre-commit-config.yaml", "repos:\n  - repo: https://github.com/gitleaks/gitleaks\n    hooks:\n      - id: gitleaks\n")
    verdict, evidence = _rows(repo)["secrets.scanner"]
    assert verdict is Verdict.FAILING
    assert "hooks" in evidence


def test_a_scanner_the_gate_reaches_through_its_hooks_passes(repo: Repo) -> None:
    repo.write("justfile", "check:\n    prek run --all-files\n")
    repo.write(".pre-commit-config.yaml", "repos:\n  - repo: https://github.com/gitleaks/gitleaks\n    hooks:\n      - id: gitleaks\n")
    assert _rows(repo)["secrets.scanner"][0] is Verdict.PASSING
