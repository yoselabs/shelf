"""A tiny worker for the suite: `_worker.py MODE [args]`. It says `ready` when its signal handling is set."""

import os
import signal
import sys
import time
from pathlib import Path

if Path("FAIL").exists():
    sys.exit(3)
mode = sys.argv[1]
if mode == "stubborn":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
if mode == "env":
    print("index", os.environ["ANY_SUPERVISE_INDEX"], "count", os.environ["ANY_SUPERVISE_COUNT"], "argv", sys.argv[2:], flush=True)
    print(
        "extra", os.environ.get("EXTRA"), "leak", os.environ.get("CLAUDE_CODE_TEST_LEAK"), "passed", os.environ.get("PASSED_ON"), flush=True
    )
print("ready", flush=True)
deadline = time.monotonic() + 120  # a test that dies without its teardown leaves nothing behind for long
while time.monotonic() < deadline:
    if mode == "chatty":
        print("tick" * 20, flush=True)
    time.sleep(0.01 if mode == "chatty" else 0.1)
