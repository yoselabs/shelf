"""Writes: canonical block style for a new file, and a merge into the author's document that keeps their comments,
blank lines and key order (yaml-merge). The file writers replace the file atomically."""

import io
from pathlib import Path

from atomic_io import atomic_write_text
from ruamel.yaml import YAML
from yaml_merge import merge3, merge_into


def writer() -> YAML:
    yaml = YAML(typ="rt")
    yaml.width = 1000
    yaml.indent(mapping=2, sequence=2, offset=0)
    return yaml


def _text(yaml: YAML, data: object) -> str:
    out = io.StringIO()
    yaml.dump(data, out)
    return out.getvalue()


def dump(data: object) -> str:
    """A new file in one canonical block style, one field per line, so Git merges line by line."""
    return _text(writer(), data)


def merge_text(existing: str, data: object) -> str:
    """`data` written over the document `existing`: changed values change, everything the author wrote around them stays.

    A scalar `data` replaces the document."""
    yaml = writer()
    if isinstance(data, dict):
        return _text(yaml, merge_into(yaml.load(existing), data))
    if isinstance(data, list):
        return _text(yaml, merge_into(yaml.load(existing), data))
    return dump(data)


def merge3_text(base: str | None, ours: str | None, theirs: str | None) -> str | None:
    """A three-way merge of one file by entry id, keeping ours' comments; None when the merged file is gone.

    Raises MergeConflictError (with the path) when both sides changed one value differently."""
    yaml = writer()
    base_doc, ours_doc, theirs_doc = (None if text is None else yaml.load(text) for text in (base, ours, theirs))
    merged: object = merge3(base_doc, ours_doc, theirs_doc)
    return None if merged is None else _text(yaml, merged)


def write(path: Path, data: object) -> None:
    """Write `data` to `path` atomically: merged into the file when it exists (comments and order kept), else canonical."""
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    text = merge_text(existing, data) if existing.strip() else dump(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, text, keep_mode=True)
