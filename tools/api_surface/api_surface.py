#!/usr/bin/env python3
"""A package's public API between two git tags, derived from the source ASTs; and what a package costs to learn.

`diff <package> <tagA> <tagB>` lists ADDED / REMOVED / CHANGED public names, one line each, BREAKING where a caller must adapt: a removal,
a removed or renamed parameter, a new required one, a parameter that turned keyword-only or required, a reordered positional, a changed
return or field annotation text, a new typed exception raised, a removed or newly required dataclass field. Breaking is free here and there
are no migration docs (constitution III), so this list is what an upgrading agent reads instead.

The public surface of a version is the names the package's `__init__` lists in `__all__` (else its public module-level names), each followed
to its definition through `from x import y`. Recorded per name: function and method signatures (parameter kind, default present or not,
annotation text, return annotation text, async/property/staticmethod/classmethod), the exceptions a body raises directly (`raise X` of a
class defined in the package, not inside a nested def), dataclass/NamedTuple/TypedDict fields, class bases. Not seen: inherited methods,
other decorators, default values, behaviour. Sources come from `git archive <tag>` read in memory: nothing is checked out and no package
code is imported. Stdlib only.

`learning-cost [package ...]` prints a table, largest first: tokens to read the README plus every public signature plus each docstring's
first line. Tokens are `ceil(words * 1.3)`, words split on whitespace. A metric to read, never a gate.
"""

from __future__ import annotations

import argparse
import ast
import io
import subprocess
import sys
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

GIT_TIMEOUT = 120.0  # seconds one git call may take
TOKENS_PER_WORD = 13  # tenths: 1.3 tokens a word
DEFS = (ast.FunctionDef, ast.AsyncFunctionDef)
RECORDS = ("NamedTuple", "TypedDict")


class GitError(RuntimeError):
    """A git call failed; the message is git's own."""


@dataclass(frozen=True)
class Param:
    name: str
    kind: str  # pos, pos-or-kw, var-pos, kw, var-kw
    default: bool
    ann: str


@dataclass(frozen=True)
class Entry:
    kind: str  # function, method, class, field, const, import, module, unresolved
    params: tuple[Param, ...] = ()
    returns: str = ""
    raises: tuple[str, ...] = ()
    text: str = ""  # modifiers (functions), bases (classes), annotation (fields), value or source (the rest)
    default: bool = False  # a field has a default
    doc: str = field(default="", compare=False)


def git(repo: Path, *args: str) -> bytes:
    try:
        done = subprocess.run(["git", *args], cwd=repo, capture_output=True, check=False, timeout=GIT_TIMEOUT)
    except subprocess.TimeoutExpired as err:
        message = f"git {args[0]} timed out"
        raise GitError(message) from err
    if done.returncode:
        # lossy-ok: display: git's error text, shown to the reader, never stored
        raise GitError(done.stderr.decode(errors="replace").strip() or f"git {args[0]} failed")
    return done.stdout


def sources(repo: Path, rev: str, package: str) -> dict[str, str]:
    """{path under src without `.py`: source} of `packages/<package>/src` at `rev`."""
    prefix = f"packages/{package}/src/"
    data = git(repo, "archive", "--format=tar", rev, prefix)
    out: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for member in tar:
            if member.isfile() and member.name.endswith(".py") and (handle := tar.extractfile(member)):
                out[member.name.removeprefix(prefix).removesuffix(".py")] = handle.read().decode("utf-8")
    return out


def first_line(node: ast.AST) -> str:
    doc = ast.get_docstring(node) if isinstance(node, (ast.Module, ast.ClassDef, *DEFS)) else None
    return doc.splitlines()[0].strip() if doc else ""


