"""Is a step's declared input set sound? Compare what a step read with the globs it declares (`any-gate steps --reads`).

Why: a step whose globs omit a file it reads is skipped when only that file changes, so a break reaches main (`any_gate.inputs`). That
is the worse error; a step declared wider than it reads is only slow, and is reported as information, never a failure.

How: the audit hook of `any_gate.opens` (a `sitecustomize` first on `PYTHONPATH` of every step) also writes, per Python process, the
tracked files under the repo it opened for reading, the folders it listed, and the programs it started. A static scan of the recipe
(`just --dump --dump-format json`, dependencies included) names every command that is not plain Python. A step is judged:

- `UNDER`: it read a tracked file (or listed a folder) no declared glob covers. Proven: those reads happened. Exit 1.
- `SOUND`: every read seen is declared, and nothing opaque ran: the verdict holds for what Python saw, no more.
- `CANNOT`: nothing proven wrong, but the step ran something the hook cannot see (any non-Python program: ruff, git, uv, shells;
  `python -I`, `-E`, `-S` start no hook), so the reads seen are a floor. Never a green.
- `WHOLE` / `ALWAYS`: it declares `*`, or declares nothing: it runs on every change.

Never seen, so never judged: reads by non-Python programs; Python run with `-I`/`-E`/`-S`; a process killed before it exits (its reads are
written at exit); `stat` and `exists` checks (no audit event, so a step that only tests a file's presence); reads of untracked files; a
read that depends on a file's absence. A Python reading through an opaque child is judged only for its own reads.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
from dataclasses import dataclass
from pathlib import PurePath
from typing import TYPE_CHECKING

from stream_proc import capture

from any_gate import inputs
from any_gate import opens as step_opens

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

NOT_SEEN = "reads by non-python programs, python -I/-E/-S, files a killed process had open, stat/exists checks, untracked files"
_HARMLESS = {"echo", "exit", "set", "true", "false", ":"}
_SHOWN = 5
_GIT_TIMEOUT = 60.0
_ASSIGN = re.compile(r"[A-Za-z_]\w*=")


@dataclass(frozen=True)
class Trace:
    """What a step's Python processes saw: repo-relative files read, folders listed, programs started that the hook cannot follow."""

    reads: frozenset[str]
    dirs: frozenset[str]
    opaque: tuple[str, ...]
    pythons: int


@dataclass(frozen=True)
class Verdict:
    """One step's soundness: `status` (UNDER, SOUND, CANNOT, WHOLE, ALWAYS), the reads no glob covers, the globs read nothing."""

    step: str
    status: str
    under: tuple[str, ...] = ()
    wide: tuple[str, ...] = ()
    why: str = ""
    seen: int = 0


def blind_flag(args: Sequence[str]) -> str:
    """The first of `-I`, `-E`, `-S` among a python's own options (those before the script, `-m` or `-c`), else ""."""
    for arg in args:
        if not arg.startswith("-") or arg == "-":
            return ""
        if arg.startswith("--"):
            continue
        for letter in arg[1:]:
            if letter in "IES":
                return f"-{letter}"
            if letter in "cm":
                return ""
    return ""


def _program(exe: str, args: Sequence[str]) -> str:
    """ "" for a Python the hook follows, else the name to report."""
    name = PurePath(exe).name or "?"
    if not name.startswith("python"):
        return name
    flag = blind_flag(args)
    return f"python {flag}" if flag else ""


def load(folder: Path, step: str, repo: Path) -> Trace:
    """The step's trace from the files the hook wrote in `folder`, paths made relative to `repo` (a symlinked `repo` is resolved)."""
    roots = {str(repo), str(repo.resolve())}
    found: dict[str, set[str]] = {"r": set(), "d": set(), "s": set()}
    log = folder / f"{step}.reads"
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines() if log.is_file() else []:  # lossy-ok: display
        kind, _, text = line.partition("\t")
        if kind in found:
            found[kind].add(text)

    def rel(path: str) -> str | None:
        for root in roots:
            if path == root:
                return "."
            if path.startswith(root + "/"):
                return path[len(root) + 1 :]
        return None

    opaque: list[str] = []
    for spawn in sorted(found["s"]):
        exe, _, argv = spawn.partition("\t")
        name = _program(exe, argv.split())
        if name and name not in opaque:
            opaque.append(name)
    reads = {r for p in found["r"] if (r := rel(p))}
    dirs = {r for p in found["d"] if (r := rel(p))}
    return Trace(frozenset(reads), frozenset(dirs), tuple(opaque), step_opens.collect(folder, [step])[0].pythons)


