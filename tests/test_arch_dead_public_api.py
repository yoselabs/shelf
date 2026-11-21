"""Decay (constitution Article VIII): a name in a package's `__all__` that nothing outside the package uses is a deletion candidate.

A package's public surface is the `__all__` of its top-level `src/<module>/__init__.py`. A name is USED when some file
outside that package's own `src/`, `tests/`, README and CHANGELOG mentions both the name and the package (its module name or
its hyphenated name) in the same file: another package's source or tests, the repo's `tests/`, `tools/`, `skills/`, a
`use-cases/` file, another README, the root `pyproject.toml` (import-linter contracts) or another config. Inside the package,
surfaces count as use: its `__main__.py` files, a `module:name` entry in its own `pyproject.toml` (`[project.scripts]` and
entry-point tables), and the `pytest_*` hooks of a package that registers a `pytest11` plugin.
A name used only by its own package's tests, or only documented in its own README,
is not used by any consumer: it is a hit.

The match is a token match, not an import resolver, so it errs toward "used" (a common word such as `run` next to the package
name counts). Every hit is therefore a real candidate; a miss is possible. Docs, ADRs, the catalog and the ledger are not
consumers and are not read.

A hit is one dead name; each package with hits is a row with an exact count. Reason prefixes:

- `debt:` the names are owed a decision at reconciliation: delete them, or find the consumer that should use them; the reason
  lists them
- `outcome:` the name is public for a reader outside this repo and is documented as such
"""

from __future__ import annotations

import ast
import os
import re
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from any_arch import Row, Rule, check, plant

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent

_PRUNE = frozenset(  # dot folders are skipped too: caches, the venv, other worktrees
    {
        "node_modules",
        "__pycache__",
        "docs",
        "catalog",
        "ledger",
        "openspec",
    }
)
_READ = frozenset({".py", ".md", ".toml", ".yaml", ".yml", ".json", ".feature", ".cfg", ".txt", ".sh", ".just"})
_ROOTS = ("packages", "tests", "tools", "skills", "use-cases", "evals")  # where a consumer can live; nothing else is read
_ROOT_FILES = ["pyproject.toml", "README.md", "justfile", "conftest.py"]
_SKIP_NAMES = frozenset({"CHANGELOG.md", "uv.lock"})
_ARCH_FILES = ("tests/test_arch_", "tests/arch_")  # rows and reasons name things without using them
_SKIP_RELS = frozenset({"use-cases/README.md"})  # derived index of the use-cases, not a consumer
_WORD = re.compile(r"\w+")


@cache
def _corpus(root: Path) -> dict[str, tuple[str, frozenset[str]]]:
    """rel path -> (text, its word tokens) of every file a consumer could use a name in."""
    found: dict[str, tuple[str, frozenset[str]]] = {}
    walks = [(str(root), [], [f for f in _ROOT_FILES if (root / f).is_file()])]
    walks += [(folder, dirs, files) for top in _ROOTS for folder, dirs, files in os.walk(root / top)]
    for folder, dirs, files in walks:
        dirs[:] = [d for d in dirs if d not in _PRUNE and not d.startswith(".") and not d.endswith(".egg-info")]
        for name in files:
            path = Path(folder, name)
            if (
                name in _SKIP_NAMES
                or path.relative_to(root).as_posix() in _SKIP_RELS
                or name == Path(__file__).name
                or (path.suffix not in _READ and name != "justfile")
            ):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            found[path.relative_to(root).as_posix()] = (text, frozenset(_WORD.findall(text)))
    return found