def decorator_names(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: set[str] = set()
    for deco in node.decorator_list:
        target = deco.func if isinstance(deco, ast.Call) else deco
        names.add(target.attr if isinstance(target, ast.Attribute) else ast.unparse(target))
    return names


def parameters(args: ast.arguments, *, drop_first: bool) -> tuple[Param, ...]:
    positional = [*args.posonlyargs, *args.args]
    firsts = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    rows = [
        (a, "pos" if i < len(args.posonlyargs) else "pos-or-kw", d is not None)
        for i, (a, d) in enumerate(zip(positional, firsts, strict=True))
    ]
    if drop_first:
        rows = rows[1:]
    if args.vararg:
        rows.append((args.vararg, "var-pos", False))
    rows += [(a, "kw", d is not None) for a, d in zip(args.kwonlyargs, args.kw_defaults, strict=True)]
    if args.kwarg:
        rows.append((args.kwarg, "var-kw", False))
    return tuple(Param(a.arg, kind, has, ast.unparse(a.annotation) if a.annotation else "") for a, kind, has in rows)


def raised(node: ast.FunctionDef | ast.AsyncFunctionDef, classes: set[str]) -> tuple[str, ...]:
    """Package classes raised directly in the body (nested defs and classes are their own)."""
    found: set[str] = set()
    stack: list[ast.AST] = list(node.body)
    while stack:
        item = stack.pop()
        if isinstance(item, (*DEFS, ast.ClassDef)):
            continue
        if isinstance(item, ast.Raise) and item.exc is not None:
            exc = item.exc.func if isinstance(item.exc, ast.Call) else item.exc
            name = exc.id if isinstance(exc, ast.Name) else exc.attr if isinstance(exc, ast.Attribute) else ""
            if name in classes:
                found.add(name)
        stack.extend(ast.iter_child_nodes(item))
    return tuple(sorted(found))


def function_entry(node: ast.FunctionDef | ast.AsyncFunctionDef, classes: set[str], *, method: bool) -> Entry:
    decos = decorator_names(node)
    mods = ["async"] if isinstance(node, ast.AsyncFunctionDef) else []
    mods += sorted(decos & {"property", "staticmethod", "classmethod"})
    params = parameters(node.args, drop_first=method and "staticmethod" not in decos)
    returns = ast.unparse(node.returns) if node.returns else ""
    return Entry("method" if method else "function", params, returns, raised(node, classes), " ".join(mods), doc=first_line(node))


def field_default(value: ast.expr | None) -> bool:
    if isinstance(value, ast.Call) and ast.unparse(value.func).split(".")[-1] == "field":
        return any(k.arg in ("default", "default_factory") for k in value.keywords)
    return value is not None


def class_entries(node: ast.ClassDef, classes: set[str]) -> dict[str, Entry]:
    bases = [ast.unparse(b) for b in node.bases]
    out = {"": Entry("class", text=", ".join(bases), doc=first_line(node))}
    record = "dataclass" in decorator_names(node) or any(b.split(".")[-1] in RECORDS for b in bases)
    for item in node.body:
        if record and isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and not item.target.id.startswith("_"):
            ann = ast.unparse(item.annotation)
            if not ann.startswith("ClassVar"):
                out[item.target.id] = Entry("field", text=ann, default=field_default(item.value))
        elif isinstance(item, DEFS) and (not item.name.startswith("_") or item.name == "__init__"):
            skip = decorator_names(item) & {"overload", "setter", "deleter"}
            if not skip:
                out[item.name] = function_entry(item, classes, method=True)
    return out


class Package:
    """The parsed modules of one version, and name resolution through its imports."""

    def __init__(self, texts: dict[str, str]) -> None:
        dotted = {path: ".".join(p for p in path.split("/") if p != "__init__") for path in texts}
        self.trees = {dotted[path]: ast.parse(text) for path, text in texts.items()}
        self.inits = {dotted[path] for path in texts if path.endswith("__init__")}
        self.classes = {n.name for tree in self.trees.values() for n in tree.body if isinstance(n, ast.ClassDef)}
        self.root = min(self.trees, key=lambda name: (name.count("."), name), default="")

    def target(self, module: str, node: ast.ImportFrom) -> str:
        if node.level == 0:
            return node.module or ""
        base = module.split(".") if module in self.inits else module.split(".")[:-1]
        base = base[: len(base) - (node.level - 1)]
        return ".".join([*base, *([node.module] if node.module else [])])

    def resolve(self, module: str, name: str, depth: int = 0) -> dict[str, Entry]:
        """Entries `name` stands for in `module`, keyed by member path ('' is the name itself); the last binding wins."""
        found: dict[str, Entry] = {"": Entry("unresolved")}
        for node in self.trees[module].body:
            if isinstance(node, DEFS) and node.name == name and not decorator_names(node) & {"overload"}:
                found = {"": function_entry(node, self.classes, method=False)}
            elif isinstance(node, ast.ClassDef) and node.name == name:
                found = class_entries(node, self.classes)
            elif isinstance(node, ast.ImportFrom):
                found = self.imported(module, node, name, depth) or found
            elif isinstance(node, ast.Import):
                hit = [a.name for a in node.names if (a.asname or a.name.split(".")[0]) == name]
                found = {"": Entry("import", text=hit[0])} if hit else found
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                found = self.assigned(node, name) or found
        return found

    def imported(self, module: str, node: ast.ImportFrom, name: str, depth: int) -> dict[str, Entry]:
        for alias in node.names:
            if (alias.asname or alias.name) != name:
                continue
            source = self.target(module, node)
            if f"{source}.{alias.name}" in self.trees:
                return {"": Entry("module", text=f"{source}.{alias.name}")}
            if source in self.trees and depth < 10:
                return self.resolve(source, alias.name, depth + 1)
            return {"": Entry("import", text=f"{source}.{alias.name}")}
        return {}

    @staticmethod
    def assigned(node: ast.Assign | ast.AnnAssign, name: str) -> dict[str, Entry]:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(t, ast.Name) and t.id == name for t in targets) or node.value is None:
            return {}
        text = ast.unparse(node.value)
        return {"": Entry("const", text=text if len(text) <= 80 else text[:77] + "...")}

    def public_names(self) -> list[str]:
        if not self.root:
            return []
        body = self.trees[self.root].body
        for node in body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, (ast.List, ast.Tuple)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
                    return [e.value for e in node.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        names: list[str] = []
        for node in body:
            if isinstance(node, (*DEFS, ast.ClassDef)):
                names.append(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names += [t.id for t in targets if isinstance(t, ast.Name)]
        return [n for n in dict.fromkeys(names) if not n.startswith("_")]

    def surface(self) -> dict[str, Entry]:
        out: dict[str, Entry] = {}
        for name in self.public_names():
            for member, entry in self.resolve(self.root, name).items():
                out[f"{name}.{member}" if member else name] = entry
        return out


def surface(repo: Path, rev: str, package: str) -> dict[str, Entry]:
    return Package(sources(repo, rev, package)).surface()


def params_text(params: tuple[Param, ...]) -> str:
    parts: list[str] = []
    for i, p in enumerate(params):
        if p.kind == "kw" and not any(q.kind == "var-pos" for q in params) and not any(q.kind == "kw" for q in params[:i]):
            parts.append("*")
        prefix = {"var-pos": "*", "var-kw": "**"}.get(p.kind, "")
        parts.append(f"{prefix}{p.name}" + (f": {p.ann}" if p.ann else "") + ("=..." if p.default else ""))
        if p.kind == "pos" and (i + 1 == len(params) or params[i + 1].kind != "pos"):
            parts.append("/")
    return ", ".join(parts)


def render(name: str, e: Entry) -> str:
    if e.kind in ("function", "method"):
        text = f"{e.text} " if e.text else ""
        out = f"{text}{name}({params_text(e.params)})" + (f" -> {e.returns}" if e.returns else "")
        return out + (f" raises {', '.join(e.raises)}" if e.raises else "")
    if e.kind == "class":
        return f"class {name}" + (f"({e.text})" if e.text else "")
    if e.kind == "field":
        return f"{name}: {e.text}" + (" = ..." if e.default else "")
    if e.kind == "const":
        return f"{name} = {e.text}"
    return f"{name} <- {e.text}" if e.text else f"{name} ({e.kind})"


def param_changes(old: Entry, new: Entry) -> list[tuple[bool, str]]:
    before = {p.name: p for p in old.params}
    after = {p.name: p for p in new.params}
    out = [(True, f"param removed: {n}") for n in sorted(before.keys() - after.keys())]
    for n in sorted(after.keys() - before.keys()):
        required = not after[n].default and after[n].kind not in ("var-pos", "var-kw")
        out.append((required, f"new {'required ' if required else ''}param: {n}"))
    for n in sorted(before.keys() & after.keys()):
        a, b = before[n], after[n]
        if a.kind != b.kind:
            out.append((b.kind != "pos-or-kw", f"param {n}: {a.kind} -> {b.kind}"))
        if a.default and not b.default:
            out.append((True, f"param {n}: now required"))
        if a.ann != b.ann:
            out.append((False, f"param {n}: {a.ann or '-'} -> {b.ann or '-'}"))
    both = {n for n in before.keys() & after.keys() if before[n].kind in ("pos", "pos-or-kw") and after[n].kind in ("pos", "pos-or-kw")}
    order = [[p.name for p in e.params if p.name in both] for e in (old, new)]
    return out + ([(True, "positional order changed")] if order[0] != order[1] else [])


def changes(old: Entry, new: Entry) -> list[tuple[bool, str]]:
    """(breaking, note) for each way `new` differs from `old`; empty when they agree."""
    if old.kind != new.kind:
        return [(True, f"{old.kind} -> {new.kind}")]
    out: list[tuple[bool, str]] = []
    if old.kind in ("function", "method"):
        out += [(True, f"modifiers: {old.text or '-'} -> {new.text or '-'}")] if old.text != new.text else []
        out += param_changes(old, new)
        out += [(True, f"returns {old.returns or '-'} -> {new.returns or '-'}")] if old.returns != new.returns else []
        out += [(True, f"new raises {n}") for n in sorted(set(new.raises) - set(old.raises))]
        out += [(False, f"no longer raises {n}") for n in sorted(set(old.raises) - set(new.raises))]
    elif old.kind == "class" and old.text != new.text:
        out.append((bool(set(old.text.split(", ")) - set(new.text.split(", "))), f"bases: {old.text or '-'} -> {new.text or '-'}"))
    elif old.kind == "field":
        out += [(True, f"annotation: {old.text} -> {new.text}")] if old.text != new.text else []
        out += [(True, "field now required")] if old.default and not new.default else []
    elif old.text != new.text:
        out.append((False, f"{old.text} -> {new.text}"))
    return out


def diff(old: dict[str, Entry], new: dict[str, Entry]) -> list[str]:
    """REMOVED, then CHANGED, then ADDED lines, each group by name; members of a removed or added class are not repeated."""
    gone, fresh = old.keys() - new.keys(), new.keys() - old.keys()

    def inside(name: str, names: set[str]) -> bool:
        return "." in name and name.rsplit(".", 1)[0] in names

    lines = [f"REMOVED  BREAKING  {render(n, old[n])}" for n in sorted(gone) if not inside(n, gone)]
    for n in sorted(old.keys() & new.keys()):
        notes = changes(old[n], new[n])
        if notes:
            mark = "BREAKING  " if any(b for b, _ in notes) else ""
            lines.append(f"CHANGED  {mark}{n}: " + "; ".join(note for _, note in notes))
    for n in sorted(fresh):
        if not inside(n, fresh):
            required = new[n].kind == "field" and not new[n].default
            lines.append(f"ADDED    {'BREAKING  ' if required else ''}{render(n, new[n])}")
    return lines


def diff_report(repo: Path, package: str, tag_a: str, tag_b: str) -> list[str]:
    lines = diff(surface(repo, tag_a, package), surface(repo, tag_b, package))
    if not lines:
        return ["no public API changes"]
    return [*lines, f"{sum(line[9:17] == 'BREAKING' for line in lines)} breaking"]


def tokens(words: int) -> int:
    return (words * TOKENS_PER_WORD + 9) // 10


def cost_row(repo: Path, rev: str, package: str) -> tuple[str, int, int, int, int]:
    try:
        readme = git(repo, "show", f"{rev}:packages/{package}/README.md").decode(
            errors="replace"
        )  # lossy-ok: measure: words are counted, never stored
    except GitError:
        readme = ""
    try:
        entries = surface(repo, rev, package)
    except GitError:
        entries: dict[str, Entry] = {}
    words = sum(len(f"{render(n, e)} {e.doc}".split()) for n, e in entries.items())
    readme_tokens, api_tokens = tokens(len(readme.split())), tokens(words)
    return package, readme_tokens + api_tokens, readme_tokens, api_tokens, sum("." not in n for n in entries)


def learning_cost(repo: Path, rev: str, packages: Sequence[str]) -> list[str]:
    names = packages or [
        line.removeprefix("packages/") for line in git(repo, "ls-tree", "--name-only", rev, "packages/").decode().splitlines()
    ]
    rows = sorted((cost_row(repo, rev, n) for n in names), key=lambda r: (-r[1], r[0]))
    width = max((len(r[0]) for r in rows), default=7)
    table = [f"{'package':<{width}}  {'tokens':>6}  {'readme':>6}  {'api':>6}  {'names':>5}"]
    table += [f"{n:<{width}}  {t:>6}  {r:>6}  {a:>6}  {c:>5}" for n, t, r, a, c in rows]
    return [*table, f"tokens = ceil(words * 1.3) of README.md (readme) and public signatures plus docstring first lines (api), at {rev}"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2], help="the git repository (default: this one)")
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("diff", help="public API changes of a package between two tags")
    one.add_argument("package")
    one.add_argument("tag_a")
    one.add_argument("tag_b")
    cost = commands.add_parser(
        "learning-cost", help="tokens to learn each package: README plus public signatures plus docstring first lines"
    )
    cost.add_argument("packages", nargs="*", help="default: every package")
    cost.add_argument("--rev", default="HEAD", help="the revision to measure (default HEAD)")
    args = parser.parse_args(argv)
    try:
        if args.command == "diff":
            report = diff_report(args.repo, args.package, args.tag_a, args.tag_b)
            print("\n".join([f"{args.package}: {args.tag_a} -> {args.tag_b}", *report]))
        else:
            print("\n".join(learning_cost(args.repo, args.rev, args.packages)))
    except GitError as err:
        print(f"api_surface: {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
