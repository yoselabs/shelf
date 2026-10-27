"""Secrets: a sealed file really is sealed, and a sops rule covers it.

A `.sops` name proves nothing: a plaintext file renamed in passes every reader, so the files are read for
sops's own markers, which needs no key. Research: openspec/changes/blueprint-skill/research/shell-and-secrets.md.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from blueprint.model import check, failing, not_applicable, not_checked, not_set_up, passing

if TYPE_CHECKING:
    from blueprint.model import Context, Finding

# A sops file by name: `x.sops`, `x.sops.yaml`, `x.secrets.env.sops`; `.sops.yaml` is the rules file, not a secret.
_SOPS_NAME = re.compile(r"(^|/)[^/]*\.sops(\.[^/]*)?$")
_RULES = ".sops.yaml"
_NO_SOPS = "no sops files and no .sops.yaml: this repo seals no secrets"
# dotenv: the trailer holds `sops_mac=ENC[`; yaml/json: a top-level `sops:` key. Both carry ENC[AES256_GCM, values.
_DOTENV_MAC = re.compile(r"^sops_mac=ENC\[", re.MULTILINE)
_TREE_KEY = re.compile(r'^sops:|"sops"\s*:', re.MULTILINE)
_ENC = re.compile(r"ENC\[AES256_GCM,")
_PATH_REGEX = re.compile(r"^\s*-?\s*path_regex:\s*['\"]?(.+?)['\"]?\s*$", re.MULTILINE)


def _sops_files(ctx: Context) -> list[str] | None:
    listed = ctx.git("ls-files", "-z")
    if listed is None:
        return None
    return [p for p in listed.split("\0") if p and p != _RULES and _SOPS_NAME.search(p)]


def _plain(text: str) -> list[str]:
    """dotenv: the keys whose value is not ENC[...]; comments and the sops_ trailer hold no secret."""
    lines = (ln for ln in text.splitlines() if ln.strip() and not ln.startswith(("#", "sops_")))
    return [ln.split("=", 1)[0] for ln in lines if not re.match(r"[^=]+=ENC\[", ln)]


def _sealed(text: str) -> bool:
    if _DOTENV_MAC.search(text):
        return not _plain(text)
    return bool(_TREE_KEY.search(text)) and bool(_ENC.search(text))


@check("secrets.encrypted", "every sops file in git is encrypted: sops markers on every value, no plaintext line")
def encrypted(ctx: Context) -> Finding:
    """Read without a key: dotenv values are all `ENC[...]` with a `sops_mac`; yaml/json carry a `sops:` block."""
    files = _sops_files(ctx)
    if files is None:
        return ctx.not_a_repository()
    if not files and ctx.read(_RULES) is None:
        return not_applicable(_NO_SOPS)
    bad = [rel for rel in files if not _sealed(ctx.read(rel) or "")]
    if bad:
        return failing(
            f"not encrypted, or holding a plaintext value: {', '.join(bad)}",
            "`sops encrypt -i <file>`, then rotate what it held: the plaintext is in git history",
        )
    return passing(f"{len(files)} sops file{'s' if len(files) != 1 else ''}, every value ENC[...] with a MAC")


@check("secrets.rule-coverage", "every sops file matches a creation_rules path_regex in .sops.yaml")
def rule_coverage(ctx: Context) -> Finding:
    """sops picks recipients by the first matching rule; a file no rule matches cannot be re-keyed (`sops updatekeys`)."""
    files = _sops_files(ctx)
    if files is None:
        return ctx.not_a_repository()
    rules = ctx.read(_RULES)
    if not files and rules is None:
        return not_applicable(_NO_SOPS)
    if rules is None:
        return not_set_up("sops files and no .sops.yaml", "add .sops.yaml with a creation_rules path_regex per secrets folder")
    regexes = _PATH_REGEX.findall(rules)
    if not regexes:
        return not_checked("no `path_regex:` line in .sops.yaml; rules written another way are not read")
    uncovered = [f for f in files if not any(re.search(r, f) for r in regexes)]
    if uncovered:
        return failing(f"no creation_rule matches: {', '.join(uncovered)}", "add a path_regex to .sops.yaml that matches each")
    return passing(f"{len(files)} sops file(s), each matched by one of {len(regexes)} rule(s)")
