"""The corpus diff: what a blueprint release changes for the repositories it judges."""

import subprocess
import sys
from pathlib import Path

from tools.corpus_diff import corpus_diff


def test_moved_names_every_row_whose_verdict_differs_or_that_one_engine_lacks():
    old = {"a": "passing", "b": "failing", "c": "passing"}
    new = {"a": "passing", "b": "passing", "d": "failing"}
    assert corpus_diff.moved(old, new) == ["b: failing -> passing", "c: passing -> absent", "d: absent -> failing"]


def test_the_report_prints_changes_and_counts_the_rest():
    results = {
        "same": ({"a": "passing"}, {"a": "passing"}),
        "worse": ({"a": "passing", "b": "passing"}, {"a": "passing", "b": "failing"}),
        "broken": None,
    }
    lines = corpus_diff.report(results, ["gone"])
    assert lines == [
        "broken: not judged (engine failed or timed out)",
        "worse: 2 -> 1 passing of 2",
        "  b: passing -> failing",
        "unchanged: 1 of 3 repos; not on this machine: gone",
    ]


def test_one_engine_against_itself_changes_nothing(tmp_path: Path, capsys):
    shelf = Path(__file__).resolve().parent.parent
    repo = tmp_path / "corpus" / "tiny"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "pyproject.toml").write_text('[project]\nname = "tiny"\nversion = "0.1.0"\n', encoding="utf-8")
    corpus = tmp_path / "corpus.toml"
    corpus.write_text('repos = ["tiny", "absent"]\n', encoding="utf-8")
    code = corpus_diff.main(
        ["--repo", str(shelf), "--base", "HEAD", "--head", "HEAD", "--corpus", str(corpus), "--root", str(tmp_path / "corpus")]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert out.strip() == "unchanged: 1 of 1 repos; not on this machine: absent"


def test_help_exits_zero_and_prints_usage():
    done = subprocess.run([sys.executable, "-I", "tools/corpus_diff/corpus_diff.py", "--help"], capture_output=True, text=True, check=False)
    assert done.returncode == 0
    assert "usage" in done.stdout
