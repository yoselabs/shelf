"""Property-based tests, additive on top of test_atomic_io.py.

See docs/runbooks/property-based-testing.md. Round-trip and no-temp-file-left-behind
are genuine independent checks (they compare Hypothesis's input against a real
filesystem read/listing, not against the function's own intermediate output), not
tautologies — the failure mode that runbook warns about doesn't apply here. Uses a
fresh `tempfile.TemporaryDirectory()` per example rather than pytest's `tmp_path`
fixture, which is function-scoped and not reset between Hypothesis examples.

Round-trip assertions read back with `Path.read_bytes()`, not `Path.read_text()`: a
first pass used `read_text()` and found a real, reproducible failure on `text='\\r'`
(read back as `'\\n'`) — not a bug in `atomic_write_text`, which writes the exact
bytes given, but Python's own universal-newline translation on text-mode *read*. The
function's docstring now says so explicitly; this suite checks the byte-level
guarantee the function actually makes.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from atomic_io import atomic_write_text
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# Deadline off: every example does real filesystem I/O (mkstemp, fsync, replace).
_IO_SETTINGS = settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])

_CONTENT = st.text(max_size=2000)  # includes unicode, empty string, control chars


@given(text=_CONTENT)
@_IO_SETTINGS
def test_property_write_then_read_round_trips(text: str) -> None:
    """For any generated string, what's written is exactly what's read back."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "note.txt"
        atomic_write_text(target, text)
        assert target.read_bytes() == text.encode("utf-8")


@given(first=_CONTENT, second=_CONTENT)
@_IO_SETTINGS
def test_property_second_write_fully_replaces_first(first: str, second: str) -> None:
    """Overwrite is total: no byte of the first write survives into the second read,
    for any pair of generated strings — not just the hand-picked v1/v2 example.
    """
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "note.txt"
        atomic_write_text(target, first)
        atomic_write_text(target, second)
        assert target.read_bytes() == second.encode("utf-8")


@given(text=_CONTENT)
@_IO_SETTINGS
def test_property_no_temp_file_left_behind_on_success(text: str) -> None:
    """The atomicity invariant, generalized: after ANY successful write, the
    directory contains exactly the target file — no `.{name}.*.tmp` survivor.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        target = tmp_path / "note.txt"
        atomic_write_text(target, text)
        leftovers = [p for p in tmp_path.iterdir() if p != target]
        assert leftovers == []


@given(depth=st.integers(min_value=1, max_value=5), text=_CONTENT)
@_IO_SETTINGS
def test_property_creates_parent_dirs_of_any_depth(depth: int, text: str) -> None:
    """Generalizes the single hand-picked nesting depth in the example test."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        for i in range(depth):
            target = target / f"level{i}"
        target = target / "note.txt"
        atomic_write_text(target, text)
        assert target.read_bytes() == text.encode("utf-8")
