"""Gate: one command decides Done, and the hooks and CI run that same command."""

from __future__ import annotations

import re
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from blueprint.model import Context, Finding, FixedBy, check, failing, not_applicable, not_checked, not_set_up, passing, walk

if TYPE_CHECKING:
    import subprocess

_TARGET = re.compile(r"^([A-Za-z][A-Za-z0-9_.-]*)\s*:(?!=)", re.MULTILINE)
_GATE_RUN = re.compile(r"\bmake\s+(?:-\S+\s+)*check(?:-all)?\b")
_USES = re.compile(r"^\s*-?\s*uses:\s*['\"]?([^\s'\"#]+)", re.MULTILINE)
_SHA = re.compile(r"@[0-9a-f]{40}$")
# A script a recipe runs: `python3 x.py`, `uv run python x.py`, or `g=x.py` handed to python later.
_SCRIPT = re.compile(r"(?:python3?\s+|uv run python\s+|\b[A-Za-z_]\w*=)((?:[\w.-]+/)*[\w.-]+\.py)\b")
_ONBOARD = (
    "the shelf onboarding writes the gate: `make bootstrap`, or python3 <shelf>/.agents/skills/onboard-consumer/scripts/onboard.py --repo ."
)


def _targets(makefile: str) -> set[str]:
    return set(_TARGET.findall(makefile))


def _rules(makefile: str) -> dict[str, tuple[list[str], str]]:
    """target -> (prerequisites, recipe text)."""
    rules: dict[str, tuple[list[str], str]] = {}
    matches = list(_TARGET.finditer(makefile))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(makefile)
        header, _, body = makefile[m.start() : end].partition("\n")
        recipe = "\n".join(line for line in body.splitlines() if line.startswith("\t"))
        rules[m.group(1)] = (header.split(":", 1)[1].split(), recipe)
    return rules


def _reachable(makefile: str, start: str = "check") -> list[str]:
    """Recipes of every target `start` reaches: through prerequisites, or a recipe naming a target."""
    rules = _rules(makefile)
    seen, queue = {start}, [start]
    while queue:
        prereqs, recipe = rules.get(queue.pop(), ([], ""))
        words = set(prereqs) | set(re.findall(r"[\w.-]+", recipe))
        for nxt in sorted(words & rules.keys() - seen):
            seen.add(nxt)
            queue.append(nxt)
    return [rules[t][1] for t in sorted(seen) if t in rules]


@check("gate.one-command", "`make check` exists and every target it names resolves")
def one_command(ctx: Context) -> Finding:
    """The Makefile has a `check` target and `make -n check` resolves."""
    python = any(s.startswith("python") for s in ctx.profile.stacks)
    fixer = (_ONBOARD, FixedBy.AUTO) if python else ("add a Makefile whose `check` target runs every linter and the tests", FixedBy.AGENT)
    makefile = ctx.read("Makefile")
    if makefile is None:
        return not_set_up("no Makefile", *fixer)
    if "check" not in _targets(makefile):
        return not_set_up("the Makefile has no `check` target", *fixer)
    dry = ctx.run("make", "-n", "check", timeout=60)
    if dry is None:
        return not_checked("`make` is not installed or timed out")
    if dry.returncode != 0:
        complaint = (dry.stderr.strip() or dry.stdout.strip()).splitlines()[-1:] or ["no output"]
        return failing(f"`make -n check` fails: {complaint[0]}", "add or fix the target make names")
    return passing("`make -n check` resolves")


def _workflows(ctx: Context) -> list[Path]:
    wf = ctx.path(".github/workflows")
    return sorted([*wf.glob("*.yml"), *wf.glob("*.yaml")]) if wf.is_dir() else []


@check("gate.ci", "CI runs the gate command; every action is pinned to a commit SHA; permissions are declared")
def ci(ctx: Context) -> Finding:
    """GitHub Actions: some job runs `make check`/`check-all`; `uses:` pinned by SHA; top-level permissions."""
    files = _workflows(ctx)
    if not files:
        if ctx.read(".gitlab-ci.yml") is not None:
            return not_checked("GitLab CI is not checked yet; blueprint covers GitHub Actions")
        return not_set_up(
            "no .github/workflows/*.yml",
            "add a workflow that runs `make check-all` (or `make check`) on push and pull request; "
            "a repo that should have no CI records an override with its reason",
        )
    problems: list[str] = []
    if not any(_GATE_RUN.search(f.read_text()) for f in files):
        problems.append("no workflow runs `make check`")
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


