"""Stop caring how a markdown file's YAML frontmatter is read, written and versioned.

- :mod:`any_frontmatter.document` — parse and dump keeping the author's comments, one
  error for every malformation, an atomic write.
- :mod:`any_frontmatter.version` — a content-hash version stable across layout, and a
  write that refuses a stale one.
- :mod:`any_frontmatter.coerce` — reads of untyped values that never raise.
"""

from __future__ import annotations

from any_frontmatter.coerce import opt_str, str_seq, written_nothing
from any_frontmatter.document import FENCE, Document, FrontmatterError, dump, parse, read, round_trip_yaml, write
from any_frontmatter.version import (
    StaleVersionError,
    WriteOutcome,
    canonicalize,
    check_version,
    compute_version,
    version_of,
    version_of_file,
    write_checked,
)

__all__ = [
    "FENCE",
    "Document",
    "FrontmatterError",
    "StaleVersionError",
    "WriteOutcome",
    "canonicalize",
    "check_version",
    "compute_version",
    "dump",
    "opt_str",
    "parse",
    "read",
    "round_trip_yaml",
    "str_seq",
    "version_of",
    "version_of_file",
    "write",
    "write_checked",
    "written_nothing",
]
