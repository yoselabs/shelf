"""Gate: one command decides Done, and the hooks and CI run that same command."""

from __future__ import annotations

import itertools
import json
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING

from blueprint import gate_graph
from blueprint.model import (
    Context,
    Finding,
    FixedBy,
    Verdict,
    check,
    failing,
    is_skipped,
    not_applicable,
    not_checked,
    not_set_up,
    passing,
    walk,
)

if TYPE_CHECKING:
    import subprocess

    from blueprint.gate_graph import Gate

# `make check`, `just check-all`, `uv run just check`, `uvx rust-just@1.58.0 check`: a step that runs the gate.
_GATE_RUN = re.compile(r"\b(?:make|just|rust-just(?:@\S+)?)\s+(?:-\S+\s+)*check(?:-all)?\b")
_USES = re.compile(r"^\s*-?\s*uses:\s*['\"]?([^\s'\"#]+)", re.MULTILINE)
_SHA = re.compile(r"@[0-9a-f]{40}$")
# A script a recipe runs: `python3 x.py`, `uv run python x.py`, or `g=x.py` handed to python later.
# `python3 -I tools/x.py`: interpreter flags before the script (the recipes are run isolated) still name it.
_SCRIPT = re.compile(r"(?:python3?(?:\s+-\w+)*\s+|uv run python(?:\s+-\w+)*\s+|\b[A-Za-z_]\w*=)((?:[\w.-]+/)*[\w.-]+\.py)\b")
_ONBOARD = (
    "the shelf onboarding writes the gate: `just bootstrap`, or python3 <shelf>/.agents/skills/onboard-consumer/scripts/onboard.py --repo ."
)


@check("gate.one-command", "`just check` exists and every recipe it names resolves")
def one_command(ctx: Context) -> Finding:
    """The justfile has a `check` recipe and `just --dry-run check` resolves (a Makefile: `make -n check`)."""
    python = any(s.startswith("python") for s in ctx.profile.stacks)
    generic = "add a justfile whose `check` recipe runs every linter and the tests"
    if not ctx.profile.stacks:
        generic += (
            '; no code yet? declare the stack it will have, `[profile] stacks = ["python-uv"]` in '
            "docs/blueprint/blueprint.toml, for its own fix"
        )
    fixer = (_ONBOARD, FixedBy.AUTO) if python else (generic, FixedBy.AGENT)
    gate = gate_graph.load(ctx)
    if gate is None:
        return not_set_up("no justfile", *fixer)
    if not gate.has_recipe("check"):
        if gate.unread and gate.runner == "just":
            return not_checked(f"the justfile cannot be read: {gate.unread} (pin the runner: `uv add --dev rust-just`)")
        return not_set_up(f"the {gate.path} has no `check` {'recipe' if gate.runner == 'just' else 'target'}", *fixer)
    argv = _DRY_RUN[gate.runner]
    dry = ctx.run(gate_graph.just_command(ctx) if gate.runner == "just" else argv[0], *argv[1:], timeout=60)
    shown = " ".join(argv)
    if dry is None:
        return not_checked(f"`{gate.runner}` is not installed or timed out")
    if dry.returncode != 0:
        lines = (dry.stderr.strip() or dry.stdout.strip()).splitlines() or ["no output"]
        # just prints "error: <what>" first and a source excerpt after it; make's last line is the error.
        complaint = next((line for line in lines if line.startswith("error")), lines[-1])
        return failing(f"`{shown}` fails: {complaint}", "add or fix the recipe the gate names")
    return passing(f"`{shown}` resolves")


_DRY_RUN = {"just": ("just", "--dry-run", "check"), "make": ("make", "-n", "check")}
_MIGRATION = (
    "move the Makefile to a justfile (ADR 0023): `uv add --dev rust-just`, port each target to a recipe "
    "(same names; loops go in shebang recipes; no backticks), run it as `uv run just check`, delete the Makefile; "
    "the shelf's own justfile is the reference"
)


@check("gate.runner", "the gate runner is just: a justfile holds the gate, not a Makefile")
def runner(ctx: Context) -> Finding:
    """One runner for every repo, so blueprint reads the gate graph from one JSON dump (ADR 0023)."""
    if gate_graph.load(ctx) is None:
        return not_applicable("no gate: gate.one-command reports the missing one")
    if gate_graph.has_makefile_only(ctx):
        return failing("the gate is a Makefile; the shelf's runner is just (a justfile)", _MIGRATION)
    return passing("a justfile holds the gate")


def _workflows(ctx: Context) -> list[Path]:
    wf = ctx.path(".github/workflows")
    return sorted([*wf.glob("*.yml"), *wf.glob("*.yaml")]) if wf.is_dir() else []


@check("gate.ci", "CI runs the gate command; every action is pinned to a commit SHA; permissions are declared")
def ci(ctx: Context) -> Finding:
    """GitHub Actions: some job runs `just check`/`check-all` (or make's); `uses:` pinned by SHA; top-level permissions."""
    files = _workflows(ctx)
    if not files:
        if ctx.read(".gitlab-ci.yml") is not None:
            return not_checked("GitLab CI is not checked yet; blueprint covers GitHub Actions")
        return not_set_up(
            "no .github/workflows/*.yml",
            "add a workflow that runs `uv run just check-all` (or `just check`) on push and pull request; "
            "a repo that decided on no CI records an override of gate.ci with its reason and "
            '`adr = "NNNN"` (the accepted ADR that decided it)',
        )
    problems: list[str] = []
    if not any(_GATE_RUN.search(f.read_text()) for f in files):
        problems.append("no workflow runs the gate (`just check` or `just check-all`)")
    for f in files:
        text = f.read_text()
        unpinned = sorted({u for u in _USES.findall(text) if not u.startswith(("./", "docker://")) and not _SHA.search(u)})
        if unpinned:
            problems.append(f"{f.name}: not pinned to a SHA: {', '.join(unpinned)}")
        if not re.search(r"^permissions:", text, re.MULTILINE):
            problems.append(f"{f.name}: no top-level `permissions:`")
    if problems:
        return failing(
            "; ".join(problems),
            "run the gate word in CI; pin each action as `owner/repo@<40-hex sha> # vX`; add `permissions: contents: read`",
        )
    return passing(f"{len(files)} workflow(s) run the gate, pinned, with permissions")


