"""No error erasure (constitution Article III, "Two kinds of failure").

A function that turns "it broke" into `None`, `False`, `[]`, `{}`, `0` or `''` makes a failure look like an empty answer:
the caller cannot tell "nothing there" from "could not look". A hit is

- an `except` handler that returns such a constant (any path of the handler, nested functions excluded) and does not raise,
  unless every type it catches is an absence type: `FileNotFoundError`, `NotADirectoryError`, `KeyError`,
  `ProcessLookupError`, `StopIteration`, or a `LookupError` subclass named `*NotFound*` / `*Missing*`; or
- a `return` anywhere inside a `finally` block, whatever it returns: it replaces the exception in flight.

This extends `tests/test_arch_swallowed_exceptions.py` and stays disjoint from it: that rule owns silent handlers (`pass`,
`...`, `continue`, a bare `return`, a lone constant, `suppress`), this one owns a handler that does something and then
answers with a constant, plus `return` in `finally`. A handler is never a hit of both (a bare `return` has no value here).

Checked over `packages/*/src` (tests excluded). Rows: file -> (hit count, reason). `debt:` an erased failure still owed a fix
(raise, or return a typed outcome such as `Missing()` / `Failed(reason)`); `outcome:` the constant is the true answer of a
probe (`is_alive`, `looks_like`) and a failure to ask means "no" by definition.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from any_arch import Rule, check, plant, rows

from tests.arch_keys import qualnames

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent
_ABSENCE = {"FileNotFoundError", "NotADirectoryError", "KeyError", "ProcessLookupError", "StopIteration"}
_EMPTY_CALLS = {"list", "dict", "set", "tuple", "frozenset"}


def _absence(name: str) -> bool:
    return name in _ABSENCE or "NotFound" in name or "Missing" in name


def _erasing(value: ast.expr | None) -> bool:
    match value:
        case ast.Constant(value=None | False | 0 | "" | b"") | ast.List(elts=[]) | ast.Dict(keys=[]) | ast.Tuple(elts=[]):
            return True
        case ast.Call(func=ast.Name(id=name), args=[], keywords=[]):
            return name in _EMPTY_CALLS
        case _:
            return False


def _own(nodes: list[ast.stmt]) -> Iterator[ast.AST]:
    """Every node under `nodes` without entering a nested function or class."""
    stack: list[ast.AST] = list(nodes)
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef):
            stack.extend(ast.iter_child_nodes(node))


def _catches_only_absence(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return False
    types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return all(_absence(ast.unparse(t).split(".")[-1]) for t in types)


def _erased(source: Source) -> Iterator[Hit]:
    """Key `file:Class.function` so a file with an outcome and a debt gets two rows."""
    names = qualnames(source.tree)
    for node in ast.walk(source.tree):
        if isinstance(node, ast.ExceptHandler):
            inside = list(_own(node.body))
            returns = [n for n in inside if isinstance(n, ast.Return) and n.value is not None and _erasing(n.value)]
            if returns and not any(isinstance(n, ast.Raise) for n in inside) and not _catches_only_absence(node):
                yield f"{source.rel}:{names[node]}", node.lineno
        elif isinstance(node, ast.Try):
            yield from ((f"{source.rel}:{names[node]}", n.lineno) for n in _own(node.finalbody) if isinstance(n, ast.Return))


_DEBT_DEFECT = (
    "debt: the handler catches a defect type (`Exception`, `TypeError`, `AttributeError`, `RuntimeError`) and "
    "answers with a constant, so a bug looks like a normal miss; narrow it to the errors the call raises and let "
    "the rest raise"
)
_DEBT_LOSSY = (
    "debt: a failed read (OSError) or an in-range constant (`0.0`, `''`, `{}`, `[]`) is returned from a function "
    "whose type has no way to say 'could not look'; return `T | None` or a typed `Unreadable`, or let it raise"
)
_OUTCOME_PARSE = (
    "outcome: input that does not parse (a torn line, a bad date, invalid JSON or TOML) is the answer 'not one of "
    "these'; the caller skips it"
)
_OUTCOME_IMPORT = "outcome: an optional dependency that is not installed is the answer; the next engine or extractor is tried"
_OUTCOME_TYPED = (
    "outcome: a typed refusal (lock held, git failed, child timed out, filesystem unsafe) is the answer of a try- "
    "lock or a probe and is recorded or returned as None"
)
_OUTCOME_PROBE = (
    "outcome: a bool probe (`is_*`, `*_available`, `has_*`) answers no when it cannot look: absent file, process gone, platform unsupported"
)
_OUTCOME_ABSENT = "outcome: a file, record or value that is absent or unreadable is the answer of a read-only lookup typed `T | None`"

_ALLOWED = {
    # --- debt-defect: 17 rows, 19 hits ---
    **rows(
        _DEBT_DEFECT,
        ("packages/a2effect/src/a2effect/raises.py:Raises.flatten_from_annotation", 1),
        ("packages/a2effect/src/a2effect/raises_registry.py:read_inline_annotation", 2),
        ("packages/a2effect/src/a2effect/testing/__init__.py:_enricher_output_types", 1),
        ("packages/any-agent/src/any_agent/harnesses/opencode.py:OpenCodeHarness.free_model_ok", 1),
        ("packages/any-browser/src/any_browser/playwright.py:_is_challenged_subresource", 1),
        ("packages/any-browser/src/any_browser/zendriver.py:_is_challenged_cdp_response", 1),
        ("packages/any-frontmatter/src/any_frontmatter/coerce.py:opt_str", 1),
        ("packages/any-net/src/any_net/probe.py:last", 1),
        ("packages/any-plugin-cache/src/any_plugin_cache/installs.py:installed_version", 1),
        ("packages/blueprint/src/blueprint/concerns/beads/backlog.py:_settings_env", 1),
        ("packages/convert-md/src/convert_md/engines.py:_pptx_notes", 2),
        ("packages/json-in-html/src/json_in_html/__init__.py:extract_json_payloads", 1),
        ("packages/json-in-html/src/json_in_html/__init__.py:parse_json_response", 1),
        ("packages/mcp-bridge/src/mcp_bridge/__init__.py:downstream_client_name", 1),
        ("packages/sqlite-store/src/sqlite_store/connections.py:SharedConnections.get", 1),
        ("packages/sqlite-store/src/sqlite_store/filesystem.py:_unsafe_filesystem", 1),
        ("packages/stream-proc/src/stream_proc/procmac.py:boot_id", 1),
    ),
    # --- debt-lossy: 13 rows, 13 hits ---
    **rows(
        _DEBT_LOSSY,
        ("packages/any-agent/src/any_agent/harnesses/codex_rollout.py:_when", 1),
        ("packages/any-gate/src/any_gate/receipts.py:Receipts._read", 1),
        ("packages/any-gate/src/any_gate/state.py:GateState.passed", 1),
        ("packages/any-json-doc/src/any_json_doc/__init__.py:DocSet.keys", 1),
        ("packages/any-lease/src/any_lease/pace.py:_read", 1),
        ("packages/any-speech/src/any_speech/speech.py:Speech._tries_so_far", 1),
        ("packages/beads-client/src/beads_client/classify.py:loads", 1),
        ("packages/blueprint/src/blueprint/facts.py:package_json", 1),
        ("packages/blueprint/src/blueprint/profile.py:_runtime_dependencies", 1),
        ("packages/due-schedule/src/due_schedule/__init__.py:cron_is_due", 1),
        ("packages/jsonl-log/src/jsonl_log/cursor.py:size", 1),
        ("packages/mcp-clients/src/mcp_clients/__init__.py:configured_servers", 1),
        ("packages/sqlite-sidecar/src/sqlite_sidecar/__init__.py:unreadable", 1),
    ),
    # --- outcome-parse: 17 rows, 18 hits ---
    **rows(
        _OUTCOME_PARSE,
        ("packages/any-agent/src/any_agent/activity.py:decode", 2),
        ("packages/any-agent/src/any_agent/harnesses/claude.py:ClaudeHarness.parse_line", 1),
        ("packages/any-agent/src/any_agent/harnesses/codex.py:CodexHarness.parse_line", 1),
        ("packages/any-agent/src/any_agent/harnesses/opencode.py:OpenCodeHarness.parse_line", 1),
        ("packages/any-proc/src/any_proc/run.py:parse_result", 1),
        ("packages/asgi-token-gate/src/asgi_token_gate/__init__.py:TokenGate._token", 1),
        ("packages/blueprint/src/blueprint/concerns/beads/agents.py:_settings", 1),
        ("packages/blueprint/src/blueprint/model.py:Context.toml", 1),
        ("packages/content-extract/src/content_extract/__init__.py:_parse_date", 1),
        ("packages/json-in-html/src/json_in_html/__init__.py:_try_parse", 1),
        ("packages/partial-time/src/partial_time/__init__.py:_instant", 1),
        ("packages/partial-time/src/partial_time/__init__.py:_partial", 1),
        ("packages/process-lock/src/process_lock/__init__.py:_parse", 1),
        ("packages/py-symbols/src/py_symbols/__init__.py:_parse", 1),
        ("packages/record-mine/src/record_mine/detector.py:_parse_tree", 1),
        ("packages/timefmt/src/timefmt/__init__.py:parse_until", 1),
        ("packages/timefmt/src/timefmt/__init__.py:to_epoch", 1),
    ),
    # --- outcome-import: 2 rows, 2 hits ---
    **rows(
        _OUTCOME_IMPORT,
        ("packages/convert-md/src/convert_md/html.py:_extract_html2text", 1),
        ("packages/convert-md/src/convert_md/html.py:_extract_trafilatura", 1),
    ),
    # --- outcome-typed: 4 rows, 4 hits ---
    **rows(
        _OUTCOME_TYPED,
        ("packages/any-gate-python/src/any_gate_python/select.py:_exports", 1),
        ("packages/any-lease/src/any_lease/leases.py:Leases._take_path", 1),
        ("packages/blueprint/src/blueprint/model.py:Context.run", 1),
        ("packages/git-porcelain/src/git_porcelain/history.py:show_at", 1),
    ),
    # --- outcome-probe: 13 rows, 13 hits ---
    **rows(
        _OUTCOME_PROBE,
        ("packages/any-lease/src/any_lease/leases.py:_is_held", 1),
        ("packages/any-speech/src/any_speech/failures.py:is_known_failure", 1),
        ("packages/any-speech/src/any_speech/speech.py:is_current", 1),
        ("packages/anyllm/src/anyllm/providers/claude_code_sdk.py:_session_credentials_present", 1),
        ("packages/blueprint/src/blueprint/report.py:_unchanged", 1),
        ("packages/convert-md/src/convert_md/dispatch.py:_installed", 1),
        ("packages/git-porcelain/src/git_porcelain/lfs.py:lfs_available", 1),
        ("packages/git-porcelain/src/git_porcelain/porcelain.py:has_conflict_markers", 1),
        ("packages/git-porcelain/src/git_porcelain/real_write.py:has_markers", 1),
        ("packages/sqlite-store/src/sqlite_store/connections.py:SharedConnections.usable", 1),
        ("packages/stream-proc/src/stream_proc/proctable.py:group_alive", 1),
        ("packages/stream-proc/src/stream_proc/tree.py:_Sent.call", 1),
    ),
    # --- outcome-absent: 19 rows, 20 hits ---
    **rows(
        _OUTCOME_ABSENT,
        ("packages/any-agent/src/any_agent/harnesses/codex_rollout.py:read", 1),
        ("packages/any-gate-python/src/any_gate_python/graph.py:lock_touched", 1),
        ("packages/any-gate-python/src/any_gate_python/graph.py:touched_between", 1),
        ("packages/any-gate/src/any_gate/state.py:_git", 1),
        ("packages/any-lease/src/any_lease/leases.py:_read_limit", 1),
        ("packages/any-proc/src/any_proc/cpus.py:cgroup_quota", 2),
        ("packages/any-proc/src/any_proc/run.py:read_args", 1),
        ("packages/blueprint/src/blueprint/gate_py.py:settings", 1),
        ("packages/blueprint/src/blueprint/gate_units.py:_computes_imports", 1),
        ("packages/blueprint/src/blueprint/gate_units.py:_import_names", 1),
        ("packages/blueprint/src/blueprint/gate_units.py:_project_part", 1),
        ("packages/blueprint/src/blueprint/profile.py:_builds_tooling_only", 1),
        ("packages/git-porcelain/src/git_porcelain/porcelain.py:_head_from_files", 1),
        ("packages/git-porcelain/src/git_porcelain/porcelain.py:git_dir", 1),
        ("packages/git-porcelain/src/git_porcelain/real_cache.py:rev_files", 1),
        ("packages/git-porcelain/src/git_porcelain/real_cache.py:sig", 1),
        ("packages/git-porcelain/src/git_porcelain/real_env.py:git_dir", 1),
        ("packages/page-tsv/src/page_tsv/render.py:_tsv_or_none", 1),
        ("packages/process-lock/src/process_lock/__init__.py:holder", 1),
        ("packages/stream-proc/src/stream_proc/procfs.py:boot_id", 1),
    ),
}

ERASURE = Rule(
    "error-erasure",
    "a handler turns a failure into a constant answer (raise, or return a typed outcome, or add a reasoned row)",
    _erased,
    _ALLOWED,
    ("debt", "outcome"),
)


def test_repo_erases_exactly_the_failures_its_rows_list() -> None:
    check(ERASURE, _ROOT)


@pytest.mark.parametrize(
    "source",
    [
        "def g():\n    try:\n        return f()\n    except OSError:\n        return None\n",
        "def g():\n    try:\n        return f()\n    except Exception:\n        return False\n",
        "def g():\n    try:\n        return f()\n    except (OSError, ValueError):\n        log()\n        return []\n",
        "def g():\n    try:\n        return f()\n    except:\n        return {}\n",
        "def g():\n    try:\n        return f()\n    except ValueError:\n        if x:\n            return 0\n        return ''\n",
        "def g():\n    try:\n        return f()\n    except OSError:\n        return list()\n",
        "def g():\n    try:\n        f()\n    finally:\n        return 1\n",
        "def g():\n    try:\n        f()\n    finally:\n        cleanup()\n        return compute()\n",
    ],
)
def test_a_planted_erasure_is_found(tmp_path: Path, source: str) -> None:
    found = plant(ERASURE, tmp_path, source)
    assert list(found) == ["packages/pkg/src/pkg/mod.py:g"]
    assert len(found["packages/pkg/src/pkg/mod.py:g"]) == 1


@pytest.mark.parametrize(
    "source",
    [
        "def g():\n    try:\n        return f()\n    except FileNotFoundError:\n        return None\n",
        "def g():\n    try:\n        return d[k]\n    except (KeyError, ProcessLookupError):\n        return False\n",
        "def g():\n    try:\n        return f()\n    except ProfileNotFound:\n        return None\n",
        "def g():\n    try:\n        return f()\n    except OSError:\n        return Failed('x')\n",
        "def g():\n    try:\n        return f()\n    except OSError as e:\n        raise Wrapped() from e\n",
        "def g():\n    try:\n        return f()\n    except OSError:\n        log()\n        raise\n",
        "def g():\n    try:\n        return f()\n    except OSError:\n        return\n",
        "def g():\n    try:\n        return f()\n    except OSError:\n        pass\n",
        "def g():\n    try:\n        f()\n    finally:\n        cleanup()\n",
        "def g():\n    try:\n        f()\n    finally:\n        def h():\n            return 1\n",
    ],
)
def test_an_absence_a_typed_answer_a_raise_or_a_swallow_is_not_a_hit(tmp_path: Path, source: str) -> None:
    assert plant(ERASURE, tmp_path, source) == {}
