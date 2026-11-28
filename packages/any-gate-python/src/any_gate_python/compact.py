"""Compact pytest output for a gate: the full stream goes to a log file, the console gets what a reader acts on.

A red run of 57 failures prints ~460 KB of tracebacks, captured output and warnings. What the reader needs is the list of failing test
ids with their one-line cause, the totals, and where the rest is. Few failures (<= `SHOW_BELOW`) keep their tracebacks: there the
detail is the answer. `ANY_GATE_FULL=1` prints everything, as before.

The full stream is written beside its final name and takes that name only when the run failed: a green retry never overwrites the log
of the red run (the one place the assertion text of a failure that did not repeat stays). The note names the log and shows the head of
the first failure, so the gate's own kept log holds a real assertion, not only totals.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_HEADER = re.compile(r"^=+ (?P<name>.+?) =+\s*$")
_HIDDEN = ("FAILURES", "ERRORS", "warnings summary")
_OUTCOME = re.compile(r"^(?:FAILED|ERROR) ")
SHOW_BELOW = 4  # up to this many failures the tracebacks stay on the console
MAX_LINE = 220
MAX_DETAIL = 150  # lines of kept traceback
FIRST_FAILURE = 15  # lines of the first failure shown when the rest is held back


class Compact:
    """Feed every output line; `finish()` writes what was held back, if it earned a place."""

    def __init__(self, write: Callable[[str], None], log: Path) -> None:
        self._write = write
        self._part = log.with_name(f"{log.name}.{os.getpid()}.part")
        self._log = self._part.open("w", encoding="utf-8")
        self.log_path = log
        self._hiding = False
        self._held: list[str] = []
        self._hidden_lines = 0
        self._failures = 0

    def feed(self, line: str) -> None:
        self._log.write(line)
        header = _HEADER.match(line)
        if header:
            self._hiding = header.group("name") in _HIDDEN
        if self._hiding:
            self._hidden_lines += 1
            if len(self._held) < 4 * MAX_DETAIL:
                self._held.append(line)
            return
        if _OUTCOME.match(line):
            self._failures += 1
            if len(line) > MAX_LINE:
                line = line[: MAX_LINE - 1] + "…\n"
        self._write(line)

    def finish(self) -> None:
        self._log.close()
        if self._failures or self._hidden_lines:
            self._part.replace(self.log_path)
        else:
            self._part.unlink(missing_ok=True)
        if not self._hidden_lines:
            return
        if 0 < self._failures <= SHOW_BELOW:
            self._write("".join(self._held[:MAX_DETAIL]))
            return
        self._write(self._first_failure())
        self._write(
            f"any-gate-python: {self._hidden_lines} lines of tracebacks and warnings held back; "
            f"full output: {self.log_path} (ANY_GATE_FULL=1 prints it all)\n"
        )

    def _first_failure(self) -> str:
        """The head of the first failure's block (from its `___ name ___` line to the next one): what it asserted, as the log keeps it."""
        block: list[str] = []
        for line in self._held:
            if line.startswith("_") and block:
                break
            if not _HEADER.match(line) and (block or line.startswith("_")):
                block.append(line)
        return "".join(block[:FIRST_FAILURE])
