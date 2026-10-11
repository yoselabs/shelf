"""Backlog checkpoints, against a fake `bd`: each seen passing and failing on a planted violation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from blueprint.concerns.backlog import STRICT
from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo


def _beads(repo: Repo, *, config: dict[str, str] | None = None, lint_exit: int = 0) -> None:
    repo.write(".beads/config.yaml", "")
    repo.write(".gitignore", ".beads.gate.lock*\n")
    repo.write(".claude/settings.json", json.dumps({"env": {"BD_DISABLE_METRICS": "1"}}))
    repo.fake_bd(STRICT if config is None else config, lint_exit=lint_exit, lint_out="shelf-1 missing acceptance criteria")


def _verdicts(repo: Repo) -> dict[str, Verdict]:
    return {r.id: r.verdict for r in run(repo.root, concern="backlog", audit=True, env=repo.env).rows}


def test_a_strict_quiet_beads_repo_passes_every_backlog_checkpoint(repo: Repo) -> None:
    _beads(repo)
    assert set(_verdicts(repo).values()) == {Verdict.PASSING}


def test_no_beads_means_the_tracker_is_not_set_up_and_beads_checks_do_not_run(repo: Repo) -> None:
    assert _verdicts(repo) == {"backlog.tracker": Verdict.NOT_SET_UP}


@pytest.mark.parametrize(("key", "weak"), [("validation.on-create", "warn"), ("export.auto", "true"), ("no-git-ops", "false")])
def test_a_weakened_setting_fails_strict_config(repo: Repo, key: str, weak: str) -> None:
    _beads(repo, config={**STRICT, key: weak})
    assert _verdicts(repo)["backlog.strict-config"] is Verdict.FAILING


def test_a_setting_from_the_environment_fails_strict_config(repo: Repo) -> None:
    _beads(repo)
    shown = json.loads((repo.bin_dir / "bd.json").read_text())
    shown[0]["source"] = "env"
    (repo.bin_dir / "bd.json").write_text(json.dumps(shown))
    assert _verdicts(repo)["backlog.strict-config"] is Verdict.FAILING


def _show(repo: Repo, *entries: tuple[str, str, str]) -> None:
    """bd's `config show --json` for the strict set, with these (key, value, source) rows added or replacing the key's."""
    keys = {k for k, _, _ in entries}
    rows = [{"key": k, "value": v, "source": "config.yaml"} for k, v in STRICT.items() if k not in keys]
    rows += [{"key": k, "value": v, "source": src} for k, v, src in entries]
    (repo.bin_dir / "bd.json").write_text(json.dumps(rows))


@pytest.mark.parametrize("reverse", [False, True])
def test_a_value_only_in_bds_database_fails_whatever_order_bd_lists_it_in(repo: Repo, reverse: bool) -> None:
    # a2kay: `bd config set import.auto false` wrote the database; bd then listed the key twice
    # (default true, database false) in random order, and the verdict flipped between runs.
    _beads(repo)
    pair = [("import.auto", "true", "default"), ("import.auto", "false", "database")]
    _show(repo, *(pair[::-1] if reverse else pair))
    row = next(r for r in run(repo.root, concern="backlog", audit=True, env=repo.env).rows if r.id == "backlog.strict-config")
    assert row.verdict is Verdict.FAILING
    assert "import.auto" in row.evidence
    assert ".beads/config.yaml" in row.evidence
    assert ".beads/config.yaml" in row.remediation
    assert "bd config set import.auto" not in row.remediation


@pytest.mark.parametrize("reverse", [False, True])
def test_config_yaml_outranks_a_duplicate_default_whatever_the_order(repo: Repo, reverse: bool) -> None:
    _beads(repo)
    pair = [("import.auto", "true", "default"), ("import.auto", "false", "config.yaml")]
    _show(repo, *(pair[::-1] if reverse else pair))
    assert _verdicts(repo)["backlog.strict-config"] is Verdict.PASSING


def test_a_strict_value_that_only_the_default_supplies_fails(repo: Repo) -> None:
    _beads(repo)
    _show(repo, ("export.auto", "false", "default"))
    assert _verdicts(repo)["backlog.strict-config"] is Verdict.FAILING


def test_a_tracked_jsonl_export_fails(repo: Repo) -> None:
    _beads(repo)
    repo.write(".beads/issues.jsonl", "{}\n")
    repo.commit()
    assert _verdicts(repo)["backlog.no-tracked-export"] is Verdict.FAILING


@pytest.mark.parametrize("plant", ["local-file", "session-env"])
def test_a_local_override_fails(repo: Repo, plant: str) -> None:
    _beads(repo)
    if plant == "local-file":
        repo.write(".beads/config.local.yaml", "validation:\n  on-create: none\n")
    else:
        repo.write(".claude/settings.json", json.dumps({"env": {"BD_DISABLE_METRICS": "1", "BD_VALIDATION_ON_CREATE": "none"}}))
    assert _verdicts(repo)["backlog.no-local-override"] is Verdict.FAILING


def test_a_bead_failing_lint_fails(repo: Repo) -> None:
    _beads(repo, lint_exit=1)
    assert _verdicts(repo)["backlog.lint"] is Verdict.FAILING


def test_a_blocked_bead_is_linted_too(repo: Repo) -> None:
    # `bd lint` alone reads only `open`; a blocked bead turns ready when its blocker closes, so it needs criteria too.
    _beads(repo)
    real = (repo.bin_dir / "bd").read_text()
    (repo.bin_dir / "bd").write_text(
        real.replace(
            'if [ "$1" = lint ]',
            'if [ "$1" = lint ] && [ "$3" = blocked ]; then echo "x-9 [task]: t"; exit 1; fi\nif [ "$1" = lint ]',
            1,
        )
    )
    row = next(r for r in run(repo.root, concern="backlog", audit=True, env=repo.env).rows if r.id == "backlog.lint")
    assert row.verdict is Verdict.FAILING
    assert "x-9" in row.evidence


_LINT = """Template warnings (3 issues, 4 warnings):