@dataclass(frozen=True)
class _Step:
    job: str
    name: str
    run: str


_JOB = re.compile(r"^ {2}([\w.-]+):\s*(?:#.*)?$")
_ITEM = re.compile(r"^(\s*)-\s+(.*)$")


def _step_chunks(workflow: str) -> list[tuple[str, list[str]]]:
    """(job, lines) per step, in file order; each chunk's first line is the `- ` item with its marker blanked."""
    job, item_indent, in_jobs = "", None, False
    chunks: list[tuple[str, list[str]]] = []
    for line in workflow.splitlines():
        if re.match(r"^jobs:\s*$", line):
            in_jobs = True
        elif in_jobs and (m := _JOB.match(line)):
            job, item_indent = m.group(1), None
        elif in_jobs and re.match(r"^\s+steps:\s*$", line):
            item_indent = None
        elif in_jobs and job and (m := _ITEM.match(line)) and item_indent in (None, len(m.group(1))):
            item_indent = len(m.group(1))
            chunks.append((job, [" " * (item_indent + 2) + m.group(2)]))
        elif chunks and item_indent is not None and (not line.strip() or len(line) - len(line.lstrip()) > item_indent):
            chunks[-1][1].append(line)
    return chunks


def _block_scalar(lines: list[str], indent: int) -> str:
    """The lines of a `|` or `>` value: everything indented deeper than its key."""
    block: list[str] = []
    for line in lines:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        block.append(line.strip())
    return "\n".join(block)


def _unquoted(value: str) -> str:
    return value[1:-1] if len(value) > 1 and value[0] == value[-1] and value[0] in "'\"" else value


def _steps(workflow: str) -> list[_Step]:
    """The steps of every job, in file order, with their name and `run` text.

    A line-wise reading: stdlib has no YAML parser, and a workflow's steps are regular enough that the
    `- ` items under `steps:` give each one's keys at a fixed indent.
    """
    steps: list[_Step] = []
    for job, lines in _step_chunks(workflow):
        indent = len(lines[0]) - len(lines[0].lstrip())
        fields: dict[str, str] = {}
        for i, line in enumerate(lines):
            if key := re.match(rf"^ {{{indent}}}(name|run):\s*(.*)$", line):
                value = key.group(2).strip()
                fields[key.group(1)] = _block_scalar(lines[i + 1 :], indent) if value[:1] in {"|", ">"} else _unquoted(value)
        steps.append(_Step(job, fields.get("name", ""), fields.get("run", "")))
    return steps


_MANIFESTS = (
    r"(?:[\w./-]*/)?(?:pyproject\.toml|uv\.lock|poetry\.lock|requirements[\w.-]*\.txt|package\.json|package-lock\.json|yarn\.lock|"
    r"pnpm-lock\.yaml|Cargo\.toml|Cargo\.lock|go\.mod|go\.sum|Directory\.Packages\.props|packages\.lock\.json|[\w.-]+\.csproj)"
)
_WRITES_MANIFEST = re.compile(
    rf"\bsed\b[^\n]*\s-[A-Za-z]*i\b[^\n]*{_MANIFESTS}|\btee\b[^\n]*{_MANIFESTS}|>>?\s*{_MANIFESTS}", re.IGNORECASE
)
# Each rewrites the lockfile unless told not to; the installing form that fails on a stale lock is named in the remediation.
_LOCK_REWRITERS = (
    (re.compile(r"^uv (?:lock|sync)\b"), re.compile(r"--(?:check|locked|frozen)\b"), "uv lock/sync without --locked or --frozen"),
    (re.compile(r"^uv (?:add|remove)\b"), None, "uv add/remove"),
    (re.compile(r"^poetry (?:lock|update|add)\b"), None, "poetry lock/update/add"),
    (re.compile(r"^npm (?:install|i|update)(?:\s+-{1,2}[\w-]+)*$"), re.compile(r"\s(?:-g|--global)\b"), "npm install instead of npm ci"),
    (re.compile(r"^cargo update\b"), None, "cargo update"),
)


def _rewrites(run_text: str) -> str | None:
    """What in a step's shell text rewrites the dependency set, or None."""
    if written := _WRITES_MANIFEST.search(run_text):
        target = re.search(_MANIFESTS, written.group(0), re.IGNORECASE)
        return f"writes {target.group(0) if target else 'a manifest or lockfile'}"
    for raw in re.split(r"&&|\|\||;|\n", run_text):
        command = raw.strip()
        for starts, exempt, label in _LOCK_REWRITERS:
            if starts.match(command) and not (exempt and exempt.search(command)):
                return label
    return None


