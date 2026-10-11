#!/usr/bin/env python3
"""Fail when merged coverage is under the committed floor; the floor only rises, in the commit that earns it.

A blueprint recipe (`blueprint recipe dotnet-coverage > tools/check_coverage.py`): the repo copies it and owns the copy.
Reads ReportGenerator's JsonSummary, so it serves any stack whose reports ReportGenerator merges.

Usage: check_coverage.py cov/Summary.json coverage-floor.json   (coverage-floor.json: {"line": 89.0, "branch": 75.0})
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    """Compare the summary at argv[0] with the floor at argv[1]; exit 1 when any metric is under it."""
    summary = json.loads(Path(argv[0]).read_text())["summary"]
    floor: dict[str, float] = json.loads(Path(argv[1]).read_text())
    actual = {name: float(summary[f"{name}coverage"]) for name in floor}
    sys.stdout.write("coverage: " + ", ".join(f"{k} {actual[k]}% (floor {v}%)" for k, v in floor.items()) + "\n")
    bad = [f"{k} coverage {actual[k]}% < floor {v}%" for k, v in floor.items() if actual[k] < v]
    if bad:
        sys.stdout.write("coverage below floor: " + "; ".join(bad) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
