"""Select the checks a repo's profile calls for and run them all in this one process."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import date
from typing import TYPE_CHECKING

from blueprint import concerns
from blueprint.model import REGISTRY, Check, Context, Finding, FixedBy, Profile, Sub, Verdict, not_checked
from blueprint.profile import State, detect, load_state

if TYPE_CHECKING:
    from pathlib import Path

concerns.load()


@dataclass(frozen=True)
class Row:
    """One checkpoint's line in a report (design D18)."""

    id: str
    concern: str
    statement: str
    verdict: Verdict
    set_up: bool | None
    working: bool | None
    evidence: str
    remediation: str
    fixed_by: FixedBy
    blueprint_gap: bool = False
    layer: str = "generic"
    version: int = 1
    # Not in the set the repo's last audit judged: reported, never failing the gate, until the next
    # audit takes it in. A shelf change must not turn every consumer's pre-push red mid-task.
    new: bool = False

    @property
    def key(self) -> str:
        """`id@version`, the line the audit record keeps."""
        return f"{self.id}@{self.version}"


@dataclass(frozen=True)
class Run:
    """A whole run: the profile it judged, the checkpoint-set hash, every row."""

    profile: Profile
    set_hash: str
    rows: tuple[Row, ...]
    problems: tuple[str, ...]
    # Audit-only checkpoints that apply but did not run (no `--audit`): a summary that hides them
    # shows fewer failures than the audit's README holds.
    skipped_audit: int = 0

    @property
    def exit_code(self) -> int:
        """1 when anything fails or is not set up; 2 when nothing fails but something went unchecked.

        A row the blueprint itself cannot judge yet (`blueprint_gap`) counts for neither: it is the
        shelf's gap, filed there, not the repo's.
        """
        verdicts = {r.verdict for r in self.rows if not r.blueprint_gap and not r.new}
        if verdicts & {Verdict.FAILING, Verdict.NOT_SET_UP} or self.problems:
            return 1
        return 2 if Verdict.NOT_CHECKED in verdicts else 0


ACCEPTED = "docs/blueprint/checkpoints.txt"


def _accepted(repo: Path) -> set[str] | None:
    """The `id@version` lines the last audit wrote; None before the first audit, so all is enforced.

    An audit from before the record existed (a README, no record) counts as an empty record: every
    row it did not see passing is new, so consumers audited earlier are not turned red by an upgrade.
    """
    path = repo / ACCEPTED
    if path.is_file():
        return set(path.read_text().split())
    return set() if (repo / ACCEPTED).with_name("README.md").is_file() else None


def active(profile: Profile, concern: str | None = None) -> list[Check]:
    """The registered checks that apply to `profile`, in registry order."""
    return [c for c in REGISTRY if c.applies(profile) and (concern is None or c.concern == concern)]


def set_hash(checks: list[Check]) -> str:
    """Identity of the checkpoint set: sorted ids with each check's version."""
    return hashlib.sha256("\n".join(sorted(f"{c.id}@{c.version}" for c in checks)).encode()).hexdigest()[:12]


def _refused(finding: Finding) -> Finding:
    if not finding.evidence.strip():
        return not_checked("the check returned no evidence, so its verdict is refused")
    return finding


def _judge(chk: Check, ctx: Context) -> list[Sub]:
    try:
        result = chk.run(ctx)
    except Exception as exc:  # noqa: BLE001 -- one broken check must not hide the others' verdicts
        return [Sub(chk.concern, chk.id, chk.statement, not_checked(f"the check itself crashed: {type(exc).__name__}: {exc}"))]
    if isinstance(result, Finding):
        return [Sub(chk.concern, chk.id, chk.statement, _refused(result))]
    return [Sub(s.concern, s.id, s.statement, _refused(s.finding)) for s in result]


def _row(chk: Check, sub: Sub, state: State, today: date) -> Row:
    finding = sub.finding
    verdict, evidence = finding.verdict, finding.evidence
    override = state.overrides.get(sub.id)
    if override is not None and verdict is not Verdict.PASSING:
        problem = override.problem(today)
        if problem is None:
            verdict = Verdict.PASSING
            evidence = f"override {override.code} {override.lasts}: {override.reason} (saw: {evidence})"
        else:
            evidence = f"{evidence}; {problem}"
    return Row(
        sub.id,
        sub.concern,
        sub.statement,
        verdict,
        finding.set_up,
        finding.working,
        evidence,
        finding.remediation,
        finding.fixed_by,
        finding.blueprint_gap,
        chk.layer,
        chk.version,
    )


def run(
    repo: Path, *, concern: str | None = None, audit: bool = False, today: date | None = None, env: dict[str, str] | None = None
) -> Run:
    """Run every applicable check on `repo`; the audit-only ones only when `audit`."""
    repo = repo.resolve()
    today = today or date.today()  # noqa: DTZ011 -- override expiry is a calendar date in the owner's zone
    state = load_state(repo, today)
    profile = detect(repo, state)
    ctx = Context(repo=repo, profile=profile, settings=state.settings)
    if env is not None:
        ctx.env = env
    checks = active(profile, concern)
    rows = tuple(_row(c, sub, state, today) for c in checks if audit or not c.audit_only for sub in _judge(c, ctx))
    accepted = _accepted(repo)
    if accepted is not None:
        rows = tuple(replace(r, new=True) if r.key not in accepted and r.verdict is not Verdict.PASSING else r for r in rows)
    skipped = 0 if audit else sum(c.audit_only for c in checks)
    return Run(profile=profile, set_hash=set_hash(active(profile)), rows=rows, problems=state.problems, skipped_audit=skipped)
