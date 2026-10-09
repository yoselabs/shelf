"""Trust a folder's files on this machine, direnv-style.

A folder that came from somewhere else — a cloned repository, a synced vault — may carry
code that runs when it is opened. It stays inert until someone on this machine grants it.
The grant records a hash over the folder's matching files, so editing one, adding one or
removing one revokes it without anyone saying so: the next check sees a different hash.

The grant store is one YAML mapping, ``{resolved key path: hex digest}``, written
atomically. It belongs outside the folder it vouches for, or the folder could vouch for
itself.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import tempfile
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

__all__ = ["TrustStore", "TrustStoreError", "folder_hash"]

_yaml = YAML(typ="safe")


class TrustStoreError(Exception):
    """The grant store exists but cannot be read or written. ``path`` names it."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"trust store {path} is unusable: {reason}")
        self.path = path


def folder_hash(folder: Path, pattern: str = "*") -> str:
    """SHA-256 over the files in ``folder`` matching ``pattern`` (not recursive).

    Files are taken in name order, so the digest does not depend on the order the
    filesystem lists them; each file's bytes follow its name and a NUL, so moving bytes
    from one file to the next changes the digest. A missing or empty folder has one fixed
    digest. Folders that match the pattern are skipped.
    """
    h = hashlib.sha256()
    if folder.exists():
        for path in sorted(folder.glob(pattern), key=lambda p: p.name):
            if not path.is_file():
                continue
            h.update(path.name.encode("utf-8"))
            h.update(b"\0")
            h.update(path.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


class TrustStore:
    """The machine-local grant store: one YAML file mapping a key path to a folder hash.

    ``key`` names what is trusted (a vault, a checkout) and is stored resolved, so two
    spellings of one path share a grant. ``folder`` is what is hashed; it is usually inside
    ``key``. ``pattern`` picks the files that count and must be the same on grant and check.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def grant(self, key: Path, folder: Path, *, pattern: str = "*") -> None:
        """Trust ``folder`` as it is now, under ``key``. A later edit revokes it."""
        data = self._load()
        data[str(key.resolve())] = folder_hash(folder, pattern)
        self._save(data)

    def revoke(self, key: Path) -> bool:
        """Forget ``key``'s grant; ``True`` when there was one."""
        data = self._load()
        removed = data.pop(str(key.resolve()), None)
        self._save(data)
        return removed is not None

    def is_trusted(self, key: Path, folder: Path, *, pattern: str = "*") -> bool:
        """``True`` only when ``key`` has a grant and ``folder`` still hashes to it."""
        recorded = self._load().get(str(key.resolve()))
        return recorded is not None and recorded == folder_hash(folder, pattern)

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            data = _yaml.load(self._path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, YAMLError) as exc:
            raise TrustStoreError(self._path, str(exc)) from exc
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}

    def _save(self, data: dict[str, str]) -> None:
        # Atomic: a torn write leaves every granted folder looking untrusted.
        buf = io.StringIO()
        _yaml.dump(data, buf)
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            _write_atomic(self._path, buf.getvalue())
        except OSError as exc:
            raise TrustStoreError(self._path, str(exc)) from exc


def _write_atomic(path: Path, text: str) -> None:
    """Temp file beside ``path``, fsync, rename over it. Not atomic-io: a sibling
    dependency would put a workspace source in front of every git consumer's own pin."""
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        tmp.replace(path)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