@check("gate.ci-no-manifest-edit", "no CI step before the gate rewrites a dependency manifest or lockfile")
def ci_no_manifest_edit(ctx: Context) -> Finding:
    """CI gates the committed dependency set: a step ahead of `just check` that edits pyproject.toml or re-locks gates another one."""
    files = _workflows(ctx)
    if not files:
        return not_applicable("no .github/workflows: gate.ci reports the missing CI")
    parsed = {f.name: _steps(f.read_text()) for f in files}
    gated = any(_GATE_RUN.search(step.run) for steps in parsed.values() for step in steps)
    found: list[str] = []
    for name, steps in parsed.items():
        for job in dict.fromkeys(step.job for step in steps):
            job_steps = [step for step in steps if step.job == job]
            gate_at = next((i for i, step in enumerate(job_steps) if _GATE_RUN.search(step.run)), None)
            if gate_at is None and gated:
                continue  # another job is the gate; this one gates nothing
            found += [
                f"{name} job {job} step {step.name or step.run.splitlines()[0][:40]!r}: {what}"
                for step in job_steps[:gate_at]
                if (what := _rewrites(step.run)) is not None
            ]
    if found:
        return failing(
            "; ".join(found),
            "commit the change instead of patching it in CI; install with the locked form (`uv sync --locked`, `npm ci`)",
        )
    return passing(f"{len(files)} workflow(s): no step before the gate edits a manifest or re-locks")


# Hooks (research/hooks-and-beads.md): prek owns them through .pre-commit-config.yaml, and bd's hooks
# run from that file (`bd hooks run <event>`), never installed by bd itself. bd appends its block to
# other managers' hook files, where a failing check then no longer blocks the commit.
HOOK_CONFIG = ".pre-commit-config.yaml"
BD_EVENTS = ("pre-commit", "post-merge", "pre-push", "post-checkout", "prepare-commit-msg")
_OTHER_MANAGERS = {
    "lefthook": ("lefthook.yml", "lefthook.yaml", ".lefthook.yml", ".lefthook.yaml"),
    "husky": (".husky",),
    "githooks": (".githooks",),
}
_RECIPE = "PYTHONPATH=<shelf>/packages/blueprint/src python3 -m blueprint recipe hooks > .pre-commit-config.yaml; then `prek install`"
_BEADS_MARKER = "BEGIN BEADS INTEGRATION"


# The fix for an existing hook config: merge the recipe in (shelf-3gl: `>` destroyed homelab's own ~20 hooks). Its `gate`
# hook stays: it is pre-push only and `prek run --all-files` runs the pre-commit stage, so a gate that runs the hooks does
# not recurse through it (homelab, 2026-10-11).
_MERGE_FIX = (
    f"merge the recipe into the existing {HOOK_CONFIG}, never overwrite it: `default_install_hook_types` at the top, the "
    "recipe's bd `repo: local` block first under `repos:`, and keep every hook the repo already has after it "
    "(`python3 -m blueprint recipe hooks` prints the recipe); then `prek install`"
)


_HOOK_START = re.compile(r"^\s*-\s*id:", re.MULTILINE)


def _pre_push_gate(config: str) -> bool:
    """Whether a hook staged on pre-push runs the gate (`just check`, or `make check` before the runner moved)."""
    starts = [m.start() for m in _HOOK_START.finditer(config)] + [len(config)]
    blocks = (config[a:b] for a, b in itertools.pairwise(starts))
    return any(re.search(r"\b(?:just|make) check\b", b) and re.search(r"stages:.*pre-push", b) for b in blocks)


@check(
    "gate.hooks-recipe",
    "prek owns the git hooks through .pre-commit-config.yaml, bd's hooks run from it, pre-push runs the gate",
    version=3,
)
def hooks_recipe(ctx: Context) -> Finding:
    """The versioned half of the recipe: one config, bd's five events in it, no bd-owned hook files tracked."""
    others = [name for name, files in _OTHER_MANAGERS.items() if any(ctx.path(f).exists() for f in files)]
    config = ctx.read(HOOK_CONFIG)
    tracked = (ctx.git("ls-files", ".beads/hooks", ".beads-hooks") or "").split()
    problems: list[str] = []
    if others:
        problems.append(f"hooks also owned by {', '.join(others)}: move their checks into {HOOK_CONFIG} and delete them")
    if tracked:
        problems.append(f"bd's own hook files are tracked ({len(tracked)}): git rm -r --cached .beads/hooks")
    if config is None:
        return not_set_up("; ".join(["no .pre-commit-config.yaml", *problems]), _RECIPE, FixedBy.AUTO)
    if ctx.profile.tracker == "beads":
        missing = [e for e in BD_EVENTS if f"bd hooks run {e}" not in config]
        if missing:
            problems.append(f"bd events not run from {HOOK_CONFIG}: {', '.join(missing)}")
        if "default_install_hook_types" not in config:
            problems.append("no default_install_hook_types, so `prek install` installs pre-commit only")
    if not _pre_push_gate(config):
        problems.append("no pre-push hook runs `just check`, so a push skips the gate (the recipe's `gate` hook)")
    if problems:
        return failing("; ".join(problems), _MERGE_FIX)
    return passing(f"{HOOK_CONFIG} owns the hooks" + (", bd's five events run from it" if ctx.profile.tracker == "beads" else ""))


