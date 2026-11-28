"""The suite is deaf to the hook that runs it: a pre-push hook's environment must not change what a throwaway repo's gate decides.

2026-11-28: under the pre-push hook `PRE_COMMIT_TO_REF` (the sha being pushed) reached the `any_gate steps` these tests spawn in a
throwaway clone; `GateState.green` then saw a push of some other commit, answered "no gate passed this tree", and 13 tests in
test_inputs.py failed (`assert ['tag-check'] == []`). Run alone, without the hook's variables, they passed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
HOOK = {
    "PRE_COMMIT": "1",
    "PRE_COMMIT_TO_REF": "0" * 39 + "1",
    "PRE_COMMIT_FROM_REF": "0" * 40,
    "GATE_FAIL_FAST": "1",
    "GATE_SLOTS": "0",
}


def test_the_golden_inputs_tests_pass_under_a_pre_push_hooks_environment() -> None:
    target = f"{HERE / 'test_inputs.py'}::test_a_skipped_step_is_reported_as_a_skipped_line"
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider", "-p", "no:xdist", target],
        env={**os.environ, **HOOK, "ANY_GATE_LEASED": str(os.getpid())},
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout[-1500:]
