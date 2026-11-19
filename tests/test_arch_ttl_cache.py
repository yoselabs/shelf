"""One owner of the sqlite TTL table (constitution Article III; bead shelf-tyld.4).

llm-cache and http-cache each hand-wrote the same store: a row with an expiry column, read
with an expiry filter, deleted lazily, stamped from the wall clock. any-ttl-cache owns that
now. This rule keeps it from growing back: outside `any_ttl_cache`, no package source may
carry a SQL statement that reads, writes or deletes by an `expir…` column.

Deliberately narrow, and honest about it. What it checks: a string literal in `packages/*/src`
that begins with SELECT, INSERT, UPDATE or DELETE and names an `expir…` column. What it does
not check: a TTL kept under another column name, DDL (a caller owns its `CREATE TABLE`, which
is how existing databases keep their bytes), or a TTL kept outside sqlite.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_OWNER = "any_ttl_cache"
_DML = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE)\b", re.IGNORECASE)
_EXPIRY = re.compile(r"expir", re.IGNORECASE)


def _offending_statements(source: str) -> list[str]:
    """String literals in ``source`` that are SQL DML against an expiry column."""
    tree = ast.parse(source)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
    }
    found: list[str] = []
    for node in ast.walk(tree):
        if id(node) in docstrings:
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and _DML.match(node.value) and _EXPIRY.search(node.value):
            found.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            text = "".join(part.value for part in node.values if isinstance(part, ast.Constant) and isinstance(part.value, str))
            if _DML.match(text) and _EXPIRY.search(text):
                found.append(text)
    return found


def test_sql_on_an_expiry_column_lives_only_in_the_ttl_cache_package() -> None:
    sources = [p for p in (_ROOT / "packages").glob("*/src/**/*.py") if _OWNER not in p.parts]
    assert sources, "no package sources found; the walk is vacuous"
    offenders = {str(p.relative_to(_ROOT)): hits for p in sources if (hits := _offending_statements(p.read_text(encoding="utf-8")))}
    assert not offenders, (
        f"SQL on an expiry column outside {_OWNER}; use any_ttl_cache.TtlTable for the read, write and eviction:\n  "
        + "\n  ".join(f"{path}: {hits}" for path, hits in offenders.items())
    )


def test_the_rule_flags_the_shapes_the_two_caches_used_to_hand_write() -> None:
    # Anti-vacuity: the statements llm-cache 0.1.2 and http-cache 0.1.0 carried, plus an f-string one.
    assert _offending_statements('q = "DELETE FROM llm_cache WHERE expires_at <= ?"')
    assert _offending_statements('q = "SELECT body FROM cache WHERE url = ? AND expires_at > ?"')
    assert _offending_statements('q = "INSERT OR REPLACE INTO c (k, expires_at) VALUES (?, ?)"')
    assert _offending_statements('q = f"DELETE FROM {t} WHERE expires_at <= ?"')


def test_the_rule_leaves_ddl_and_unrelated_sql_to_the_callers() -> None:
    assert not _offending_statements('s = "CREATE TABLE IF NOT EXISTS c (k TEXT, expires_at INTEGER NOT NULL)"')
    assert not _offending_statements('q = "SELECT COUNT(*) FROM llm_cache"')
    assert not _offending_statements('doc = "Entries expire after ttl_s"')
    assert not _offending_statements('def f():\n    """Delete the expired rows."""\n')
