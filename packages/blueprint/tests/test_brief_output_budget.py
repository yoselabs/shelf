"""`blueprint check --brief` stays short per failing row however long the evidence and the fix, and says nothing when nothing fails."""

from __future__ import annotations

from blueprint.testing import Repo, run_cli

PER_ROW = 500  # bytes one non-passing row may take in the brief form (a2web: 52 rows took 11.9 KB, 229 each)


def test_the_brief_form_takes_at_most_500_bytes_per_failing_row(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\nversion = "0.1.0"\n')
    done = run_cli(["check", "--repo", str(repo.root), "--brief"], cwd=repo.root)
    rows = [ln for ln in done.stdout.splitlines() if ln.startswith(("blueprint: ❌", "blueprint: ⚠"))]
    assert len(rows) >= 5, done.stdout  # a bare python repo fails several rows, or this test measures nothing
    assert len(done.stdout) <= 120 + PER_ROW * len(rows)
    assert max(len(ln.encode()) for ln in rows) <= PER_ROW + 100