def _words(line: str) -> list[list[str]]:
    """The commands of one recipe line: split at `&&`, `||`, `;`, `|`, redirections (and their targets) dropped."""
    lex = shlex.shlex(line, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    try:
        tokens = list(lex)
    except ValueError:
        return [["?"]]
    commands: list[list[str]] = [[]]
    skip = False
    for token in tokens:
        if skip:
            skip = False
        elif token and set(token) <= set("<>&") and ("<" in token or ">" in token):
            skip = True  # a redirection: its target is not a command
        elif token and set(token) <= set("&|;()"):
            commands.append([])
        else:
            commands[-1].append(token)
    return [c for c in commands if c]


def _line_text(fragments: object) -> str:
    if isinstance(fragments, list):
        return "".join(f if isinstance(f, str) else "X" for f in fragments)
    return str(fragments)


def _opaque_in(name: str, dump: Mapping[str, object], seen: set[str]) -> list[str]:
    found: list[str] = []
    recipe = dump.get(name)
    if name in seen:
        return found
    seen.add(name)
    if not isinstance(recipe, dict):
        return ["recipe unreadable"]
    body = [_line_text(line) for line in recipe.get("body", [])]
    if recipe.get("shebang") and body:
        words = shlex.split(body[0][2:].strip()) if body[0].startswith("#!") else ["?"]
        words = [w for w in words if w != "-S"]
        exe = words[1] if PurePath(words[0]).name == "env" and len(words) > 1 else words[0]
        found.append(_program(exe, words[1:]) or "")
        found = [f for f in found if f]
    else:
        for line in body:
            for command in _words(line.lstrip("@-+")):
                rest = list(command)
                while rest and _ASSIGN.match(rest[0]):
                    rest.pop(0)
                if not rest or rest[0] in _HARMLESS:
                    continue
                found.append(_program(rest[0], rest[1:]) or "")
    for dep in recipe.get("dependencies", []):
        if isinstance(dep, dict) and isinstance(dep.get("recipe"), str):
            found += _opaque_in(dep["recipe"], dump, seen)
    return [f for f in found if f]


def opaque_commands(dump: Mapping[str, object], step: str) -> tuple[str, ...]:
    """The commands of recipe `step` (and its dependencies) a Python audit hook cannot follow, from `just --dump` JSON; in order, once."""
    names: list[str] = []
    for name in _opaque_in(step, dump, set()):
        if name not in names:
            names.append(name)
    return tuple(names)


def _covered(path: str, globs: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in (*globs, *inputs.DEFINITION))


def judge(step: str, globs: Sequence[str], tracked: frozenset[str], trace: Trace, static: Sequence[str]) -> Verdict:
    """The verdict on one step: its `globs`, the repo's `tracked` files, what its processes `trace`d, what the recipe scan found opaque."""
    if "*" in globs:
        return Verdict(step, "WHOLE", why="declares *: every change runs it", seen=len(trace.reads))
    under = sorted(p for p in trace.reads if p in tracked and not _covered(p, globs))
    for folder in sorted(trace.dirs):
        inside = [t for t in tracked if folder == "." or t.startswith(folder + "/")]
        if inside and not any(_covered(t, globs) for t in inside):
            under.append(f"{folder}/ (listed)")
    opaque = list(dict.fromkeys([*trace.opaque, *static]))
    if trace.pythons == 0:
        opaque.append("no python process reported")
    seen = len({p for p in trace.reads if p in tracked})
    if under:
        return Verdict(step, "UNDER", tuple(under), why="reads files no declared glob covers", seen=seen)
    if opaque:
        return Verdict(step, "CANNOT", why=f"opaque: {', '.join(opaque)}", seen=seen)
    listed = {t for f in trace.dirs for t in tracked if f == "." or t.startswith(f + "/")}
    wide = tuple(g for g in globs if not any(fnmatch.fnmatch(p, g) for p in (*trace.reads, *listed)))
    return Verdict(step, "SOUND", wide=wide, why="python reads only", seen=seen)


def _tracked(repo: Path) -> frozenset[str]:
    done = capture(["git", "ls-files", "-z"], cwd=repo, timeout=_GIT_TIMEOUT)
    return frozenset(p for p in done.text.split("\0") if p)


def _recipes(repo: Path, runner: str) -> dict[str, object] | None:
    """The runner's recipes (`just --dump --dump-format json`); None when it is not just or would not say."""
    if PurePath(runner).name != "just":
        return None
    done = capture([runner, "--dump", "--dump-format", "json"], cwd=repo, timeout=_GIT_TIMEOUT)
    if done.exit != 0:
        return None
    recipes = json.loads(done.out).get("recipes")
    return recipes if isinstance(recipes, dict) else None


def root_env(repo: Path) -> str:
    """The `GATE_READS_ROOT` value: the repo as given and resolved (the hook sees whichever the step's cwd spells)."""
    return os.pathsep.join(dict.fromkeys([str(repo), str(repo.resolve())]))


def _list(items: Sequence[str]) -> str:
    """The first few items; past that, the folders they sit in (`126 under packages/any-gate/src`), biggest first."""
    if len(items) <= _SHOWN:
        return ", ".join(items)
    groups: dict[str, int] = {}
    for item in items:
        key = "/".join(item.split("/")[:3]) if item.count("/") > 2 else item
        groups[key] = groups.get(key, 0) + 1
    top = sorted(groups.items(), key=lambda kv: (-kv[1], kv[0]))[:_SHOWN]
    shown = ", ".join(f"{n} under {k}" if n > 1 else k for k, n in top)
    return f"{len(items)} files: {shown}" + (", …" if len(groups) > _SHOWN else "")


def lines(verdicts: Sequence[Verdict]) -> list[str]:
    """The report: one line per step, the wide globs as information, then what the check cannot see and the tally."""
    out: list[str] = []
    for v in verdicts:
        if v.status == "UNDER":
            out.append(f"gate soundness: UNDER {v.step} reads {_list(v.under)} outside its inputs: a change there skips it")
        elif v.status == "CANNOT":
            out.append(f"gate soundness: CANNOT {v.step}: {v.why}; {v.seen} declared reads seen, the rest is not known")
        elif v.status == "SOUND":
            out.append(f"gate soundness: SOUND {v.step}: {v.seen} tracked files read, all declared ({v.why})")
        else:
            out.append(f"gate soundness: {v.status} {v.step}: {v.why}")
        if v.wide:
            out.append(f"gate soundness: wide {v.step}: {_list(v.wide)} matched nothing it read (information only)")
    count = {s: sum(1 for v in verdicts if v.status == s) for s in ("UNDER", "CANNOT", "SOUND")}
    tally = " ".join(f"{n} {s}" for s, n in count.items())
    out.append(f"gate soundness: {tally} | not seen: {NOT_SEEN}")
    return out


def audit(repo: Path, names: Sequence[str], folder: Path, runner: str) -> tuple[list[str], bool]:
    """Judge each of `names` (the steps that ran under the hook): the report lines, and whether any step is UNDER."""
    declared = inputs.declared(repo)
    tracked = _tracked(repo)
    dump = _recipes(repo, runner) or {}
    verdicts = []
    for name in names:
        if name not in declared:
            verdicts.append(Verdict(name, "ALWAYS", why="declares nothing: runs on every change"))
            continue
        verdicts.append(judge(name, declared[name], tracked, load(folder, name, repo), opaque_commands(dump, name)))
    return lines(verdicts), any(v.status == "UNDER" for v in verdicts)
