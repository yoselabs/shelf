"""Gate ci: owning domain checks and evidence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from blueprint.model import (
    Context,
    Finding,
    failing,
    not_applicable,
    not_checked,
    not_set_up,
    passing,
)

if TYPE_CHECKING:
    from pathlib import Path

# `make check`, `just check-all`, `uv run just check`, `uvx rust-just@1.58.0 check`: a step that runs the gate.
_GATE_RUN = re.compile(r"\b(?:make|just|rust-just(?:@\S+)?)\s+(?:-\S+\s+)*check(?:-all)?\b")
_USES = re.compile(r"^\s*-?\s*uses:\s*['\"]?([^\s'\"#]+)", re.MULTILINE)
_SHA = re.compile(r"@[0-9a-f]{40}$")


def workflows(ctx: Context) -> list[Path]:
    wf = ctx.path(".github/workflows")
    return sorted([*wf.glob("*.yml"), *wf.glob("*.yaml")]) if wf.is_dir() else []


def ci(ctx: Context) -> Finding:
    """GitHub Actions: some job runs `just check`/`check-all` (or make's); `uses:` pinned by SHA; top-level permissions."""
    files = workflows(ctx)
    if not files:
        if ctx.read(".gitlab-ci.yml") is not None:
            return not_checked("GitLab CI is not checked yet; blueprint covers GitHub Actions")
        return not_set_up(
            "no .github/workflows/*.yml",
            "add a workflow that runs `uv run just check-all` (or `just check`) on push and pull request; "
            "a repo that decided on no CI records an override of gate.ci with its reason and "
            '`adr = "NNNN"` (the accepted ADR that decided it)',
        )
    problems: list[str] = []
    if not any(_GATE_RUN.search(f.read_text()) for f in files):
        problems.append("no workflow runs the gate (`just check` or `just check-all`)")
    for f in files:
        text = f.read_text()
        unpinned = sorted({u for u in _USES.findall(text) if not u.startswith(("./", "docker://")) and not _SHA.search(u)})
        if unpinned:
            problems.append(f"{f.name}: not pinned to a SHA: {', '.join(unpinned)}")
        if not re.search(r"^permissions:", text, re.MULTILINE):
            problems.append(f"{f.name}: no top-level `permissions:`")
    if problems:
        return failing(
            "; ".join(problems),
            "run the gate word in CI; pin each action as `owner/repo@<40-hex sha> # vX`; add `permissions: contents: read`",
        )
    return passing(f"{len(files)} workflow(s) run the gate, pinned, with permissions")


@dataclass(frozen=True)
class _Step:
    job: str
    name: str
    run: str


_JOB = re.compile(r"^ {2}([\w.-]+):\s*(?:#.*)?$")
_ITEM = re.compile(r"^(\s*)-\s+(.*)$")


def _step_chunks(workflow: str) -> list[tuple[str, list[str]]]:
    """(job, lines) per step, in file order; each chunk's first line is the `- ` item with its marker blanked."""
    job, item_indent, in_jobs = "", None, False
    chunks: list[tuple[str, list[str]]] = []
    for line in workflow.splitlines():
        if re.match(r"^jobs:\s*$", line):
            in_jobs = True
        elif in_jobs and (m := _JOB.match(line)):
            job, item_indent = m.group(1), None
        elif in_jobs and re.match(r"^\s+steps:\s*$", line):
            item_indent = None
        elif in_jobs and job and (m := _ITEM.match(line)) and item_indent in (None, len(m.group(1))):
            item_indent = len(m.group(1))
            chunks.append((job, [" " * (item_indent + 2) + m.group(2)]))
        elif chunks and item_indent is not None and (not line.strip() or len(line) - len(line.lstrip()) > item_indent):
            chunks[-1][1].append(line)
    return chunks


def _block_scalar(lines: list[str], indent: int) -> str:
    """The lines of a `|` or `>` value: everything indented deeper than its key."""
    block: list[str] = []
    for line in lines:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        block.append(line.strip())
    return "\n".join(block)


def _unquoted(value: str) -> str:
    return value[1:-1] if len(value) > 1 and value[0] == value[-1] and value[0] in "'\"" else value


def _steps(workflow: str) -> list[_Step]:
    """The steps of every job, in file order, with their name and `run` text.

    A line-wise reading: stdlib has no YAML parser, and a workflow's steps are regular enough that the
    `- ` items under `steps:` give each one's keys at a fixed indent.
    """
    steps: list[_Step] = []
    for job, lines in _step_chunks(workflow):
        indent = len(lines[0]) - len(lines[0].lstrip())
        fields: dict[str, str] = {}
        for i, line in enumerate(lines):
            if key := re.match(rf"^ {{{indent}}}(name|run):\s*(.*)$", line):
                value = key.group(2).strip()
                fields[key.group(1)] = _block_scalar(lines[i + 1 :], indent) if value[:1] in {"|", ">"} else _unquoted(value)
        steps.append(_Step(job, fields.get("name", ""), fields.get("run", "")))
    return steps


_MANIFESTS = (
    r"(?:[\w./-]*/)?(?:pyproject\.toml|uv\.lock|poetry\.lock|requirements[\w.-]*\.txt|package\.json|package-lock\.json|yarn\.lock|"
    r"pnpm-lock\.yaml|Cargo\.toml|Cargo\.lock|go\.mod|go\.sum|Directory\.Packages\.props|packages\.lock\.json|[\w.-]+\.csproj)"
)
_WRITES_MANIFEST = re.compile(
    rf"\bsed\b[^\n]*\s-[A-Za-z]*i\b[^\n]*{_MANIFESTS}|\btee\b[^\n]*{_MANIFESTS}|>>?\s*{_MANIFESTS}", re.IGNORECASE
)
# Each rewrites the lockfile unless told not to; the installing form that fails on a stale lock is named in the remediation.
_LOCK_REWRITERS = (
    (re.compile(r"^uv (?:lock|sync)\b"), re.compile(r"--(?:check|locked|frozen)\b"), "uv lock/sync without --locked or --frozen"),
    (re.compile(r"^uv (?:add|remove)\b"), None, "uv add/remove"),
    (re.compile(r"^poetry (?:lock|update|add)\b"), None, "poetry lock/update/add"),
    (re.compile(r"^npm (?:install|i|update)(?:\s+-{1,2}[\w-]+)*$"), re.compile(r"\s(?:-g|--global)\b"), "npm install instead of npm ci"),
    (re.compile(r"^cargo update\b"), None, "cargo update"),
)


def _rewrites(run_text: str) -> str | None:
    """What in a step's shell text rewrites the dependency set, or None."""
    if written := _WRITES_MANIFEST.search(run_text):
        target = re.search(_MANIFESTS, written.group(0), re.IGNORECASE)
        return f"writes {target.group(0) if target else 'a manifest or lockfile'}"
    for raw in re.split(r"&&|\|\||;|\n", run_text):
        command = raw.strip()
        for starts, exempt, label in _LOCK_REWRITERS:
            if starts.match(command) and not (exempt and exempt.search(command)):
                return label
    return None


def ci_no_manifest_edit(ctx: Context) -> Finding:
    """CI gates the committed dependency set: a step ahead of `just check` that edits pyproject.toml or re-locks gates another one."""
    files = workflows(ctx)
    if not files:
        return not_applicable("no .github/workflows: gate.ci reports the missing CI")
    parsed = {f.name: _steps(f.read_text()) for f in files}
    gated = any(_GATE_RUN.search(step.run) for steps in parsed.values() for step in steps)
    found: list[str] = []
    for name, steps in parsed.items():
        for job in dict.fromkeys(step.job for step in steps):
            job_steps = [step for step in steps if step.job == job]
            gate_at = next((i for i, step in enumerate(job_steps) if _GATE_RUN.search(step.run)), None)
            if gate_at is None and gated:
                continue  # another job is the gate; this one gates nothing
            found += [
                f"{name} job {job} step {step.name or step.run.splitlines()[0][:40]!r}: {what}"
                for step in job_steps[:gate_at]
                if (what := _rewrites(step.run)) is not None
            ]
    if found:
        return failing(
            "; ".join(found),
            "commit the change instead of patching it in CI; install with the locked form (`uv sync --locked`, `npm ci`)",
        )
    return passing(f"{len(files)} workflow(s): no step before the gate edits a manifest or re-locks")


_GITHUB_REMOTE = re.compile(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?/?$")


def _head_runs(ctx: Context) -> tuple[str, str, dict[str, dict[str, str]]] | Finding:
    """(branch, head sha, the latest run per workflow on that sha), or the reason they cannot be read."""
    found = _GITHUB_REMOTE.search((ctx.git("remote", "get-url", "origin") or "").strip())
    if found is None:
        return not_checked("origin is not a GitHub repository; this row reads GitHub Actions")
    slug = found.group(1)
    branch = (ctx.git("symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD") or "origin/main").strip().removeprefix("origin/")
    fields = "workflowName,headSha,status,conclusion,event"
    done = ctx.run("gh", "run", "list", "--repo", slug, "--branch", branch, "--limit", "30", "--json", fields, timeout=60)
    if done is None or done.returncode != 0:
        why = (done.stderr.strip().splitlines() or ["no output"])[-1] if done else "gh is not installed or timed out"
        return not_checked(f"gh could not list the runs ({why}): `gh auth login` once on this machine")
    # Dependabot's own update runs (event `dynamic`) are not the repo's CI.
    runs = [r for r in json.loads(done.stdout or "[]") if r.get("event") != "dynamic"]
    if not runs:
        return not_checked(f"no CI runs on {branch} yet")
    # The pushed tip, as this clone last fetched it: right after a push the newest run is the previous commit's.
    head = (ctx.git("rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}") or "").strip() or runs[0]["headSha"]
    if not any(r["headSha"] == head for r in runs):
        return not_checked(f"no CI run on {head[:7]} yet; `gh run watch` once it starts, and re-run")
    latest: dict[str, dict[str, str]] = {}
    for r in runs:
        if r["headSha"] == head:
            latest.setdefault(r["workflowName"], r)
    return branch, head, latest


def ci_green(ctx: Context) -> Finding:
    """A repo blueprint passes can still be red where it ships: the shelf's own CI failed every push for hours unread.

    Read through `gh` (logged in once per machine).
    """
    if not workflows(ctx):
        return not_applicable("no GitHub Actions workflows")
    read = _head_runs(ctx)
    if not isinstance(read, tuple):
        return read
    branch, head, latest = read
    going = [name for name, r in latest.items() if r["status"] != "completed"]
    if going:
        return not_checked(f"{', '.join(going)} still running on {head[:7]}; `gh run watch` and re-run")
    red = [f"{name} ({r['conclusion']})" for name, r in latest.items() if r["conclusion"] != "success"]
    if red:
        fix = "`gh run view --log-failed` on the red run; fix it before anything else ships"
        return failing(f"{branch} {head[:7]}: {', '.join(red)}", fix)
    return passing(f"{branch} {head[:7]}: {', '.join(latest)} green")
