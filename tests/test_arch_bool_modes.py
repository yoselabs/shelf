"""No optionality (Article III): a bool parameter with a default is a mode, and each one is a named, justified row.

ruff FBT covers positional bools only. This check covers every function and method in `packages/*/src`
that takes a parameter annotated `bool`, `bool | None` or `Optional[bool]` WITH a default, keyword-only
included, private helpers included. A hit is keyed `package:function:parameter`, so one flag repeated on
a Protocol, its real and fake implementations is one row. The rows below are the CURRENT hits, triaged in docs/bool-modes-triage.md;
a new bool mode fails the gate,
a row whose flag is gone must be deleted. Reason prefixes:

- `split:` the flag picks between two behaviours of one operation; the reason names the separate type or function
- `fact:` the flag is data about one call, one value or one error (or a third-party library's own option), not a code path
- `cost:` the default is the complete or durable answer and the flag skips or adds a named cost (Article IX); ADR 0030
- `construction:` chosen once when the object is built, never per call; ADR 0030

Tolerance is a handler, not a flag (Article III, ADR 0030): a second check below covers public parameters named
force, overwrite, missing_ok, exist_ok, ignore_errors or check, and public parameters annotated Literal or an Enum
(the same flag in a coat). Each hit needs a row in `_POLICY_ALLOWED` with a reason.
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
    # --- cost opt-ins and construction config (ADR 0030) ---
    **_rows(
        "cost: durability tier of one write (fsync or not); the default is the safe one, off is for caches and hot state; ADR 0030",
        "any-json-doc:__init__:fsync",
        "atomic-io:atomic_write_bytes:fsync",
        "atomic-io:atomic_write_json:fsync",
        "atomic-io:atomic_write_text:fsync",
        "atomic-io:atomic_replace_bytes:fsync",
        "atomic-io:atomic_replace_json:fsync",
        "atomic-io:atomic_replace_text:fsync",
    ),
    **_rows(
        "cost: the dirty flag needs one `git status` per worktree (Article IX: cost makes it opt-in); ADR 0030",
        "git-porcelain:worktrees:with_dirty",
    ),
    **_rows(
        "cost: the network ls-remote probe; check_push=False stays local and fast; ADR 0030",
        "git-porcelain:readiness:check_push",
    ),
    **_rows(
        "construction: whether a repo observation is cached, chosen once at construction, for fresh reads; ADR 0030",
        "git-porcelain:__init__:memoize",
    ),
    **_rows(
        "cost: pin=False skips the checkout's environment pin for one call (the runner's own escape hatch); ADR 0030",
        "git-porcelain:run:pin",
        "git-porcelain:try_run:pin",
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
        "atomic-io:atomic_replace_json:sort_keys",
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


_NAMED = frozenset({"force", "overwrite", "missing_ok", "exist_ok", "ignore_errors", "check"})
_ENUM_BASES = frozenset({"Enum", "StrEnum", "IntEnum", "Flag", "IntFlag"})


def _enums_and_aliases(tree: ast.Module) -> set[str]:
    """Names in one module that stand for a Literal or an Enum: Enum subclasses and `X = Literal[...]` aliases."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(ast.unparse(base).split(".")[-1] in _ENUM_BASES for base in node.bases):
            names.add(node.name)
        elif isinstance(node, ast.Assign | ast.AnnAssign | ast.TypeAlias):
            value = node.value
            target = node.name if isinstance(node, ast.TypeAlias) else (node.targets[0] if isinstance(node, ast.Assign) else node.target)
            if value is not None and "Literal[" in ast.unparse(value) and isinstance(target, ast.Name):
                names.add(target.id)
    return names


def policy_params(root: Path) -> dict[str, int]:
    """`package:function:parameter` for each public function parameter that is a tolerance or policy switch."""
    hits: dict[str, int] = {}
    for path in sorted((root / "packages").glob("*/src/**/*.py")):
        package = path.relative_to(root / "packages").parts[0]
        tree = ast.parse(path.read_text())
        coats = _enums_and_aliases(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) or (node.name.startswith("_") and node.name != "__init__"):
                continue
            for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
                note = ast.unparse(arg.annotation) if arg.annotation is not None else ""
                names = {n.id for n in ast.walk(arg.annotation) if isinstance(n, ast.Name)} if arg.annotation is not None else set()
                if arg.arg in _NAMED or "Literal[" in note or names & coats:
                    key = f"{package}:{node.name}:{arg.arg}"
                    hits[key] = hits.get(key, 0) + 1
    return hits