def _exports(tree: ast.Module) -> list[ast.Constant]:
    """The string elements of the module's `__all__` list or tuple."""
    for node in tree.body:
        value = node.value if isinstance(node, ast.Assign | ast.AnnAssign) else None
        names = [t.id for t in node.targets if isinstance(t, ast.Name)] if isinstance(node, ast.Assign) else []
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        if "__all__" in names and isinstance(value, ast.List | ast.Tuple):
            return [e for e in value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


def _uses(root: Path, package: str, module: str, name: str) -> bool:
    own = f"packages/{package}/"
    for rel, (text, tokens) in _corpus(root).items():
        if rel.startswith(own):
            if rel == f"{own}pyproject.toml":
                if re.search(rf"\b{module}[\w.]*:{name}\b", text) or (name.startswith("pytest_") and "entry-points.pytest11" in text):
                    return True  # a script or entry-point target, or a hook of a pytest plugin module
                continue
            if not (rel.startswith(f"{own}src/") and rel.endswith("/__main__.py")):
                continue
        if rel.startswith(_ARCH_FILES):
            if re.search(rf"from {module}(?:\.\w+)* import (?:\([^)]*|[^\n]*)\b{name}\b", text):
                return True  # an arch test lists names in its rows; only an import of the name is use
            continue
        if name in tokens and (module in tokens or package in text):
            return True
    return False


def _unused(root: Path) -> Rule:
    def find(source: Source) -> Iterator[Hit]:
        match = re.fullmatch(r"packages/([^/]+)/src/([^/]+)/__init__\.py", source.rel)
        if match is None:
            return
        package, module = match.groups()
        for element in _exports(source.tree):
            name = str(element.value)
            if not name.startswith("__") and not _uses(root, package, module, name):
                yield package, element.lineno

    return Rule(
        "dead-public-api",
        "a name in `__all__` that nothing outside its package uses (delete it, or add a reasoned row until reconciliation decides)",
        find,
        _ALLOWED,
        ("debt", "outcome"),
    )


# package, names with no in-repo user, public names in all, the first of those names, consumers outside this repo (use-cases)
_DEAD = (
    ("a2effect", 4, 9, "ErrorKind, Raises, register_error_kind, translate_to", "a2kay, a2web"),
    ("any-agent", 17, 37, "AccessPolicy, ClaudeAccess, ClaudePermissionMode, CodexAccess, CodexApproval and 12 more", "iorlas-task-loop"),
    ("any-breaker", 13, 19, "CLOSED, OK, OPEN, OUT, RELEASE and 8 more", "delegate"),
    ("any-browser", 3, 9, "camoufox_launcher, chromium_launch, patchright_launcher", "a2web"),
    ("any-clock", 1, 3, "PhaseClock", "task-loop"),
    ("any-disk", 5, 6, "GIB, Verdict, await_space_async, space_verdict, verdict", "channel-research"),
    ("any-failure-fp", 4, 8, "Event, Trip, head, seen_within", "task-loop"),
    ("any-file", 6, 17, "DEFAULT_SLUG_LENGTH, OCTET_STREAM, REGISTERED_TYPES, SECRET_NAME_PATTERNS, TEXT_MEDIA_TYPES and 1 more", "a2kay"),
    ("any-frontmatter", 5, 19, "FENCE, WriteOutcome, canonicalize, round_trip_yaml, written_nothing", "a2kay"),
    ("any-gate", 4, 9, "GateState, Resources, RunResult, run_runner", "shelf"),
    ("any-gate-python", 8, 13, "ExportError, Exporter, Rules, affected_packages, lock_touched and 3 more", "shelf"),
    ("any-json-doc", 4, 11, "ConflictError, Read, RefusedError, refusal", "task-loop"),
    ("any-lease", 3, 8, "HeldAll, Occupant, Pacer", "iorlas-task-loop"),
    ("any-markdown", 12, 16, "ATX_HEADING_RE, WIKILINK_RE, Chunk, Section, View and 7 more", "a2kay, ogy"),
    ("any-net", 4, 8, "Probe, View, looks_dropped, view", "delegate"),
    ("any-path-glob", 1, 3, "GlobError", "lifesim"),
    ("any-pipeline", 6, 19, "MemoryStore, Ok, Outcome, StageFailed, gather3 and 1 more", "none"),
    ("any-plugin-cache", 7, 9, "NoVersionError, entry_offset, installed_version, previous, rollback_target and 2 more", "task-loop"),
    ("any-recorded-fixture", 1, 9, "GoldenMismatchError", "iorlas-task-loop"),
    ("any-shell-policy", 4, 7, "Rule, Verdict, has_write_syntax, strip_excluded", "task-loop"),
    (
        "any-speech",
        29,
        37,
        "CARDS, DEFAULT_BUDGET_GB, AudioHasher, Diarized, Diarizer and 24 more",
        "channel-research, iorlas-perform, personal-brand",
    ),
    ("any-ttl-cache", 2, 3, "EXPIRES, Entry", "none"),
    ("any-versioned", 1, 3, "Migration", "none"),
    ("any-work", 6, 10, "ClassifiedError, Item, Kind, Progress, RetryRow and 1 more", "channel-research"),
    ("anyembed", 4, 5, "AnyEmbedError, EmbeddingCache, LlamaCppEmbedder, LocalEmbedder", "a2kay"),
    (
        "anyllm",
        22,
        25,
        "DEFAULT_COST_POLICY, DEFAULT_ORDER, DEFAULT_PROVIDER, AnthropicApiAdapter, ClaudeCodeCliAdapter and 17 more",
        "a2kay, a2web",
    ),
    ("app-dirs", 3, 10, "PLUGIN_DATA_ENV, Kind, plugin_data_dir", "iorlas-task-loop"),
    ("argparse-mcp", 2, 3, "Result, Run", "ogy"),
    ("asgi-token-gate", 6, 10, "ASGIApp, Receive, Resolver, Scope, Send and 1 more", "a2kay"),
    ("atomic-io", 1, 6, "atomic_replace_json", "a2kay"),
    ("bdd-tags", 3, 6, "KNOWN_BUG, PENDING, TRACE_PREFIXES", "a2kay"),
    ("beads-client", 15, 17, "DEP_BLOCKS, TESTED_BELOW, TESTED_FROM, BdError, BdRun and 10 more", "task-loop"),
    (
        "child-env",
        8,
        13,
        "APP_NAMES, APP_PREFIXES, CREDENTIAL_MARKERS, CREDENTIAL_NAMES, CREDENTIAL_PREFIXES and 3 more",
        "iorlas-task-loop",
    ),
    ("convert-md", 14, 18, "ConversionEngine, ConversionError, ConversionResult, Fidelity, Html2TextEngine and 9 more", "a2kay"),
    ("dom-schema", 2, 5, "Extraction, Field", "a2web"),
    ("duckdb-sidecar", 1, 4, "is_index_drift", "a2kay"),
    ("due-schedule", 5, 6, "cron_is_due, is_cron_like, is_due, is_valid_cron, parse_interval", "a2kay"),
    ("fts-query", 5, 12, "DEFAULT_TOKENIZE, NO_FOLD, FtsQueryError, is_identifier_token, unstemmed", "a2kay"),
    ("git-porcelain", 108, 120, "DEFAULT_TIMEOUT, BranchExists, BranchHeld, BranchPinned, BranchTaken and 103 more", "a2kay, ogy"),
    ("http-fetch", 6, 9, "DEFAULT_MAX_BODY_BYTES, LinkChecker, LinkReply, LinkResult, LinkState and 1 more", "a2web"),
    ("json-in-html", 3, 10, "JsonSource, ld_entries, microdata_to_ld", "a2web"),
    ("jsonl-log", 17, 22, "LOCK_TIMEOUT, ROTATE_BYTES, Entry, Jsonl, JsonlLogError and 12 more", "a2kay"),
    ("launchd-agent", 9, 16, "EXIT_TIMEOUT, LAUNCHCTL_TIMEOUT_S, LAUNCHD_PATH, Launchctl, LaunchctlResult and 4 more", "a2kay"),
    ("llm-cache", 1, 3, "LlmCache", "a2web"),
    ("llm-wobble", 7, 15, "BoundFunnel, bind, emit_wobble, recovered_fields, strip_all_fenced_blocks and 2 more", "a2kay, a2web"),
    ("managed-region", 1, 1, "replace_region", "a2kay"),
    ("mcp-arg-errors", 6, 8, "DETAILS_CHARS, STALE_TOOL_LIST_HINT, ArgumentFault, TypedError, argument_fault and 1 more", "a2kay"),
    ("mcp-bridge", 3, 4, "DEFAULT_WAIT, downstream_client_name, refused", "a2kay"),
    ("mcp-call", 4, 6, "PROTOCOL_VERSION, McpCallError, ServerInfo, ToolResult", "a2kay"),
    ("mcp-clients", 2, 6, "McpClient, configured_servers", "a2kay"),
    ("mcp-feedback", 1, 2, "FeedbackReportResult", "a2web"),
    ("mcp-result-wire", 1, 3, "ListViewSettings", "a2kay"),
    ("mcp-steps", 5, 6, "AGENT, SOMEONE_ELSE, McpWorld, refusal_of, result_of", "a2kay"),
    ("page-tsv", 13, 19, "FormatHint, FormatHintInferred, FormatName, Rendered, Response and 8 more", "a2kay"),
    ("path-pattern", 2, 8, "PLACEHOLDER_RE, Placeholder", "a2kay"),
    ("plugin-surface", 4, 8, "Described, Problem, describe_directory, describe_file", "a2web"),
    ("settings-base", 1, 4, "ConfigOverrideError", "a2web"),
    ("shelf-vendor", 3, 5, "dir_files, newer_tags, tag_files", "iorlas-task-loop"),
    ("sqlite-resource", 1, 2, "OnOpen", "a2web"),
    ("sqlite-sidecar", 5, 18, "MARK_SUFFIX, ExtensionUnavailableError, connect_read_only, from_text_utc, needs_rebuild", "a2kay"),
    ("sqlite-store", 6, 14, "SharedConnections, SqlValue, Step, cas_update, clear_filesystem_cache and 1 more", "iorlas-task-loop"),
    ("stream-proc", 9, 30, "IdentityUnavailableError, Kind, PidHandle, ProcessObservation, TermHold and 4 more", "delegate, task-loop"),
    ("task-spec", 2, 8, "Ask, AskKind", "iorlas-task-loop"),
    ("timefmt", 5, 6, "fmt_span, fmt_until, human_count, parse_until, to_epoch", "a2web"),
    ("verb-cli", 3, 10, "FlagSpec, VerbCliError, choice_flags_of", "a2kay, ogy"),
)

_ALLOWED = {
    package: Row(
        f"debt: {count} of {total} public names have no in-repo user ({names}); external consumers: {external}; "
        "drop them from `__all__` and delete what only they kept alive, or name the consumer that should use them",
        count,
    )
    for package, count, total, names, external in _DEAD
}

DEAD_PUBLIC_API = _unused(_ROOT)


def test_every_public_name_has_a_consumer_or_a_reasoned_row() -> None:
    check(DEAD_PUBLIC_API, _ROOT)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


_INIT_PATH = "packages/a/src/a/__init__.py"
_INIT = '__all__ = [\n    "dead",\n    "entry",\n    "kept",\n    "main_only",\n    "off_in_readme",\n]\n'


def test_a_planted_name_nothing_outside_the_package_uses_is_a_hit(tmp_path: Path) -> None:
    _write(tmp_path, "packages/b/src/b/m.py", "from a import kept\n")
    _write(tmp_path, "packages/a/tests/test_a.py", "from a import dead\n")  # its own tests are not a consumer
    _write(tmp_path, "packages/a/README.md", "`off_in_readme` and `dead` are documented here\n")
    _write(tmp_path, "packages/a/pyproject.toml", '[project.scripts]\na = "a.cli:entry"\n')
    _write(tmp_path, "packages/a/src/a/__main__.py", "from a import main_only\n")
    assert plant(_unused(tmp_path), tmp_path, _INIT, path=_INIT_PATH) == {"a": [2, 6]}  # `dead` and `off_in_readme`


def test_a_use_in_a_use_case_file_or_another_packages_tests_counts(tmp_path: Path) -> None:
    _write(tmp_path, "use-cases/x--a.toml", 'software = "a"\nneeds = "dead and off_in_readme"\n')
    _write(tmp_path, "packages/b/tests/test_b.py", "import a\na.entry\na.kept\na.main_only\n")
    assert plant(_unused(tmp_path), tmp_path, _INIT, path=_INIT_PATH) == {}


def test_an_arch_test_uses_a_name_only_by_importing_it_and_the_use_case_index_is_no_consumer(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_arch_x.py", "from a import (\n    kept,\n    entry,\n)\n# dead and off_in_readme are named in a row\n")
    _write(tmp_path, "use-cases/README.md", "a: dead, off_in_readme, main_only\n")
    assert plant(_unused(tmp_path), tmp_path, _INIT, path=_INIT_PATH) == {"a": [2, 5, 6]}


@pytest.mark.parametrize(("name", "expected"), [("__version__", {}), ("_private", {"a": [1]})])
def test_a_dunder_is_not_a_public_name(tmp_path: Path, name: str, expected: dict[str, list[int]]) -> None:
    assert plant(_unused(tmp_path), tmp_path, f'__all__ = ["{name}"]\n', path=_INIT_PATH) == expected
