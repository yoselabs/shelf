"""A markdown file as YAML frontmatter plus a body: parse, dump, and an atomic write.

The frontmatter is a fenced YAML block (``---`` lines) at the top of the file; everything
after the closing fence is the body. A file without a fence has empty frontmatter.

What a hand-rolled ``yaml.safe_load`` gets wrong, each kept here:

- **The author's comments and key order.** ``parse`` returns ruamel's round-trip map
  un-copied. Copying it into a plain ``dict`` deletes every comment a human wrote on the
  next write, silently.
- **A value with two spaces in a row.** A long plain scalar is wrapped on dump, and the
  line break reads back as one space, so the value changes. Such strings are written
  double-quoted.
- **Every malformation is one error.** An unclosed fence, a document that is not a
  mapping, and YAML the parser cannot read all raise :class:`FrontmatterError`, the
  parser's message and position kept and the parser's error chained. A caller built to
  survive one bad file in a walk needs to catch one type, not ruamel's too.
- **A failed dump does not poison the next one.** ruamel's emitter keeps its state when a
  value cannot be represented, and the next dump on that instance writes the frontmatter
  as an empty mapping. Every dump gets its own instance.
- **A crash never leaves half a file.** :func:`write` goes to a temp file beside the
  target, fsyncs, and renames over it.
"""

from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.representer import RoundTripRepresenter

if TYPE_CHECKING:
    from collections.abc import Mapping

FENCE = "---"


def _represent_str(representer: Any, data: str) -> Any:
    """A string holding two spaces in a row is written double-quoted: wrapped as a plain
    scalar, its line break would read back as one space and change the value."""
    if "  " in data:
        return representer.represent_scalar("tag:yaml.org,2002:str", data, style='"')
    return representer.represent_str(data)


class _Representer(RoundTripRepresenter):
    """ruamel's round-trip representer with the double-space rule. A subclass, because
    ``add_representer`` on ruamel's own class changes every round-trip dump in the process."""


_Representer.add_representer(str, _represent_str)


def round_trip_yaml() -> YAML:
    """A fresh ruamel round-trip instance configured as frontmatter is written: comments and
    quotes kept, 2/4/2 indent, the double-space rule. For a consumer dumping its own YAML
    files the same way. One instance per dump: see ``_LOADER``."""
    yaml = YAML(typ="rt")
    yaml.Representer = _Representer
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


#: Shared for reads. Never for writes: a dump that raises leaves ruamel's emitter half
#: way through a document, and the next dump on the same instance writes an empty mapping.
_LOADER = round_trip_yaml()


class FrontmatterError(ValueError):
    """The frontmatter is malformed: an unclosed fence, not a mapping, or unreadable YAML."""


@dataclass
class Document:
    """Frontmatter plus body. ``frontmatter`` is arbitrary user YAML, so it is untyped."""

    frontmatter: dict[str, Any]
    body: str

    def with_frontmatter(self, frontmatter: Mapping[str, Any], *, body: str | None = None) -> Document:
        """This document with its frontmatter replaced, keeping its comments.

        ``frontmatter`` is the COMPLETE new mapping, never a patch: a key it omits is
        removed. ``self.frontmatter`` donates the comments and nothing else, so pass
        ``{**doc.frontmatter, "k": v}``; ``{"k": v}`` would truncate the document.

        A plain dict carries none of ruamel's comment attachments, so building a
        ``Document`` from the payload directly drops the leading comment and every
        per-key trailing comment. Needs the ``merge`` extra (yaml-merge).
        """
        from yaml_merge import merge_into  # noqa: PLC0415 — the `merge` extra

        merged = cast("dict[str, Any]", merge_into(self.frontmatter, frontmatter))
        return Document(frontmatter=merged, body=self.body if body is None else body)


def parse(text: str) -> Document:
    """``text`` as frontmatter plus body. No opening fence means empty frontmatter."""
    if not text.startswith(FENCE):
        return Document(frontmatter={}, body=text)
    lines = text.splitlines(keepends=True)
    closing = next((i for i in range(1, len(lines)) if lines[i].rstrip("\n\r") == FENCE), None)
    if closing is None:
        msg = "unclosed frontmatter fence"
        raise FrontmatterError(msg)
    fm_text = "".join(lines[1:closing])
    body = "".join(lines[closing + 1 :]).removeprefix("\n")
    try:
        loaded: Any = _LOADER.load(fm_text) if fm_text.strip() else None
    except YAMLError as exc:
        msg = f"malformed frontmatter YAML: {exc}"
        raise FrontmatterError(msg) from exc
    parsed: Any = loaded if loaded is not None else {}
    if not isinstance(parsed, dict):
        msg = "frontmatter must be a YAML mapping"
        raise FrontmatterError(msg)
    # ruamel's CommentedMap as-is: a dict subclass, and the only carrier of comments.
    return Document(frontmatter=parsed, body=body)


def read(path: Path) -> Document:
    """The document in the file at ``path`` (UTF-8)."""
    return parse(path.read_text(encoding="utf-8"))


def dump(doc: Document) -> str:
    """``doc`` as file text. Empty frontmatter writes the body alone, with no fence."""
    if not doc.frontmatter:
        return doc.body
    buf = io.StringIO()
    round_trip_yaml().dump(doc.frontmatter, buf)  # a fresh dumper: see _LOADER
    fm = buf.getvalue()
    if not fm.endswith("\n"):
        fm += "\n"
    return f"{FENCE}\n{fm}{FENCE}\n{doc.body}"


def write(path: Path, doc: Document) -> None:
    """Write ``doc`` to ``path`` atomically, creating missing parent folders."""
    _write_atomic(path, dump(doc))


def _write_atomic(path: Path, text: str) -> None:
    """Temp file beside ``path``, fsync, rename over it. Inline, not atomic-io: a sibling
    dependency needs a workspace source, which collides with a consumer's own pin."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        Path(name).replace(path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