@check("gate.hooks-installed", "the installed git hooks are prek's, in .git/hooks, with no bd block injected", version=2, audit_only=True)
def hooks_installed(ctx: Context) -> Finding:
    """The clone-local half: core.hooksPath unset, prek's (or pre-commit's) script installed, no bd marker."""
    if ctx.git("rev-parse", "--git-dir") is None:
        return not_checked("not a git repository")
    fix = "bd hooks uninstall; git config --unset core.hooksPath; prek install"
    hooks_path = (ctx.git("config", "--local", "core.hooksPath") or "").strip()
    if hooks_path:
        return failing(f"core.hooksPath is {hooks_path}: a fresh clone runs no hooks, and prek refuses to install", fix, FixedBy.AUTO)
    hooks_dir = Path((ctx.git("rev-parse", "--git-path", "hooks") or ".git/hooks").strip())
    hooks_dir = hooks_dir if hooks_dir.is_absolute() else ctx.repo / hooks_dir
    pre_commit = hooks_dir / "pre-commit"
    if not pre_commit.is_file():
        return not_set_up("no pre-commit hook installed", "prek install", FixedBy.AUTO)
    injected = sorted(p.name for p in hooks_dir.iterdir() if p.is_file() and _BEADS_MARKER in p.read_text(errors="replace"))
    if injected:
        return failing(f"bd injected its block into {', '.join(injected)}", fix, FixedBy.AUTO)
    text = pre_commit.read_text(errors="replace")
    if "File generated by prek" not in text and "File generated by pre-commit" not in text:
        return failing("the pre-commit hook is not prek's", "prek install --overwrite", FixedBy.AUTO)
    return passing("prek's hooks installed in .git/hooks; no bd block injected")


_HOOK_ENTRY = re.compile(r"^\s*(?:-\s*)?entry:\s*(.+?)\s*$", re.MULTILINE)
# Any `.py` path in a hook's entry (`uv run tools/x.py`, `python x.py`, a bare path); a glob such as `test_*.py` has no match.
_HOOK_SCRIPT = re.compile(r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.py)\b")


def _hook_entries(ctx: Context, recipes: str) -> list[str]:
    """The `entry:` lines of .pre-commit-config.yaml when the gate runs the hooks (`pre-commit run`, `prek run`).

    Why: a gate that runs pre-commit runs every hook's command, and the repo's own guards are usually among them.
    """
    if not gate_graph.HOOK_RUN.search(recipes):
        return []
    return _HOOK_ENTRY.findall(ctx.read(HOOK_CONFIG) or "")


def _gate_commands(ctx: Context, gate: Gate) -> str:
    """Everything the gate runs: its recipes (variables expanded) and the hook commands it triggers."""
    recipes = gate.gate_recipes()
    return "\n".join([recipes, *_hook_entries(ctx, recipes)])


def _gate_scripts(ctx: Context, gate: Gate) -> list[str]:
    found = [m for recipe in gate.reachable() for m in _SCRIPT.findall(recipe)]
    for entry in _hook_entries(ctx, gate.gate_recipes()):
        found += [m for m in _HOOK_SCRIPT.findall(entry) if not Path(m).name.startswith("test_")]
    return list(dict.fromkeys(m for m in found if ctx.path(m).is_file()))


# The tracked files blueprint reads. A container gate whose image leaves one out judges a different repo.
_BLUEPRINT_READS = (
    "justfile",
    "Makefile",
    "AGENTS.md",
    "CLAUDE.md",
    ".gitignore",
    ".pre-commit-config.yaml",
    ".beads/config.yaml",
    ".beads/.gitignore",
    ".claude/settings.json",
    "docs/blueprint/blueprint.toml",
    "docs/agents/*",
    ".github/workflows/*",
)
_DOCKER_BUILD = re.compile(r"\bdocker\s+(?:buildx\s+)?build\b")
_DOCKER_FILE_FLAG = re.compile(r"\bdocker\s+(?:buildx\s+)?build\b[^\n]*?\s(?:-f|--file)[\s=](\S+)")


def _ignore_regex(pattern: str) -> re.Pattern[str]:
    """A .dockerignore pattern as a regex over a slash path (`*` stays inside a folder, `**` crosses them)."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        else:
            out += {"*": "[^/]*", "?": "[^/]"}.get(pattern[i], re.escape(pattern[i]))
            i += 1
    return re.compile(f"^{out}$")


def _dropped(path: str, ignore: str) -> bool:
    """Whether the image's ignore file leaves `path` out of the build context: the last matching line wins, `!` re-includes."""
    parts = path.split("/")
    prefixes = ["/".join(parts[: i + 1]) for i in range(len(parts))]
    dropped = False
    for raw in ignore.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        regex = _ignore_regex(line.lstrip("!").strip("/"))
        # A pattern naming a folder drops everything under it, so any parent of the file counts.
        if any(regex.match(prefix) for prefix in prefixes):
            dropped = not negated
    return dropped


def _image_ignores(ctx: Context, gate_text: str) -> dict[str, str]:
    """Ignore file name -> text, for each image the gate file builds: `<Dockerfile>.dockerignore` first, else the root one."""
    if not _DOCKER_BUILD.search(gate_text):
        return {}
    ignores: dict[str, str] = {}
    for dockerfile in _DOCKER_FILE_FLAG.findall(gate_text) or [""]:
        for name in (f"{dockerfile}.dockerignore" if dockerfile else "", ".dockerignore"):
            if name and (text := ctx.read(name)) is not None:
                ignores[name] = text
                break
    return ignores


def _dropped_reads(ctx: Context, gate_text: str) -> list[str]:
    tracked = (ctx.git("ls-files") or "").splitlines()
    reads = [f for f in tracked if any(fnmatch(f, pattern) for pattern in _BLUEPRINT_READS)]
    return [f"{name} drops {f}" for name, text in _image_ignores(ctx, gate_text).items() for f in reads if _dropped(f, text)]


