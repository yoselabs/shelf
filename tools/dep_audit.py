#!/usr/bin/env python3
"""No locked dependency has a known vulnerability, except the ones `tools/dep_audit_exceptions.toml` allows until a date.

Runs `pip-audit` over the exported `uv.lock` (workspace packages left out: they are ours). An advisory fails the step unless an
`[[exception]]` names its package and id, with a reason, and its `until` date has not passed. Past the date the entry covers nothing and
is named; an entry whose advisory is no longer reported (the package was upgraded) fails too, so the list never outlives the need. The
gate runs it when `uv.lock` or a `pyproject.toml` changed, and always in `just check-all`. Offline, pip-audit cannot ask: that is said and
the step passes. Stdlib only, so it runs as bare `python3 -I`; `pip-audit` and `uv` run through `uv run`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import tomllib
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

EXCEPTIONS = Path(__file__).with_name("dep_audit_exceptions.toml")
TIMEOUT = 600.0  # seconds one tool may take: the advisory service on a dead network must not hang a push


def advisories(report: dict[str, Any]) -> dict[tuple[str, str], set[str]]:
    """{(package, version): advisory ids} of what pip-audit's JSON reports."""
    found: dict[tuple[str, str], set[str]] = {}
    for dep in report.get("dependencies", []):
        ids = {v["id"] for v in dep.get("vulns", [])}
        if ids:
            found[(dep["name"], dep["version"])] = ids
    return found


def problems(found: dict[tuple[str, str], set[str]], exceptions: list[dict[str, Any]], today: date) -> list[str]:
    """The lines to print: advisories nothing covers, expired entries, and entries that cover nothing now."""
    out: list[str] = []
    live: dict[tuple[str, str], set[str]] = {}  # what a still-valid entry covers
    for entry in exceptions:
        key = (str(entry["package"]), str(entry["version"]))
        until = entry["until"]
        reported = found.get(key, set())
        covers = set(entry["ids"])
        if not str(entry.get("reason", "")).strip():
            out.append(f"{key[0]} {key[1]}: an exception needs a reason")
        if until < today:
            out.append(f"{key[0]} {key[1]}: the exception ran out on {until}; upgrade the package, or extend it with a reason")
        else:
            live.setdefault(key, set()).update(covers)
        stale = sorted(covers - reported)
        if stale:
            out.append(f"{key[0]} {key[1]}: {', '.join(stale)} no longer reported; delete them from the exception")
    for (name, version), ids in sorted(found.items()):
        uncovered = sorted(ids - live.get((name, version), set()))
        if uncovered:
            out.append(f"{name} {version}: {len(uncovered)} known vulnerabilities, none allowed: {', '.join(uncovered)}")
    return out


def audit(repo: Path) -> dict[str, Any] | None:
    """pip-audit's JSON report for `repo`'s lock, or None when it could not ask (no network)."""
    export = ["uv", "export", "--frozen", "--no-hashes", "--all-packages", "--no-emit-workspace", "--quiet"]
    locked = subprocess.run(export, cwd=repo, capture_output=True, text=True, check=True, timeout=TIMEOUT).stdout
    with tempfile.TemporaryDirectory() as tmp:
        req = Path(tmp) / "requirements.txt"
        req.write_text(locked, encoding="utf-8")
        cmd = ["uv", "run", "pip-audit", "-r", str(req), "--no-deps", "--disable-pip", "--format", "json"]
        try:
            done = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=False, timeout=TIMEOUT)
            report = json.loads(done.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            return None
    return report if isinstance(report, dict) else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--exceptions", type=Path, default=EXCEPTIONS)
    parser.add_argument("--today", type=date.fromisoformat, default=date.today(), help="the date the exceptions are judged on")  # noqa: DTZ011
    args = parser.parse_args(argv)
    report = audit(args.repo)
    if report is None:
        sys.stderr.write("dep-audit: could not ask the advisory service (offline?); nothing checked\n")
        return 0
    table = tomllib.loads(args.exceptions.read_text(encoding="utf-8")) if args.exceptions.is_file() else {}
    bad = problems(advisories(report), table.get("exception", []), args.today)
    for line in bad:
        sys.stderr.write(f"dep-audit: {line}\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
