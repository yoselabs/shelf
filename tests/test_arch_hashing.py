"""One hashing home: hashlib is imported by content-digest, plus the files below, each with its reason.

A file marked "consumer wave" still hand-rolls a hash content-digest can now produce; its migration deletes
the entry. A legitimate entry says why content-digest cannot be the door. md5 and sha1 are named in no other file.
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PACKAGES = _ROOT / "packages"

_HASHLIB_IMPORTERS = {
    "any-failure-fp/src/any_failure_fp/fingerprint.py": "legitimate: sha1 suffix of a cut fingerprint is a key; sha256 would change it",
    "any-speech/src/any_speech/defaults.py": "consumer wave: sha256 of a binary file (digest_file)",
    "any-speech/src/any_speech/pipeline.py": "consumer wave: streamed sha256 of the audio, stored (digest_file, length=64)",
    "anyembed/src/anyembed/cache.py": "consumer wave: raw sha256 bytes as cache key (bytes.fromhex(digest_text(length=64)))",
    "anyembed/src/anyembed/testing.py": "legitimate: raw digest bytes seed a fake vector, not an identity",
    "blueprint/src/blueprint/runner.py": "consumer wave: sha256 of one joined string (digest_text)",
    "dir-trust/src/dir_trust/__init__.py": "legitimate: incremental hash with NUL framing, kept in trust grants; no content-digest door",
    "git-porcelain/src/git_porcelain/fake_read.py": "legitimate: sha1 of the common dir is a stored local key",
    "git-porcelain/src/git_porcelain/fake_store.py": "legitimate: git's own blob and tree object id is sha1",
    "git-porcelain/src/git_porcelain/real_cache.py": "legitimate: sha1 change detector of working-tree content, not an identity",
    "git-porcelain/src/git_porcelain/real_read.py": "legitimate: sha1 of the common dir is a stored local key",
    "shelf-vendor/src/shelf_vendor/__init__.py": "legitimate: tree hash framed by path and length; no content-digest door",
}
_WEAK = {"md5", "sha1"}
_WEAK_ALLOWED = {
    "any-failure-fp/src/any_failure_fp/fingerprint.py",
    "git-porcelain/src/git_porcelain/fake_read.py",
    "git-porcelain/src/git_porcelain/fake_store.py",
    "git-porcelain/src/git_porcelain/real_cache.py",
    "git-porcelain/src/git_porcelain/real_read.py",
}


def _sources() -> dict[str, ast.Module]:
    out: dict[str, ast.Module] = {}
    for path in sorted(_PACKAGES.glob("*/src/**/*.py")):
        rel = path.relative_to(_PACKAGES).as_posix()
        if not rel.startswith("content-digest/"):
            out[rel] = ast.parse(path.read_text())
    return out


def _imports_hashlib(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name == "hashlib" for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "hashlib":
            return True
    return False


def _names_weak_hash(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in _WEAK:
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "hashlib" and any(a.name in _WEAK for a in node.names):
            return True
        if isinstance(node, ast.Constant) and node.value in _WEAK:  # hashlib.new("sha1")
            return True
    return False


def test_hashlib_is_imported_only_by_content_digest_and_the_allowlist() -> None:
    importers = {rel for rel, tree in _sources().items() if _imports_hashlib(tree)}
    assert importers - _HASHLIB_IMPORTERS.keys() == set(), "new hashlib importer: use content_digest, or allowlist it with a reason"
    assert _HASHLIB_IMPORTERS.keys() - importers == set(), "migrated or gone: delete its allowlist entry"


def test_every_allowlist_entry_says_why() -> None:
    for rel, reason in _HASHLIB_IMPORTERS.items():
        assert reason.startswith(("legitimate: ", "consumer wave: ")), rel


def test_md5_and_sha1_appear_only_where_allowlisted() -> None:
    weak = {rel for rel, tree in _sources().items() if _names_weak_hash(tree)}
    assert weak - _WEAK_ALLOWED == set(), "md5/sha1 is not for new code; content_digest pins sha256"
    assert _WEAK_ALLOWED - weak == set(), "no longer uses md5/sha1: delete its entry"
    assert _HASHLIB_IMPORTERS.keys() >= _WEAK_ALLOWED