a2kay-p6hj [epic]: Search rewrite
  \u26a0 Missing: ## Success Criteria

a2kay-aa11 [bug]: Crash on empty query
  \u26a0 Missing: ## Steps to Reproduce
  \u26a0 Missing: ## Acceptance Criteria

a2kay-bb22 [task]: Rename the thing
  \u26a0 Missing: ## Acceptance Criteria
"""


def test_lint_evidence_counts_beads_and_missing_sections_and_names_the_first_few(repo: Repo) -> None:
    # a2kay printed `Template warnings (166 issues, 202 warnings): /  / a2kay-p6hj [epic]: ...`: blank lines as
    # empty segments, one bead named, nothing to size the cleanup by.
    repo.write(".beads/config.yaml", "")
    repo.fake_bd(STRICT, lint_exit=1, lint_out=_LINT)
    row = next(r for r in run(repo.root, concern="backlog", audit=True, env=repo.env).rows if r.id == "backlog.lint")
    assert row.verdict is Verdict.FAILING
    assert row.evidence == (
        "3 beads miss sections: Acceptance Criteria x2, Steps to Reproduce x1, Success Criteria x1; "
        "first: a2kay-p6hj, a2kay-aa11, a2kay-bb22"
    )


def test_lint_evidence_caps_the_bead_list_at_five_and_keeps_the_total(repo: Repo) -> None:
    beads = "".join(f"x-{i} [task]: t\n  \u26a0 Missing: ## Acceptance Criteria\n\n" for i in range(8))
    repo.write(".beads/config.yaml", "")
    repo.fake_bd(STRICT, lint_exit=1, lint_out=f"Template warnings (8 issues, 8 warnings):\n\n{beads}")
    row = next(r for r in run(repo.root, concern="backlog", audit=True, env=repo.env).rows if r.id == "backlog.lint")
    assert row.evidence.startswith("8 beads miss sections: Acceptance Criteria x8; first: x-0, x-1, x-2, x-3, x-4")
    assert "x-5" not in row.evidence


def test_a_second_backlog_file_fails(repo: Repo) -> None:
    _beads(repo)
    repo.write("TODO.md", "- [ ] something\n")
    assert _verdicts(repo)["backlog.no-tracker-file"] is Verdict.FAILING


def test_bd_missing_is_not_checked_never_a_pass(repo: Repo) -> None:
    _beads(repo)
    repo.env["PATH"] = "/nonexistent"
    verdicts = _verdicts(repo)
    assert verdicts["backlog.strict-config"] is Verdict.NOT_CHECKED
    assert verdicts["backlog.lint"] is Verdict.NOT_CHECKED


def test_the_gate_run_leaves_out_what_needs_bds_database(repo: Repo) -> None:
    _beads(repo)
    ids = {r.id for r in run(repo.root, concern="backlog", env=repo.env).rows}
    assert "backlog.strict-config" not in ids
    assert "backlog.lint" not in ids
    assert "backlog.no-tracked-export" in ids


def test_bds_root_lock_file_must_be_git_ignored(repo: Repo) -> None:
    # bd 1.3.1 writes .beads.gate.lock beside .beads/; homelab's audit found it untracked in `git status` (2026-10-11).
    _beads(repo)
    (repo.root / ".gitignore").unlink()
    verdict = _verdicts(repo)["backlog.lock-ignored"]
    assert verdict is Verdict.FAILING
    repo.write(".gitignore", ".beads.gate.lock*\n")
    assert _verdicts(repo)["backlog.lock-ignored"] is Verdict.PASSING


def test_a_clone_whose_bd_database_does_not_answer_fails_lint(repo: Repo) -> None:
    # a2kay (shelf-9g7): an uninitialized database made `bd lint` say "0 issues checked" and exit 0.
    _beads(repo)
    real = (repo.bin_dir / "bd").read_text()
    (repo.bin_dir / "bd").write_text(
        real.replace(
            'if [ "$1" = lint ]', 'if [ "$1" = list ]; then echo "Error: no beads database found" >&2; exit 1; fi\nif [ "$1" = lint ]', 1
        )
    )
    row = next(r for r in run(repo.root, concern="backlog", audit=True, env=repo.env).rows if r.id == "backlog.lint")
    assert row.verdict is Verdict.FAILING
    assert "bd bootstrap" in row.remediation


def test_an_uninitialized_database_gets_the_fix_bootstrap_alone_cannot_make(repo: Repo) -> None:
    _beads(repo)
    real = (repo.bin_dir / "bd").read_text()
    (repo.bin_dir / "bd").write_text(
        real.replace(
            'if [ "$1" = lint ]',
            'if [ "$1" = list ]; then echo "Error: database not initialized: issue_prefix missing" >&2; exit 1; fi\nif [ "$1" = lint ]',
            1,
        )
    )
    row = next(r for r in run(repo.root, concern="backlog", audit=True, env=repo.env).rows if r.id == "backlog.lint")
    assert "embeddeddolt.broken" in row.remediation


# homelab, 2026-10-11: `bd bootstrap` in a fresh clone rewrites .beads/metadata.json without a final newline, so an
# end-of-file-fixer over every file failed `just check` in every new clone.
_FIXER = (
    "repos:\n- repo: https://github.com/pre-commit/pre-commit-hooks\n  rev: v6.0.0\n  hooks:\n"
    "  - id: end-of-file-fixer\n{extra}  - id: check-yaml\n"
)


def test_a_whitespace_fixer_hook_over_beads_files_fails(repo: Repo) -> None:
    _beads(repo)
    repo.write(".pre-commit-config.yaml", _FIXER.format(extra=""))
    assert _verdicts(repo)["backlog.hooks-spare-beads"] is Verdict.FAILING


def test_a_whitespace_hook_never_seen_failing_on_beads_files_is_not_judged(repo: Repo) -> None:
    _beads(repo)
    repo.write(".pre-commit-config.yaml", _FIXER.format(extra="    exclude: ^\\.beads/\n").replace("check-yaml", "trailing-whitespace"))
    assert _verdicts(repo)["backlog.hooks-spare-beads"] is Verdict.PASSING


def test_a_fixer_hook_that_excludes_beads_passes(repo: Repo) -> None:
    _beads(repo)
    repo.write(".pre-commit-config.yaml", _FIXER.format(extra="    exclude: ^\\.beads/\n"))
    assert _verdicts(repo)["backlog.hooks-spare-beads"] is Verdict.PASSING


def test_a_top_level_exclude_of_beads_covers_every_hook(repo: Repo) -> None:
    _beads(repo)
    repo.write(".pre-commit-config.yaml", "exclude: ^(\\.beads/|vendor/)\n" + _FIXER.format(extra=""))
    assert _verdicts(repo)["backlog.hooks-spare-beads"] is Verdict.PASSING