@check(
    "gate.runs-blueprint",
    "`just check` runs blueprint's per-commit checkpoints (`just blueprint`), on the files blueprint reads",
    version=2,
)
def runs_blueprint(ctx: Context) -> Finding:
    """Gaps come back between audits unless the repo's own gate re-checks them on every commit."""
    gate = gate_graph.load(ctx)
    if gate is None:
        return not_applicable("no justfile: gate.one-command reports the missing gate")
    if "blueprint check" not in gate.gate_recipes():
        return not_set_up(
            "`just check` never runs blueprint",
            "copy the shelf's `blueprint` recipe into the justfile and add it to `check` (`just bootstrap` does both)",
            FixedBy.AUTO,
        )
    dropped = _dropped_reads(ctx, gate.text)
    if dropped:
        return failing(
            f"the gate image's ignore file leaves out tracked files blueprint reads: {'; '.join(dropped)}",
            "re-include each with a `!<path>` line after the drop (a container without .beads/config.yaml reports a false 'no tracker'), "
            "or keep the file in the build context; docs/agents/gate.md lists what a container gate must carry",
        )
    return passing("`just check` reaches `blueprint check --gate`")


@check("gate.guards-have-red-tests", "every repo-local script `just check` runs has a test that names it", version=2)
def guards_have_red_tests(ctx: Context) -> Finding:
    """Each repo `*.py` that `just check` reaches, in a recipe or through its pre-commit hooks, is named by some test file.

    A guard never seen red is a hypothesis.
    """
    gate = gate_graph.load(ctx)
    if gate is None:
        return not_applicable("no justfile, so no guard scripts")
    scripts = _gate_scripts(ctx, gate)
    if not scripts:
        return not_applicable("`just check` runs no repo-local Python script")
    tests = [p.read_text(errors="replace") for p in walk(ctx.repo, "test_*.py")]
    # An unchanged copy of a blueprint recipe is tested where it is written, in the shelf; an edited copy is the repo's own.
    recipes = [s for s in scripts if _is_recipe_copy(ctx, s)]
    untested = [s for s in scripts if s not in recipes and not any(Path(s).stem in t or Path(s).stem.replace("-", "_") in t for t in tests)]
    if untested:
        return failing(
            f"no test names {', '.join(untested)}",
            # A gate script is a guard (it fails the gate on a violation) or a helper the gate calls (a2kay's container slot queue).
            "add a test per script: for a guard, plant the violation it guards against and assert it fails; "
            "for a helper (a queue, a generator, a launcher), test the behaviour the gate relies on",
        )
    copied = f"; {', '.join(recipes)} unchanged from a blueprint recipe, tested in the shelf" if recipes else ""
    return passing(f"{len(scripts)} script(s) ({', '.join(scripts)}), each named by a test{copied}")


_RECIPES = Path(__file__).resolve().parent.parent / "recipes"


def _is_recipe_copy(ctx: Context, script: str) -> bool:
    shipped = _RECIPES / Path(script).name
    return shipped.is_file() and ctx.read(script) == shipped.read_text()


# The runner's own trailer (`make: *** [check] Error 2`, "error: Recipe `lint` failed on line 9 ...") names no cause.
_RUNNER_LINE = re.compile(r"^(?:g?make(\[\d+\])?: |error: Recipe `)")


def _cause(done: subprocess.CompletedProcess[str]) -> str:
    """The last line of the failing run's output that the runner did not write itself; stderr first, it carries the error."""
    for stream in (done.stderr, done.stdout):
        lines = [line.strip() for line in stream.splitlines() if line.strip() and not _RUNNER_LINE.match(line.strip())]
        if lines:
            return lines[-1]
    return "no output"


def _judge_clone(done: subprocess.CompletedProcess[str] | None, took: int, budget: object, word: str = "just") -> Finding:
    if done is None:
        return failing(f"`{word} check` in a fresh clone did not finish within an hour", "find the step that hangs")
    if done.returncode != 0:
        return failing(f"`{word} check` fails in a fresh clone ({took}s): {_cause(done)}", "make the gate pass from a clean checkout")
    if not isinstance(budget, int):
        return not_set_up(
            f"fresh-clone gate passed in {took}s; no budget recorded",
            f"record `clean-clone-seconds = {took * 2}` under [settings] in docs/blueprint/blueprint.toml",
            FixedBy.AUTO,
        )
    if took > budget:
        return failing(
            f"fresh-clone gate took {took}s, budget {budget}s", "speed the gate up, or raise the budget with the owner", FixedBy.OWNER
        )
    return passing(f"fresh-clone gate passed in {took}s (budget {budget}s)")


# What a fresh clone needs before its gate can run, in order: until `mise trust` every mise shim refuses (uv
# included), and a beads repo's database is not in git, it is pulled from refs/dolt/data (a2kay: shelf-45k, 8q7).
_FRESH_CLONE_STEPS = (
    ("mise.toml", ("mise", "trust", "--yes", ".")),
    ("mise.toml", ("mise", "install", "--locked")),
    # The stack's sync once, before the gate's parallel steps each start building the same environment at once.
    ("uv.lock", ("uv", "sync", "--locked")),
    (".beads/config.yaml", ("bd", "bootstrap", "--yes")),
)


