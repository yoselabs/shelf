"""Append an item to a top-level block list of a YAML file as text: what is above the new item is never rewritten, so
Git sees one added block and a ledger that must stay append-only can be checked by prefix."""

import re
from pathlib import Path

from atomic_io import atomic_write_text
from ruamel.yaml.error import YAMLError

from any_yaml.read import load
from any_yaml.write import dump

_ITEM = re.compile(r"^( *)- ")


def _is_top_key(line: str, key: str) -> bool:
    return re.match(rf"^(?:{re.escape(key)}|\"{re.escape(key)}\"|'{re.escape(key)}'):(?:\s|$)", line) is not None


def _block_end(lines: list[str], start: int) -> int:
    """Index after the last content line of the block that starts below line `start`."""
    end = start + 1
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        if line[0] not in " -#\t":
            break
        if line[0] != "#":
            end = index + 1
    return end


def append_item(text: str, key: str, item: object) -> str:
    """`text` with `item` added as the last entry of the top-level list `key` (created at the end when absent).

    Item lines take the indentation the list already uses (two spaces when it is new). Raises TypeError when the document is
    not a mapping or `key` holds a non-list, ValueError when its list is not a block list (`[a, b]`)."""
    document = load(text) if text.strip() else dict[str, object]()
    if not isinstance(document, dict):
        message = "append_item: the document is not a mapping"
        raise TypeError(message)
    current = document.get(key)
    if current is not None and not isinstance(current, list):
        message = f"append_item: {key!r} is not a list"
        raise TypeError(message)
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    at = next((i for i, line in enumerate(lines) if _is_top_key(line, key)), None)
    if at is None:
        lines.append(f"{key}:\n")
        at = len(lines) - 1
    elif current is not None and not current:
        lines[at] = f"{key}:\n"
    end = _block_end(lines, at)
    found = next((m for m in map(_ITEM.match, lines[at + 1 : end]) if m), None)
    indent = found.group(1) if found else "  "
    block = [f"{indent}{line}\n" if line else "\n" for line in dump([item]).splitlines()]
    result = "".join(lines[:end] + block + lines[end:])
    try:
        extended = load(result) == {**document, key: [*(current or []), item]}
    except YAMLError:
        extended = False
    if not extended:
        message = f"append_item: {key!r} is not a block list this can extend"
        raise ValueError(message)
    return result


def append_item_file(path: Path, key: str, item: object, *, initial: str = "") -> None:
    """`append_item` on the file at `path` (atomically); a missing file starts from `initial`, e.g. `format: 1\\n`."""
    text = path.read_text(encoding="utf-8") if path.exists() else initial
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, append_item(text, key, item), keep_mode=True)
