"""No optionality (Article III): a bool parameter with a default is a mode, and each one is a named, justified row.

ruff FBT covers positional bools only. This check covers every function and method in `packages/*/src`
that takes a parameter annotated `bool`, `bool | None` or `Optional[bool]` WITH a default, keyword-only
included, private helpers included. A hit is keyed `package:function:parameter`, so one flag repeated on
a Protocol, its real and fake implementations is one row. The rows below are the CURRENT hits; a new bool
mode fails the gate, a row whose flag is gone must be deleted. Reason prefixes:

- `mode:` the flag picks between behaviours (a real optionality violation for the consumer waves to split)
- `fact:` the flag carries a fact or states a safety opt-out about one call, not a second behaviour path
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _is_bool(annotation: ast.expr | None) -> bool:
    return annotation is not None and ast.unparse(annotation) in {"bool", "bool | None", "None | bool", "Optional[bool]"}


def bool_modes(root: Path) -> dict[str, int]:
    """`package:function:parameter` -> number of definitions carrying it, for `root/packages/*/src`."""
    hits: dict[str, int] = {}
    for path in sorted((root / "packages").glob("*/src/**/*.py")):
        package = path.relative_to(root / "packages").parts[0]
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            args = node.args
            positional = [*args.posonlyargs, *args.args]
            defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
            for arg, default in [*zip(positional, defaults, strict=True), *zip(args.kwonlyargs, args.kw_defaults, strict=True)]:
                if default is not None and _is_bool(arg.annotation):
                    key = f"{package}:{node.name}:{arg.arg}"
                    hits[key] = hits.get(key, 0) + 1
    return hits


def _rows(reason: str, *keys: str) -> dict[str, str]:
    return dict.fromkeys(keys, reason)


_ALLOWED: dict[str, str] = {
    # --- real modes: the flag chooses between behaviours ---
    **_rows(
        "mode: an include/skip toggle that changes what the one operation gathers or waits for",
        "content-extract:_extract_sync:include_comments",
        "content-extract:_extract_sync:include_links",
        "content-extract:_extract_sync:include_tables",
        "content-extract:extract_markdown:include_comments",
        "content-extract:extract_markdown:include_links",
        "content-extract:extract_markdown:include_tables",
        "convert-md:_extract_trafilatura:include_comments",
        "convert-md:_extract_trafilatura:include_links",
        "convert-md:_extract_trafilatura:include_tables",
        "convert-md:convert_html:include_comments",
        "convert-md:convert_html:include_links",
        "convert-md:convert_html:include_tables",
        "any-browser:_navigate:scroll_to_stable",
        "any-browser:render:scroll_to_stable",
        "git-porcelain:worktrees:with_dirty",
        "beads-client:find:include_closed",
    ),
    **_rows(
        "mode: the flag switches an I/O strategy (durability, read-only, sort) on the same operation",
        "any-json-doc:__init__:fsync",
        "atomic-io:atomic_write_bytes:fsync",
        "atomic-io:atomic_write_json:fsync",
        "atomic-io:atomic_write_text:fsync",
        "atomic-io:atomic_write_bytes:keep_mode",
        "atomic-io:atomic_write_json:keep_mode",
        "atomic-io:atomic_write_text:keep_mode",
        "atomic-io:atomic_write_json:sort_keys",
        "jsonl-log:__init__:read_only",
        "jsonl-log:open:read_only",
        "jsonl-log:_drop:evict",
        "sqlite-sidecar:connect:read_only",
        "sqlite-store:_open:shared",
        "process-lock:acquire:reentrant",
        "git-porcelain:__init__:memoize",
        "git-porcelain:memo:forever",
        "git-porcelain:run:check",
        "git-porcelain:run:pin",
        "git-porcelain:run_git:check",
    ),
    **_rows(
        "mode: a destructive-operation or error-handling opt-out; a second path through the same call",
        "git-porcelain:abort_rebase:missing_ok",
        "git-porcelain:continue_rebase:missing_ok",
        "git-porcelain:delete_remote_at:missing_ok",
        "git-porcelain:drop_worktree:missing_ok",
        "git-porcelain:add_worktree:force",
        "git-porcelain:drop_worktree:force",
        "git-porcelain:worktree_add:force",
        "git-porcelain:push_refspecs:force",
        "git-porcelain:push_request:force",
        "git-porcelain:validate_push:force",
        "git-porcelain:push_refspecs:allow_delete",
        "git-porcelain:push_request:allow_delete",
        "git-porcelain:validate_push:allow_delete",
        "git-porcelain:clean:ignored",
        "git-porcelain:clean:nested",
        "git-porcelain:fetch:retry",
        "beads-client:unclaim:force",
        "beads-client:reclaim:any_replica",
    ),
    **_rows(
        "mode: stage/hook/rebase behaviour toggled by the flag (update_refs is a tri-state: None defers to git config)",
        "git-porcelain:record:allow_empty",
        "git-porcelain:record:hooks",
        "git-porcelain:continue_rebase:check_markers",
        "git-porcelain:continue_rebase:stage_conflicts",
        "git-porcelain:park:keep_ignored",
        "git-porcelain:rebase:update_refs",
        "git-porcelain:rebase_onto:update_refs",
        "git-porcelain:start_rebase:update_refs",
        "git-porcelain:stage:literal",
        "git-porcelain:readiness:check_push",
        "git-porcelain:remote_url:push",
        "git-porcelain:remote_urls:push",
        "git-porcelain:command:lfs",
    ),
    **_rows(
        "mode: a feature toggle on one operation (render, include, strip, create, offline); consumer wave splits or defaults it",
        "git-porcelain:unavailable:full_output",
        "launchd-agent:render_plist:keep_alive",
        "launchd-agent:render_plist:run_at_load",
        "llm-wobble:parse_list_with_policy:strip_fences",
        "llm-wobble:strip_fenced_blocks:json_only",
        "verb-cli:flags_of:choices",
        "sqlite-sidecar:from_text:aware",
        "shelf-vendor:_say:err",
        "stream-proc:_hit:group",
        "stream-proc:report:error",
        "blueprint:write:prune",
        "blueprint:write:executable",
        "blueprint:check:audit_only",
        "blueprint:check_each:audit_only",
        "blueprint:run:audit",
        "blueprint:not_checked:blueprint_gap",
        "app-dirs:data_dir:create",
        "app-dirs:data_dir:plugin_data",
        "app-dirs:cache_dir:create",
        "app-dirs:config_dir:create",
        "app-dirs:state_dir:create",
        "app-dirs:cache_dir:plugin_data",
        "app-dirs:config_dir:plugin_data",
        "app-dirs:state_dir:plugin_data",
        "child-env:scrub:strip_venv",
        "child-env:scrub_current:strip_venv",
        "anyembed:__init__:gpu",
        "anyembed:__init__:offline",
        "convert-md:_result:check_yield",
        "convert-md:grade:check_yield",
        "stream-proc:capture_bytes:capture",
        "stream-proc:popen_registered:start_new_session",
        "any-agent:spawn:session",
        "anyllm:complete:thinking_disabled",
        "anyllm:resolve_provider:fallback",
    ),
    # --- facts: the flag records something about one call or one error ---
    **_rows(
        "fact: whether the failure may be retried is data on the error, not a behaviour switch",
        "a2effect:__init__:retryable",
        "a2effect:register_error_kind:retryable",
        "anyllm:__init__:retryable",
        "git-porcelain:__init__:retryable",
        "git-porcelain:failure:retryable",
    ),
    **_rows(
        "fact: an observed outcome passed into a pure classifier",
        "any-agent:classify:timed_out",
        "any-agent:classify:work_seen",
        "any-agent:finish:killed",
    ),
    **_rows(
        "fact: a test-support opt-in; contract_tests and the pytest-shaped monkeypatch wrappers mirror pytest's own signature",
        "a2effect:__init_subclass__:abstract",
        "a2effect:contract_tests:dead_enricher",
        "a2effect:contract_tests:envelope_round_trip",
        "a2effect:contract_tests:surface_parity",
        "anyllm:delenv:raising",
        "anyllm:setattr:raising",
        "git-porcelain:delenv:raising",
    ),
}


def _plant(tmp_path: Path, source: str) -> dict[str, int]:
    module = tmp_path / "packages" / "pkg" / "src" / "pkg" / "mod.py"
    module.parent.mkdir(parents=True)
    module.write_text(source)
    return bool_modes(tmp_path)


def test_repo_has_no_unlisted_bool_mode() -> None:
    new = sorted(set(bool_modes(_ROOT)) - set(_ALLOWED))
    assert not new, (
        f"bool parameter with a default is a mode (Article III: no optionality; split the behaviour or list it with a reason): {new}"
    )


def test_listed_bool_modes_still_exist_and_carry_a_reason() -> None:
    assert not sorted(set(_ALLOWED) - set(bool_modes(_ROOT))), "a listed bool mode no longer exists: delete its row"
    assert all(reason.strip() for reason in _ALLOWED.values())


def test_planted_keyword_only_bool_is_found(tmp_path: Path) -> None:
    assert _plant(tmp_path, "def run(cmd, *, fast: bool = False): ...\n") == {"pkg:run:fast": 1}


def test_planted_positional_bool_with_default_and_tri_state_are_found(tmp_path: Path) -> None:
    source = "class C:\n    def go(self, a: int, flag: bool = True, maybe: bool | None = None): ...\n"
    assert _plant(tmp_path, source) == {"pkg:go:flag": 1, "pkg:go:maybe": 1}


def test_required_bool_and_non_bool_defaults_pass(tmp_path: Path) -> None:
    source = "def a(*, flag: bool): ...\ndef b(n: int = 0, s: str = 'x', f=False): ...\n"
    assert _plant(tmp_path, source) == {}