_OTHER_TRANSPORT = tuple(
    {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": f"url.{to}.insteadOf", "GIT_CONFIG_VALUE_0": frm}
    for to, frm in (("git@github.com:", "https://github.com/"), ("https://github.com/", "ssh://git@github.com/"))
)


def _fresh_clone_steps(ctx: Context, clone: Path) -> Finding | None:
    """Run each step the clone's files call for; the first that fails is the finding."""
    env = {**ctx.env, "MISE_IGNORED_CONFIG_PATHS": str(Path.home() / ".config" / "mise"), "BD_DISABLE_METRICS": "1"}
    for marker, argv in _FRESH_CLONE_STEPS:
        if not (clone / marker).is_file():
            continue
        done = ctx.run(*argv, cwd=clone, timeout=600, env=env)
        if argv[0] == "bd" and done is not None and done.returncode != 0:
            # The committed sync.remote may name the transport this machine lacks (https on an SSH-only box, ssh in CI).
            for rewrite in _OTHER_TRANSPORT:
                done = ctx.run(*argv, cwd=clone, timeout=600, env={**env, **rewrite})
                if done is not None and done.returncode == 0:
                    break
        if done is None or done.returncode != 0:
            why = "not installed or timed out" if done is None else _cause(done)
            return failing(
                f"fresh-clone step `{' '.join(argv)}` failed: {why}", "make the documented after-clone steps work on a new clone"
            )
    return None


@check("gate.clean-clone", "a fresh clone passes `just check` within its recorded budget", audit_only=True)
def clean_clone(ctx: Context) -> Finding:
    """Clone HEAD into a temp dir and run `just check` (a Makefile repo: `make check`) there, timed.

    When HEAD fails and the working tree holds uncommitted changes, the same run on a snapshot of the working tree tells
    "commit to verify" (mid-remediation, a2kay: shelf-83g) from a real failure; the row passes only on HEAD.
    """
    if ctx.git("rev-parse", "HEAD") is None:
        return not_checked("no commit to clone")
    word = "make" if gate_graph.has_makefile_only(ctx) else "just"
    budget = ctx.settings.get("clean-clone-seconds")
    with tempfile.TemporaryDirectory(prefix="blueprint-clone-") as tmp:
        clone = ctx.run("git", "clone", "--quiet", str(ctx.repo), tmp, timeout=300)
        if clone is None or clone.returncode != 0:
            return not_checked("could not clone the repository")
        judged = _gate_in(ctx, Path(tmp), word, budget)
    uncommitted = [
        line[3:] for line in (ctx.git("status", "--porcelain", "--untracked-files=all", "--ignore-submodules=all") or "").splitlines()
    ]
    if judged.verdict is not Verdict.FAILING or not uncommitted:
        return judged
    with tempfile.TemporaryDirectory(prefix="blueprint-snapshot-") as tmp:
        if not _snapshot(ctx, Path(tmp)):
            return judged
        if _gate_in(ctx, Path(tmp), word, budget).verdict is Verdict.FAILING:
            return judged
    named = ", ".join(uncommitted[:5]) + (f" and {len(uncommitted) - 5} more" if len(uncommitted) > 5 else "")
    return not_checked(
        f"{judged.evidence}; the working tree passes in a snapshot clone: commit to verify (uncommitted: {named})",
        "commit the changes on the owner's yes and re-run the audit; a file the gate needs but nobody commits belongs in the gate",
        FixedBy.OWNER,
    )


def _gate_in(ctx: Context, folder: Path, word: str, budget: object) -> Finding:
    """The after-clone steps, then the gate, in `folder`, timed against the recorded budget."""
    start = time.monotonic()
    if (failed := _fresh_clone_steps(ctx, folder)) is not None:
        return failed
    done = ctx.run(gate_graph.just_command(ctx) if word == "just" else word, "check", cwd=folder, timeout=3600)
    return _judge_clone(done, round(time.monotonic() - start), budget, word)


def _snapshot(ctx: Context, folder: Path) -> bool:
    """A one-commit repo of the working tree as it is: tracked and untracked files git does not ignore."""
    listed = ctx.git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if listed is None:
        return False
    for rel in filter(None, listed.split("\0")):
        source = ctx.path(rel)
        if source.is_file():
            target = folder / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    steps = (
        ("init", "-q"),
        ("add", "-A"),
        ("-c", "user.email=blueprint@invalid", "-c", "user.name=blueprint", "commit", "-qm", "snapshot"),
    )
    return all((done := ctx.run("git", *args, cwd=folder, timeout=300)) is not None and done.returncode == 0 for args in steps)


_CHECKER = re.compile(r"^(?:check|lint|validate|verify)[_-].+\.(?:py|sh)$")
_NOT_GUARDS = {"tests", "test"}


def _checker_scripts(ctx: Context) -> list[str]:
    """`check_*`, `lint_*`, `validate_*`, `verify_*` scripts (py, sh) under tools/ or scripts/, outside test folders and ignored paths."""
    found: list[str] = []
    for folder in ("tools", "scripts"):
        if not ctx.path(folder).is_dir():
            continue
        for path in walk(ctx.path(folder), "*"):
            rel = path.relative_to(ctx.repo).as_posix()
            if _CHECKER.match(path.name) and not _NOT_GUARDS & set(Path(rel).parts) and not is_skipped(rel, ctx.profile.ignore):
                found.append(rel)
    return sorted(found)


@check("gate.checkers-wired", "every check/lint script under tools/ or scripts/ is run by `just check`")
def checkers_wired(ctx: Context) -> Finding:
    """A checker nothing runs guards nothing: its name says check, and the repo's own docs may say run it before a commit."""
    gate = gate_graph.load(ctx)
    if gate is None:
        return not_applicable("no justfile: gate.one-command reports the missing gate")
    scripts = _checker_scripts(ctx)
    if not scripts:
        return not_applicable("no check_*/lint_* script under tools/ or scripts/")
    commands = _gate_commands(ctx, gate)
    unwired = [s for s in scripts if not re.search(rf"(?<![\w.-]){re.escape(Path(s).name)}", commands)]
    if unwired:
        return failing(
            f"`just check` never runs {', '.join(unwired)}",
            "run each from a recipe `just check` reaches (then gate.guards-have-red-tests wants a test per script), "
            "or delete it; a script kept on purpose is an override of gate.checkers-wired with a reason and an expiry or adr",
        )
    return passing(f"{len(scripts)} checker script(s), each run by the gate")


@check("gate.default-branch", "the default branch is `main`", audit_only=True)
def default_branch(ctx: Context) -> Finding:
    """origin/HEAD when there is a remote, else `main` if it exists, else the branch checked out."""
    if ctx.git("rev-parse", "--git-dir") is None:
        return not_checked("not a git repository")
    name = (ctx.git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD") or "").strip().removeprefix("refs/remotes/origin/")
    if not name and ctx.git("show-ref", "--verify", "--quiet", "refs/heads/main") is not None:
        name = "main"
    name = name or (ctx.git("symbolic-ref", "--quiet", "--short", "HEAD") or "").strip()
    if not name:
        return not_checked("detached HEAD, no origin/HEAD and no main branch: the default branch cannot be told")
    if name != "main":
        return failing(
            f"the default branch is {name}, the shelf and its tools assume main",
            f"git branch -m {name} main; with a remote: git push -u origin main, make main the host's default branch, delete {name} there",
        )
    return passing("the default branch is main")


@check("gate.git-remote", "an `origin` remote exists, so pushes, CI and bd's Dolt sync have somewhere to go", audit_only=True)
def git_remote(ctx: Context) -> Finding:
    """`git remote` lists origin; none at all is not set up yet, others without origin is a rename."""
    listed = ctx.git("remote")
    if listed is None:
        return not_checked("not a git repository")
    remotes = listed.split()
    if "origin" in remotes:
        return passing("origin: " + (ctx.git("remote", "get-url", "origin") or "").strip())
    if remotes:
        return failing(f"remotes {', '.join(remotes)}, none called origin", f"git remote rename {remotes[0]} origin")
    return not_set_up(
        "no git remote",
        "git remote add origin <url> and push; a repo kept local on purpose is an override of gate.git-remote with a reason and an adr",
    )


# LFS: declared in .gitattributes, the pattern set is only the setup; git's own verdict on each blob is the proof.
_LFS_ATTR = "filter=lfs"
_NO_LFS = "the repo declares no LFS pattern (.gitattributes has no filter=lfs)"
_POINTER_HEAD, _POINTER_MAX = "version https://git-lfs.github.com/spec/v1", 1024
_LFS_INSTALL = "git lfs install --skip-repo (prek owns the hooks); then re-add each raw file: git rm --cached <path> && git add <path>"


def _uses_lfs(ctx: Context) -> bool:
    return _LFS_ATTR in (ctx.read(".gitattributes") or "")


def _lfs_paths(ctx: Context, paths: list[str]) -> set[str]:
    """The paths an LFS pattern covers."""
    attrs = ctx.run("git", "check-attr", "filter", "--", *paths) if paths else None
    return {line.split(": ")[0] for line in (attrs.stdout if attrs else "").splitlines() if line.endswith(": filter: lfs")}


def _raw(ctx: Context, staged: dict[str, str], under: set[str]) -> list[str]:
    """LFS-pattern paths whose blob is not a pointer: a pointer is under 200 bytes and opens with its spec line."""
    raw: list[str] = []
    for path in sorted(under):
        size = (ctx.git("cat-file", "-s", staged[path]) or "0").strip()
        if int(size) > _POINTER_MAX or not (ctx.git("cat-file", "blob", staged[path]) or "").startswith(_POINTER_HEAD):
            raw.append(path)
    return raw


_GITHUB_REMOTE = re.compile(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?/?$")


def _head_runs(ctx: Context) -> tuple[str, str, dict[str, dict[str, str]]] | Finding:
    """(branch, head sha, the latest run per workflow on that sha), or the reason they cannot be read."""
    found = _GITHUB_REMOTE.search((ctx.git("remote", "get-url", "origin") or "").strip())
    if found is None:
        return not_checked("origin is not a GitHub repository; this row reads GitHub Actions")
    slug = found.group(1)
    branch = (ctx.git("symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD") or "origin/main").strip().removeprefix("origin/")
    fields = "workflowName,headSha,status,conclusion,event"
    done = ctx.run("gh", "run", "list", "--repo", slug, "--branch", branch, "--limit", "30", "--json", fields, timeout=60)
    if done is None or done.returncode != 0:
        why = (done.stderr.strip().splitlines() or ["no output"])[-1] if done else "gh is not installed or timed out"
        return not_checked(f"gh could not list the runs ({why}): `gh auth login` once on this machine")
    # Dependabot's own update runs (event `dynamic`) are not the repo's CI.
    runs = [r for r in json.loads(done.stdout or "[]") if r.get("event") != "dynamic"]
    if not runs:
        return not_checked(f"no CI runs on {branch} yet")
    # The pushed tip, as this clone last fetched it: right after a push the newest run is the previous commit's.
    head = (ctx.git("rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}") or "").strip() or runs[0]["headSha"]
    if not any(r["headSha"] == head for r in runs):
        return not_checked(f"no CI run on {head[:7]} yet; `gh run watch` once it starts, and re-run")
    latest: dict[str, dict[str, str]] = {}
    for r in runs:
        if r["headSha"] == head:
            latest.setdefault(r["workflowName"], r)
    return branch, head, latest


@check("gate.ci-green", "CI is green on the default branch's latest commit", audit_only=True)
def ci_green(ctx: Context) -> Finding:
    """A repo blueprint passes can still be red where it ships: the shelf's own CI failed every push for hours unread.

    Read through `gh` (logged in once per machine).
    """
    if not _workflows(ctx):
        return not_applicable("no GitHub Actions workflows")
    read = _head_runs(ctx)
    if not isinstance(read, tuple):
        return read
    branch, head, latest = read
    going = [name for name, r in latest.items() if r["status"] != "completed"]
    if going:
        return not_checked(f"{', '.join(going)} still running on {head[:7]}; `gh run watch` and re-run")
    red = [f"{name} ({r['conclusion']})" for name, r in latest.items() if r["conclusion"] != "success"]
    if red:
        fix = "`gh run view --log-failed` on the red run; fix it before anything else ships"
        return failing(f"{branch} {head[:7]}: {', '.join(red)}", fix)
    return passing(f"{branch} {head[:7]}: {', '.join(latest)} green")


@check("gate.lfs-binaries", "in a repo that uses LFS, every binary blob in git is an LFS pointer")
def lfs_binaries(ctx: Context) -> Finding:
    """Two misses: a binary no pattern covers (`git ls-files --eol` says `i/-text`), and a covered file stored raw.

    A covered file is `-text`, so `--eol` cannot judge it: its blob is read instead.
    """
    if not _uses_lfs(ctx):
        return not_applicable(_NO_LFS)
    listed, staged_out = ctx.git("ls-files", "--eol", "-z"), ctx.git("ls-files", "-s", "-z")
    if listed is None or staged_out is None:
        return not_checked("not a git repository")
    staged = {e.split("\t", 1)[1]: e.split()[1] for e in staged_out.split("\0") if "\t" in e}
    binary = [e.split("\t", 1)[1] for e in listed.split("\0") if e.startswith("i/-text") and "\t" in e]
    under = _lfs_paths(ctx, sorted(staged))
    unlisted = [p for p in binary if p not in under]
    raw = _raw(ctx, staged, under)
    if not unlisted and not raw:
        return passing(f"{len(under)} files under LFS patterns, all pointers; no other binary in git")
    problems = [f"committed raw under an LFS pattern (that clone had no LFS filter): {', '.join(raw)}"] if raw else []
    problems += [f"binary with no LFS pattern: {', '.join(unlisted)}"] if unlisted else []
    return failing(
        "; ".join(problems),
        "add a `<pattern> filter=lfs diff=lfs merge=lfs -text` line for each unlisted type; " + _LFS_INSTALL,
    )


@check("gate.lfs-installed", "in a repo that uses LFS, this clone has git-lfs and its filter installed", audit_only=True)
def lfs_installed(ctx: Context) -> Finding:
    """Without the filter, git stores the bytes and a fresh clone checks out pointers: the clone-local half of LFS."""
    if not _uses_lfs(ctx):
        return not_applicable(_NO_LFS)
    if ctx.run("git", "lfs", "version") is None or not ctx.has("git-lfs"):
        return not_set_up("git-lfs is not installed", "pin git-lfs in mise.toml and run `just tools`; then " + _LFS_INSTALL)
    if not (ctx.git("config", "--get", "filter.lfs.process") or ctx.git("config", "--get", "filter.lfs.clean")):
        return failing("the LFS filter is not configured: git lfs install was never run for this user", _LFS_INSTALL, FixedBy.AUTO)
    return passing("git-lfs installed and its filter configured")


# The files that make a gate. A remote branch holding one of them may already carry the gate main lacks.
_GATE_FILES = ("justfile", "Makefile", ".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml", ".github/workflows/*")
# The rows that tell an agent to build or repair a gate: where an unmerged branch holding one changes who decides.
BRANCH_AWARE = frozenset(
    {
        "gate.one-command",
        "gate.runner",
        "gate.ci",
        "gate.ci-no-manifest-edit",
        "gate.hooks-recipe",
        "gate.runs-blueprint",
        "gate.clean-clone",
    }
)


def unmerged_gate_branches(ctx: Context) -> dict[str, list[str]]:
    """Remote-tracking branches ahead of the default branch -> the gate files they change there.

    Local refs only (no fetch), and nothing is run against a branch: the owner judges it.
    """
    head = (ctx.git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD") or "").strip().removeprefix("refs/remotes/")
    base = head or "origin/main"
    if ctx.git("rev-parse", "--verify", "--quiet", base) is None:
        return {}
    refs = (ctx.git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin") or "").split()
    found: dict[str, list[str]] = {}
    for ref in refs:
        if ref in {base, "origin", "origin/HEAD"}:
            continue
        changed = (ctx.git("diff", "--name-only", f"{base}...{ref}") or "").splitlines()
        if files := [f for f in changed if any(fnmatch(f, pattern) for pattern in _GATE_FILES)]:
            found[ref] = files
    return found


def branch_note(evidence: str, remediation: str, branches: dict[str, list[str]]) -> tuple[str, str]:
    """A not-passing gate row's evidence and remediation, naming the branches that hold gate files and handing the decision to the owner."""
    held = "; ".join(f"{ref} changes {', '.join(files)}" for ref, files in branches.items())
    return (
        f"{evidence}; unmerged remote branch(es) hold gate files: {held}",
        f"do not build a parallel gate: the owner decides whether to merge that branch or remediate on main "
        f"(the branch is not judged here). Without the branch: {remediation}".rstrip(": "),
    )
