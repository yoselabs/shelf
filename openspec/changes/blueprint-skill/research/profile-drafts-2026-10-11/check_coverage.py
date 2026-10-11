"""Fail when merged coverage is under the committed floor. Floor only rises: raise it in the same commit that earns it.

Usage: python3 tools/check_coverage.py cov/Summary.json coverage-floor.json
coverage-floor.json: {"line": 89.0, "branch": 75.0}
"""

import json
import sys

summary = json.load(open(sys.argv[1]))["summary"]  # noqa: SIM115 -- one-shot script
floor = json.load(open(sys.argv[2]))  # noqa: SIM115
actual = {"line": summary["linecoverage"], "branch": summary["branchcoverage"]}
bad = [f"{k} coverage {actual[k]}% < floor {v}%" for k, v in floor.items() if actual[k] < v]
print("coverage: " + ", ".join(f"{k} {actual[k]}% (floor {floor[k]}%)" for k in floor))
if bad:
    sys.exit("coverage below floor: " + "; ".join(bad))
