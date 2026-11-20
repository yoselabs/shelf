"""No optionality (Article III): a bool parameter with a default is a mode, and each one is a named, justified row.

ruff FBT covers positional bools only. This check covers every function and method in `packages/*/src`
that takes a parameter annotated `bool`, `bool | None` or `Optional[bool]` WITH a default, keyword-only
included, private helpers included. A hit is keyed `package:function:parameter`, so one flag repeated on
a Protocol, its real and fake implementations is one row. The rows below are the CURRENT hits, triaged in docs/bool-modes-triage.md;
a new bool mode fails the gate,
a row whose flag is gone must be deleted. Reason prefixes:

- `split:` the flag picks between two behaviours of one operation; the reason names the separate type or function
- `fact:` the flag is data about one call, one value or one error (or a third-party library's own option), not a code path
- `exception:` a named, justified opt-in (cost, safety, durability) that Article III allows only as a row; each needs an
  accepted ADR (ADR 0022) to be durable
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
    # --- split: the flag chooses between behaviours; a separate type or function is the fix ---
    **_rows(
        "split: one render() path that scrolls an infinite listing to the end; a2web consumes the Protocol",
        "any-browser:render:scroll_to_stable",
        "any-browser:_navigate:scroll_to_stable",
    ),
    **_rows(
        "split: keep_mode picks between two permission behaviours; consumers a2kay, any-frontmatter, any-net, dir-trust",
        "atomic-io:atomic_write_bytes:keep_mode",
        "atomic-io:atomic_write_json:keep_mode",
        "atomic-io:atomic_write_text:keep_mode",
    ),
    **_rows(
        "split: choices=True is a compatibility switch between two flag shapes; ogy consumes verb-cli",
        "verb-cli:flags_of:choices",
    ),
    **_rows(
        "split: fallback=False returns the first survivor instead of the composed provider; a2kay and a2web consume resolve_provider",
        "anyllm:resolve_provider:fallback",
    ),
    **_rows(
        "split: capture=False inherits stdio instead of capturing; a second operation",
        "stream-proc:capture_bytes:capture",
    ),
    **_rows(
        "split: _hit(group=) sends to the pid only or to its group too; the call site computes the flag",
        "stream-proc:_hit:group",
    ),
    **_rows(
        "split: the same call, two policies for a missing target; the codebase already returns outcome values (NothingToRecord)",
        "git-porcelain:abort_rebase:missing_ok",
        "git-porcelain:continue_rebase:missing_ok",
        "git-porcelain:delete_remote_at:missing_ok",
        "git-porcelain:drop_worktree:missing_ok",
    ),
    **_rows(
        "split: raising vs returning the exit code is two functions (run / try_run)",
        "git-porcelain:run:check",
        "git-porcelain:run_git:check",
    ),
    **_rows(
        "split: memo(forever=False) is a second cache lifetime (until the next write)",
        "git-porcelain:memo:forever",
    ),
    **_rows(
        "split: the fake's fetch(retry=False) skips ref races the real fetch always retries; a flag only the fake has",
        "git-porcelain:fetch:retry",
    ),
    **_rows(
        "split: stage_conflicts and check_markers turn continue_rebase into a resolve-and-continue operation",
        "git-porcelain:continue_rebase:check_markers",
        "git-porcelain:continue_rebase:stage_conflicts",
    ),
    **_rows(
        "split: literal=False is pathspec staging, another operation",
        "git-porcelain:stage:literal",
    ),
    **_rows(
        "split: push=True reads the push URL, git's separate `get-url --push`",
        "git-porcelain:remote_url:push",
        "git-porcelain:remote_urls:push",
    ),
    # --- exceptions: a named, justified opt-in (needs an accepted ADR, ADR 0022) ---
    **_rows(
        "exception: durability tier of one write (fsync or not); the default is the safe one, off is "
        "for caches and hot state; needs an ADR row (ADR 0022)",
        "any-json-doc:__init__:fsync",
        "atomic-io:atomic_write_bytes:fsync",
        "atomic-io:atomic_write_json:fsync",
        "atomic-io:atomic_write_text:fsync",
    ),
    **_rows(
        "exception: a cost opt-in: the dirty flag needs one `git status` per worktree (Article IX: cost "
        "makes it opt-in); needs an ADR row (ADR 0022)",
        "git-porcelain:worktrees:with_dirty",
    ),
    **_rows(
        "exception: a cost opt-in: the network ls-remote probe; check_push=False stays local and fast; needs an ADR row (ADR 0022)",
        "git-porcelain:readiness:check_push",
    ),
    **_rows(
        "exception: the safe default and a named opt-out that mirrors git's own flag for one "
        "destructive or history-changing call; needs an ADR row (ADR 0022)",
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
        "git-porcelain:record:allow_empty",
        "git-porcelain:record:hooks",
        "git-porcelain:park:keep_ignored",
        "beads-client:unclaim:force",
        "beads-client:reclaim:any_replica",
    ),
    **_rows(
        "exception: whether a repo observation is cached, chosen once at construction, for fresh reads; needs an ADR row (ADR 0022)",
        "git-porcelain:__init__:memoize",
    ),
    **_rows(
        "exception: pin=False skips the checkout's environment pin for one call (the runner's own "
        "escape hatch); needs an ADR row (ADR 0022)",
        "git-porcelain:run:pin",
    ),
    # --- facts: data about one call, value or error ---
    **_rows(
        "fact: the include/skip choice is trafilatura's own extraction option, passed through; the page "
        "decides which regions are boilerplate",
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
    ),
    **_rows(
        "fact: a plist value written verbatim (RunAtLoad, KeepAlive); the function renders data, it does not branch on it",
        "launchd-agent:render_plist:keep_alive",
        "launchd-agent:render_plist:run_at_load",
    ),
    **_rows(
        "fact: a query predicate on one `bd list` call (mirrors bd's own --all)",
        "beads-client:find:include_closed",
    ),
    **_rows(
        "fact: json.dumps's own formatting option, passed through (like indent)",
        "atomic-io:atomic_write_json:sort_keys",
    ),
    **_rows(
        "fact: the connection's thread affinity, passed to sqlite3 as check_same_thread",
        "sqlite-store:_open:shared",
    ),
    **_rows(
        "fact: a field of the StopReport being built (the observation failed), not a code path",
        "stream-proc:report:error",
    ),
    **_rows(
        "fact: subprocess's own start_new_session, passed to Popen; no caller varies it",
        "stream-proc:popen_registered:start_new_session",
    ),
    **_rows(
        "fact: a property of the checkpoint (slow, or reads outside the repo), stored on Check, not a branch in the function",
        "blueprint:check:audit_only",
        "blueprint:check_each:audit_only",
    ),
    **_rows(
        "fact: a Finding field: the blueprint itself cannot judge the row yet",
        "blueprint:not_checked:blueprint_gap",
    ),
    **_rows(
        "fact: the model's load-time hardware and network placement, passed to llama.cpp (n_gpu_layers) "
        "and transformers (local_files_only)",
        "anyembed:__init__:gpu",
        "anyembed:__init__:offline",
    ),
    **_rows(
        "fact: a request parameter of the completion call, like temperature, forwarded to the backend",
        "anyllm:complete:thinking_disabled",
    ),
    **_rows(
        "fact: git's own tri-state option (None defers to git config), passed through",
        "git-porcelain:rebase:update_refs",
        "git-porcelain:rebase_onto:update_refs",
        "git-porcelain:start_rebase:update_refs",
    ),
    **_rows(
        "fact: how much of the child's output the message quotes (the tail or all of it); the failure is the same",
        "git-porcelain:unavailable:full_output",
    ),
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
