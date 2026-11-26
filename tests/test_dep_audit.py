"""The dependency audit: a known vulnerability fails unless an exception allows it until a date; the list never outlives the need."""

import subprocess
import sys
from datetime import date

from tools import dep_audit

TODAY = date(2026, 11, 26)


def entry(package="p", version="1.0", ids=("A-1",), until=date(2026, 12, 26), reason="not triaged"):
    return {"package": package, "version": version, "ids": list(ids), "until": until, "reason": reason}


def test_advisories_reads_the_ids_per_package_and_skips_clean_packages():
    report = {
        "dependencies": [
            {"name": "p", "version": "1.0", "vulns": [{"id": "A-1"}, {"id": "A-2"}]},
            {"name": "q", "version": "2", "vulns": []},
        ]
    }
    assert dep_audit.advisories(report) == {("p", "1.0"): {"A-1", "A-2"}}


def test_an_advisory_nothing_allows_fails_and_names_its_ids():
    out = dep_audit.problems({("p", "1.0"): {"A-1", "A-2"}}, [], TODAY)
    assert out == ["p 1.0: 2 known vulnerabilities, none allowed: A-1, A-2"]


def test_an_exception_with_a_reason_and_a_future_date_allows_its_ids():
    assert dep_audit.problems({("p", "1.0"): {"A-1"}}, [entry()], TODAY) == []


def test_an_expired_exception_allows_nothing_and_is_named():
    out = dep_audit.problems({("p", "1.0"): {"A-1"}}, [entry(until=date(2026, 11, 25))], TODAY)
    assert any("ran out on 2026-11-25" in line for line in out)
    assert any("none allowed: A-1" in line for line in out)


def test_the_last_day_still_counts():
    assert dep_audit.problems({("p", "1.0"): {"A-1"}}, [entry(until=TODAY)], TODAY) == []


def test_an_id_the_exception_does_not_name_still_fails():
    out = dep_audit.problems({("p", "1.0"): {"A-1", "A-2"}}, [entry(ids=("A-1",))], TODAY)
    assert out == ["p 1.0: 1 known vulnerabilities, none allowed: A-2"]


def test_an_exception_for_an_advisory_no_longer_reported_must_be_deleted():
    out = dep_audit.problems({}, [entry()], TODAY)
    assert out == ["p 1.0: A-1 no longer reported; delete them from the exception"]


def test_an_exception_without_a_reason_fails():
    out = dep_audit.problems({("p", "1.0"): {"A-1"}}, [entry(reason="  ")], TODAY)
    assert "p 1.0: an exception needs a reason" in out


def test_help_exits_zero_and_prints_usage():
    done = subprocess.run([sys.executable, "-I", "tools/dep_audit.py", "--help"], capture_output=True, text=True, check=False, timeout=60)
    assert done.returncode == 0
    assert "usage" in done.stdout