@check("gate.hooks-recipe", "prek owns the git hooks through .pre-commit-config.yaml, and bd's hooks run from it", version=2)
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
    if problems:
        return failing("; ".join(problems), f"apply the recipe ({_RECIPE}), keeping the repo's own checks after bd's entries")
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


def _gate_scripts(ctx: Context, makefile: str) -> list[str]:
    found = (m for recipe in _reachable(makefile) for m in _SCRIPT.findall(recipe))
    return list(dict.fromkeys(m for m in found if ctx.path(m).is_file()))


@check("gate.runs-blueprint", "`make check` runs blueprint's per-commit checkpoints (`make blueprint`)")
def runs_blueprint(ctx: Context) -> Finding:
    """Gaps come back between audits unless the repo's own gate re-checks them on every commit."""
    makefile = ctx.read("Makefile")
    if makefile is None:
        return not_applicable("no Makefile: gate.one-command reports the missing gate")
    if "blueprint check" in reachable_recipes(makefile):
        return passing("`make check` reaches `blueprint check --gate`")
    return not_set_up(
        "`make check` never runs blueprint",
        "copy the shelf's `blueprint` target into the Makefile and add it to `check` (`make bootstrap` does both)",
        FixedBy.AUTO,
    )


@check("gate.guards-have-red-tests", "every repo-local script `make check` runs has a test that names it")
def guards_have_red_tests(ctx: Context) -> Finding:
    """Each repo `*.py` that `make check` reaches is named by some test file (a guard never seen red is a hypothesis)."""
    makefile = ctx.read("Makefile")
    if makefile is None:
        return not_applicable("no Makefile, so no guard scripts")
    scripts = _gate_scripts(ctx, makefile)
    if not scripts:
        return not_applicable("`make check` runs no repo-local Python script")
    tests = [p.read_text(errors="replace") for p in walk(ctx.repo, "test_*.py")]
    untested = [s for s in scripts if not any(Path(s).stem in t or Path(s).stem.replace("-", "_") in t for t in tests)]
    if untested:
        return failing(
            f"no test names {', '.join(untested)}",
            "add a test per script that plants the violation it guards against and asserts it fails",
        )
    return passing(f"{len(scripts)} script(s), each named by a test")


def _judge_clone(done: subprocess.CompletedProcess[str] | None, took: int, budget: object) -> Finding:
    if done is None:
        return failing("`make check` in a fresh clone did not finish within an hour", "find the step that hangs")
    if done.returncode != 0:
        tail = (done.stderr.strip() or done.stdout.strip()).splitlines()[-1:] or ["no output"]
        return failing(f"`make check` fails in a fresh clone ({took}s): {tail[0]}", "make the gate pass from a clean checkout")
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


@check("gate.clean-clone", "a fresh clone passes `make check` within its recorded budget", audit_only=True)
def clean_clone(ctx: Context) -> Finding:
    """Clone HEAD into a temp dir and run `make check` there, timed."""
    if ctx.git("rev-parse", "HEAD") is None:
        return not_checked("no commit to clone")
    with tempfile.TemporaryDirectory(prefix="blueprint-clone-") as tmp:
        clone = ctx.run("git", "clone", "--quiet", str(ctx.repo), tmp, timeout=300)
        if clone is None or clone.returncode != 0:
            return not_checked("could not clone the repository")
        start = time.monotonic()
        done = ctx.run("make", "check", cwd=Path(tmp), timeout=3600)
        took = round(time.monotonic() - start)
    return _judge_clone(done, took, ctx.settings.get("clean-clone-seconds"))


def reachable_recipes(makefile: str) -> str:
    """The recipe text of every target `make check` or `make check-all` reaches, joined.

    `check-all` counts: a repo may narrow `check` to what a change touches and keep the whole
    run (coverage floor included) in `check-all`, which CI runs.
    """
    return "\n".join(dict.fromkeys(_reachable(makefile) + _reachable(makefile, "check-all")))
