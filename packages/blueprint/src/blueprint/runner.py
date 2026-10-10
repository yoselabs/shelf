"""Select the checks a repo's profile calls for and run them all in this one process."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Run:
    """A whole run: the profile it judged, the checkpoint-set hash, every row."""

    profile: Profile
    set_hash: str
    rows: tuple[Row, ...]
    problems: tuple[str, ...]

    @property
    def exit_code(self) -> int:
        """1 when anything fails or is not set up; 2 when nothing fails but something went unchecked.

        A row the blueprint itself cannot judge yet (`blueprint_gap`) counts for neither: it is the
        shelf's gap, filed there, not the repo's.
        """
        verdicts = {r.verdict for r in self.rows if not r.blueprint_gap}
        if verdicts & {Verdict.FAILING, Verdict.NOT_SET_UP} or self.problems:
            return 1
        return 2 if Verdict.NOT_CHECKED in verdicts else 0


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
            evidence = f"override {override.code} until {override.expires.isoformat()}: {override.reason} (saw: {evidence})"
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
    )


def run(
    repo: Path, *, concern: str | None = None, audit: bool = False, today: date | None = None, env: dict[str, str] | None = None
) -> Run:
    """Run every applicable check on `repo`; the audit-only ones only when `audit`."""
    repo = repo.resolve()
    state = load_state(repo)
    profile = detect(repo, state)
    ctx = Context(repo=repo, profile=profile, settings=state.settings)
    if env is not None:
        ctx.env = env
    checks = active(profile, concern)
    today = today or date.today()  # noqa: DTZ011 -- override expiry is a calendar date in the owner's zone
    rows = tuple(_row(c, sub, state, today) for c in checks if audit or not c.audit_only for sub in _judge(c, ctx))
    return Run(profile=profile, set_hash=set_hash(active(profile)), rows=rows, problems=state.problems)
