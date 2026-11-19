"""Vendor shelf packages into a directory, byte-identical to a shelf tag, and prove they have not drifted.

Git-pinned dependencies do not work for a plugin's skill directory, so a plugin copies the package source. This is the
one tool for that copy (it replaced two diverging ``dev/vendor.py`` files). Sunset: remove it, and every ``_vendor/``
directory, when plugins can depend on the shelf directly.

A manifest is a JSON list of ``{name, shelf_tag, shelf_commit, tree_hash}``. ``sync`` reads files with ``git archive``
from the tag, never from the shelf working tree. ``check`` recomputes each vendored tree's hash; with a shelf it also
hashes the tag's own content and warns (never fails) when a newer shelf tag of that package exists.

``tree_hash`` is sha256 over each file in sorted POSIX relative path order: path utf-8, NUL, decimal byte length, NUL,
the bytes. ``__pycache__`` directories and ``*.pyc`` are skipped.

Standard library only; POSIX.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Vendor", "dir_files", "newer_tags", "tag_files", "tree_hash"]

_VERSION = re.compile(r"-v(\d+(?:\.\d+)*)$")


def tree_hash(files: dict[str, bytes]) -> str:
    """The hex sha256 of ``{relative posix path: bytes}``; the definition is in the module docstring."""
    h = hashlib.sha256()
    for rel in sorted(files):
        data = files[rel]
        h.update(rel.encode("utf-8") + b"\0" + str(len(data)).encode() + b"\0" + data)
    return h.hexdigest()


def dir_files(path: Path) -> dict[str, bytes]:
    """The files under ``path`` as ``{relative posix path: bytes}``, without bytecode caches."""
    return {
        p.relative_to(path).as_posix(): p.read_bytes()
        for p in sorted(path.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    }


def _git(shelf: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(shelf), *args], check=True, capture_output=True).stdout


def tag_files(shelf: Path, name: str, tag: str) -> dict[str, bytes]:
    """``{relative path: bytes}`` of ``packages/<dir>/src/<name>/`` at ``tag`` (dir is the import name with dashes)."""
    prefix = f"packages/{name.replace('_', '-')}/src/{name}"
    raw = _git(shelf, "archive", tag, prefix)
    out: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        for m in tar.getmembers():
            member = tar.extractfile(m) if m.isfile() else None
            if member is not None and m.name.startswith(prefix + "/"):
                out[m.name[len(prefix) + 1 :]] = member.read()
    if not out:
        msg = f"no files at {tag}:{prefix}"
        raise ValueError(msg)
    return out


def _version_key(tag: str, stem: str) -> tuple[int, ...] | None:
    m = _VERSION.search(tag)
    return tuple(int(x) for x in m.group(1).split(".")) if m and tag == stem + m.group(0) else None


def newer_tags(shelf: Path, name: str, tag: str) -> list[str]:
    """Version tags ``<package>-vX.Y.Z`` of the package that the recorded tag does not already contain, oldest first.

    ``tag`` may be a version tag or a bare commit: a tag counts as newer when it is not an ancestor of it (and, for a
    version tag, has a higher version).
    """
    stem = name.replace("_", "-")
    found = sorted(
        (key, t) for t in _git(shelf, "tag", "--list", f"{stem}-v*").decode().split() if (key := _version_key(t, stem)) is not None
    )
    have = _version_key(tag, stem)
    out: list[str] = []
    for key, t in found:
        if have is not None:
            if key > have:
                out.append(t)
        elif subprocess.run(["git", "-C", str(shelf), "merge-base", "--is-ancestor", t, tag], check=False).returncode:
            out.append(t)
    return out


def _install(dest: Path, files: dict[str, bytes]) -> None:
    """Replace ``dest`` by ``files``: build the new tree in a sibling directory, then rename it into place.

    A failure while building leaves ``dest`` as it was. Two renames swap the trees (the old one is parked first), so a
    crash between them leaves ``dest`` absent and the old tree beside it as ``.<name>.old-*``, never a half-copied tree.
    Standard library only, so this is not atomic-io (this package vendors itself and must stay copyable alone).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{dest.name}.new-", dir=dest.parent))
    parked = stage.with_name(stage.name.replace(".new-", ".old-", 1))
    try:
        for rel, data in files.items():
            target = stage / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            _ = target.write_bytes(data)
        if dest.is_dir():
            dest.rename(parked)
        stage.rename(dest)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        if parked.is_dir() and not dest.exists():
            parked.rename(dest)
        raise
    shutil.rmtree(parked, ignore_errors=True)


def _write_text_atomic(path: Path, text: str) -> None:
    """Write ``text`` (UTF-8) beside ``path`` under a private name, then rename it over ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        _ = tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


@dataclass(frozen=True)
class Vendor:
    """One consumer: where the copies go (``vendor_dir``) and the manifest that records them (``manifest_path``)."""

    vendor_dir: Path
    manifest_path: Path

    def load(self) -> list[dict[str, str]]:
        if not self.manifest_path.is_file():
            return []
        entries: list[dict[str, str]] = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return entries

    def sync(self, name: str, tag: str | None = None, *, shelf: Path) -> dict[str, str]:
        """Copy ``name`` from ``tag`` (default: the recorded one) and record it. ``process-lock`` is ``process_lock``."""
        name = name.replace("-", "_")
        entries = self.load()
        old = next((e for e in entries if e["name"] == name), None)
        tag = tag or (old or {}).get("shelf_tag")
        if not tag:
            msg = f"no recorded tag for {name}; pass one"
            raise ValueError(msg)
        commit = _git(shelf, "rev-parse", tag + "^{commit}").decode().strip()
        files = tag_files(shelf, name, tag)
        _install(self.vendor_dir / name, files)
        entry = {"name": name, "shelf_tag": tag, "shelf_commit": commit, "tree_hash": tree_hash(files)}
        kept = [e for e in entries if e["name"] != name]
        text = json.dumps(sorted([*kept, entry], key=lambda e: e["name"]), indent=2) + "\n"
        _write_text_atomic(self.manifest_path, text)
        return entry

    def check(self, shelf: Path | None = None) -> tuple[list[str], list[str]]:
        """``(drift, warnings)``. Drift: a missing tree, a tree whose hash differs from the manifest, a tag whose own
        content differs from it (with a shelf). Warnings: newer shelf tags (with a shelf)."""
        drift: list[str] = []
        warnings: list[str] = []
        for e in self.load():
            path = self.vendor_dir / e["name"]
            if not path.is_dir():
                drift.append(f"{e['name']}: {path} is missing")
                continue
            got = tree_hash(dir_files(path))
            if got != e["tree_hash"]:
                drift.append(f"{e['name']}: vendored tree hash {got[:12]} != recorded {e['tree_hash'][:12]}")
            if shelf is not None:
                want = tree_hash(tag_files(shelf, e["name"], e["shelf_tag"]))
                if want != e["tree_hash"]:
                    drift.append(f"{e['name']}: tag {e['shelf_tag']} content hash {want[:12]} != recorded {e['tree_hash'][:12]}")
                newer = newer_tags(shelf, e["name"], e["shelf_tag"])
                if newer:
                    warnings.append(f"{e['name']}: newer shelf tag {newer[-1]} exists (recorded {e['shelf_tag']})")
        return drift, warnings