_POLICY_ALLOWED: dict[str, str] = {
    **_rows(
        "debt: a Literal that picks between behaviours of one operation (the flag in a coat); convert to separate verbs "
        "(ADR 0030, Article III); not part of the 2026-11-20 tolerance conversion",
        "git-porcelain:finish_rebase:action",
        "git-porcelain:rebase_onto:squash_failure",
        "git-porcelain:record:mode",
        "git-porcelain:record_with_hooks:mode",
        "git-porcelain:record_args:mode",
        "git-porcelain:record_commit:mode",
        "git-porcelain:record_needed:mode",
        "git-porcelain:record_prepare:mode",
        "git-porcelain:take_branch:mode",
    ),
    **_rows(
        "fact: which part of the checkout one `record` stages is a selection of data, not a second behaviour",
        "git-porcelain:record:paths",
        "git-porcelain:record_with_hooks:paths",
        "git-porcelain:record_prepare:paths",
        "git-porcelain:record_stage:paths",
    ),
    **_rows(
        "fact: git reset's own --soft/--mixed/--hard, passed through; it names git's three reset depths",
        "git-porcelain:reset:mode",
    ),
    **_rows(
        "fact: a one-member Literal naming the single setup target, a CLI positional, not a switch",
        "any-speech:setup:what",
    ),
    **_rows(
        "fact: a tag naming the kind or outcome of one value or error; no code path branches on a caller's choice",
        "a2effect:register_error_kind:base",
        "any-agent:end:status",
        "beads-client:__init__:kind",
        "blueprint:failing:fixed_by",
        "blueprint:not_checked:fixed_by",
        "blueprint:not_set_up:fixed_by",
        "git-porcelain:__init__:reason",
        "llm-wobble:emit_wobble:tolerance",
        "task-spec:resolve:kind",
    ),
    **_rows(
        "fact: a lookup key or backend setting forwarded as data (which model, store, directory kind or request level)",
        "any-speech:__init__:model_version",
        "any-speech:default_card:role",
        "anyembed:__init__:pooling",
        "anyllm:complete:effort",
        "app-dirs:plugin_dir:kind",
        "browser-cookies:read_cookies:source",
        "convert-md:convert_html:source_kind",
        "http-fetch:__init__:opener",
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


def test_repo_has_no_unlisted_policy_parameter() -> None:
    new = sorted(set(policy_params(_ROOT)) - set(_POLICY_ALLOWED))
    assert not new, (
        "public parameter named force/overwrite/missing_ok/exist_ok/ignore_errors/check, or a Literal/Enum policy switch: "
        f"raise a typed exception the caller catches, or make two verbs (Article III, ADR 0030): {new}"
    )


def test_listed_policy_parameters_still_exist() -> None:
    assert not sorted(set(_POLICY_ALLOWED) - set(policy_params(_ROOT))), "a listed policy parameter no longer exists: delete its row"
    assert all(reason.strip() for reason in _POLICY_ALLOWED.values())


def test_planted_tolerance_names_are_found_with_any_annotation(tmp_path: Path) -> None:
    source = "def drop(path, *, missing_ok): ...\ndef put(path, overwrite=False, force: bool = True, check=None): ...\n"
    assert _plant_policy(tmp_path, source) == {"pkg:drop:missing_ok": 1, "pkg:put:overwrite": 1, "pkg:put:force": 1, "pkg:put:check": 1}


def test_planted_literal_enum_and_alias_policy_are_found(tmp_path: Path) -> None:
    source = (
        "from enum import Enum\nfrom typing import Literal, Annotated\n"
        "class Mode(Enum):\n    A = 1\n"
        "Policy = Literal['a', 'b']\n"
        "def a(x: Literal['p', 'q']): ...\n"
        "def b(x: Mode | None = None): ...\n"
        "def c(x: Policy): ...\n"
        "def d(x: Annotated[Literal['p'], 1]): ...\n"
    )
    assert _plant_policy(tmp_path, source) == {"pkg:a:x": 1, "pkg:b:x": 1, "pkg:c:x": 1, "pkg:d:x": 1}


def test_private_functions_and_plain_parameters_pass(tmp_path: Path) -> None:
    source = "def _hidden(force: bool): ...\ndef shown(path: str, limit: int = 3, mode_name: str = 'x'): ...\n"
    assert _plant_policy(tmp_path, source) == {}


def _plant_policy(tmp_path: Path, source: str) -> dict[str, int]:
    module = tmp_path / "packages" / "pkg" / "src" / "pkg" / "mod.py"
    module.parent.mkdir(parents=True)
    module.write_text(source)
    return policy_params(tmp_path)
