"""Hook scripts, their verbose output, and the value helpers shared by the contract steps."""

from __future__ import annotations

import dataclasses

from git_porcelain import Change

_COMMIT_STDOUT = "stdout-start\n" + "x" * 1024 + "\nstdout-end\n"
_COMMIT_STDERR = "stderr-start\n" + "y" * 1024 + "\nstderr-end\n"
_COMMIT_FAILURE_STDERR = "error: gpg failed to sign the data\n" + _COMMIT_STDERR


def _hook_script(kind: str, mode: str) -> str:
    if mode == "error only":
        return "echo 'error: nope' >&2\nexit 1\n"
    if mode == "silent":
        return "exit 1\n"
    if mode.startswith("verbose"):
        code = 1 if mode.endswith("refuses") else 0
        return f"printf '%s' '{_COMMIT_STDOUT}'\nprintf '%s' '{_COMMIT_STDERR}' >&2\nexit {code}\n"
    if mode == "refuses":
        return f"echo '{kind} hook declined' >&2\nexit 1\n"
    return '[ "$X" = "1" ] || { echo "X is not set" >&2; exit 1; }\n'


def _plain(item: object) -> object:
    if isinstance(item, Change):
        return f"{item.path} {item.kind} +{item.added} -{item.deleted}"
    if dataclasses.is_dataclass(item) and not isinstance(item, type):
        return {f.name: _plain(getattr(item, f.name)) for f in dataclasses.fields(item)}
    if isinstance(item, (frozenset, set)):
        return sorted(_plain(i) for i in item)  # type: ignore[type-var]
    if isinstance(item, (list, tuple)):
        return [_plain(i) for i in item]
    return str(item) if hasattr(item, "parts") else item


def _dig(value: object, path: str) -> object:
    for part in path.split("."):
        value = value[int(part)] if part.isdigit() else getattr(value, part)  # type: ignore[index]
    return value
