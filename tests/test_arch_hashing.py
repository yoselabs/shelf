"""One hashing home: hashlib is imported by content-digest, plus the files below, each with its reason.

A file marked "consumer wave" still hand-rolls a hash content-digest can now produce; its migration deletes
the row. A legitimate row says why content-digest cannot be the door. md5 and sha1 are named in no other file.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

from any_arch import Row, Rule, check, plant

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent

_HASHLIB_IMPORTERS = {
    f"packages/{key}": Row(reason)
    for key, reason in {
        "any-failure-fp/src/any_failure_fp/fingerprint.py": "legitimate: sha1 suffix of a cut fingerprint is a key; sha256 would change it",
        "anyembed/src/anyembed/testing.py": "legitimate: raw digest bytes seed a fake vector, not an identity",
        "blueprint/src/blueprint/report.py": "legitimate: sha256[:12] fingerprints stored in written reports; stdlib-only engine",
        "blueprint/src/blueprint/gate_units.py": "legitimate: sha256[:32] test-unit key; stdlib-only engine",
        "blueprint/src/blueprint/runner.py": "legitimate: sha256[:12] checkpoint-set hash stored in reports; stdlib-only engine",
        "dir-trust/src/dir_trust/__init__.py": (
            "legitimate: incremental hash with NUL framing, kept in trust grants; no content-digest door"
        ),
        "git-porcelain/src/git_porcelain/fake_read.py": "legitimate: sha1 of the common dir is a stored local key",
        "git-porcelain/src/git_porcelain/fake_store.py": "legitimate: git's own blob and tree object id is sha1",
        "git-porcelain/src/git_porcelain/real_cache.py": "legitimate: sha1 change detector of working-tree content, not an identity",
        "git-porcelain/src/git_porcelain/real_read.py": "legitimate: sha1 of the common dir is a stored local key",
        "any-gate-python/src/any_gate_python/select.py": (
            "legitimate: incremental sha256 over a package's files, a receipt key; no stream door"
        ),
        "shelf-vendor/src/shelf_vendor/__init__.py": "legitimate: tree hash framed by path and length; no content-digest door",
    }.items()
}
_WEAK = {"md5", "sha1"}
# the files allowed to name md5/sha1 give the same reason as in the importer rows above; a name missing there is a KeyError here,
# which keeps the weak list inside the importer list
_WEAK_ALLOWED = {
    key: _HASHLIB_IMPORTERS[f"packages/{key}"]
    for key in (
        "any-failure-fp/src/any_failure_fp/fingerprint.py",
        "git-porcelain/src/git_porcelain/fake_read.py",
        "git-porcelain/src/git_porcelain/fake_store.py",
        "git-porcelain/src/git_porcelain/real_cache.py",
        "git-porcelain/src/git_porcelain/real_read.py",
    )
}


def _imports_hashlib(source: Source) -> Iterator[Hit]:
    """Each `import hashlib` / `from hashlib import ...`; content-digest, the owner, is skipped."""
    if source.package == "content-digest":
        return
    for node in ast.walk(source.tree):
        if (isinstance(node, ast.Import) and any(a.name == "hashlib" for a in node.names)) or (
            isinstance(node, ast.ImportFrom) and node.module == "hashlib"
        ):
            yield source.rel, node.lineno


def _names_weak_hash(source: Source) -> Iterator[Hit]:
    """Each spelling of md5 or sha1: an attribute, a `from hashlib import`, or a string (`hashlib.new("sha1")`)."""
    if source.package == "content-digest":
        return
    for node in ast.walk(source.tree):
        if (
            (isinstance(node, ast.Attribute) and node.attr in _WEAK)
            or (isinstance(node, ast.ImportFrom) and node.module == "hashlib" and any(a.name in _WEAK for a in node.names))
            or (isinstance(node, ast.Constant) and node.value in _WEAK)
        ):
            yield source.rel, node.lineno


HASHLIB = Rule(
    "hashlib-importers",
    "new hashlib importer: use content_digest, or add a reasoned row; migrated or gone: delete its row",
    _imports_hashlib,
    _HASHLIB_IMPORTERS,
    ("legitimate", "consumer wave"),
)
WEAK_HASH = Rule(
    "weak-hashes",
    "md5/sha1 is not for new code; content_digest pins sha256; no longer uses md5/sha1: delete its row",
    _names_weak_hash,
    {f"packages/{key}": row for key, row in _WEAK_ALLOWED.items()},
    ("legitimate", "consumer wave"),
)


def test_hashlib_is_imported_only_by_content_digest_and_the_rows_and_every_row_says_why() -> None:
    check(HASHLIB, _ROOT)


def test_md5_and_sha1_appear_only_where_the_rows_allow() -> None:
    check(WEAK_HASH, _ROOT)


def test_a_planted_hashlib_import_and_weak_name_are_found(tmp_path: Path) -> None:
    where = "packages/pkg/src/pkg/mod.py"
    assert plant(HASHLIB, tmp_path / "a", "import hashlib\n", where) == {where: [1]}
    assert plant(HASHLIB, tmp_path / "b", "from hashlib import sha256\n", where) == {where: [1]}
    assert plant(HASHLIB, tmp_path / "c", "import hashlib\n", "packages/content-digest/src/content_digest/mod.py") == {}
    assert plant(WEAK_HASH, tmp_path / "d", "import hashlib\nhashlib.md5(b'')\n", where) == {where: [2]}
    assert plant(WEAK_HASH, tmp_path / "e", "import hashlib\nhashlib.new('sha1')\n", where) == {where: [2]}
    assert plant(WEAK_HASH, tmp_path / "f", "import hashlib\nhashlib.sha256(b'')\n", where) == {}
