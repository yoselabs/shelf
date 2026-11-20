# Git hooks: beads (`bd` 1.1.2) vs the hook managers

Hands-on lab, 2026-10-10. Tested: bd 1.1.2 (embedded Dolt mode), pre-commit 4.3.0, prek 0.5.5,
lefthook 2.2.1, husky 9.1.7, git 2.53.0, macOS. Throwaway repos only (lab dir in the session scratchpad).
"T" = tested in the lab, "R" = read in docs/source (beads-src clone, `bd hooks --help`), "-" = not tested.
Proof that bd's hook ran: a PATH shim `bd` that logs argv and execs the real bd (every "bd ran" below).

## 0. What bd's hooks actually do (R + T)

- `bd init` (default) installs 5 hooks into `.beads/hooks/` AND sets `core.hooksPath` to the
  **absolute** path of that dir (T). `.beads/hooks/*` get committed (T: 5 files tracked).
  `bd init --skip-hooks` does neither (T). bd is the only thing that writes hooksPath on its own.
- Each hook file = `#!/usr/bin/env sh` + a marker block `# --- BEGIN BEADS INTEGRATION v1.1.2 ---`
  that runs `bd hooks run <hook> "$@"` under a 300 s timeout. Exit 3 (no database) is turned into 0 (T, R).
- `bd hooks run pre-commit` (source `cmd/bd/hooks.go`): (1) runs `<hooksDir>/pre-commit.old` if it exists,
  (2) **only if `export.auto` is true** (default `false`, T) re-exports `.beads/issues.jsonl` and stages it.
  T: with `export.auto=true`, commit output "Exported 1 issues", and `issues.jsonl` is in the commit.
  With defaults, bd's pre-commit does nothing visible.
- post-merge / post-checkout: `.old` chain + legacy JSONL import only when no Dolt remote. pre-push: `.old` chain only.
  prepare-commit-msg: appends `Executed-By: $BD_ACTOR` trailer (T: trailer present with `BD_ACTOR=agent1`).
- `bd hooks install` without flags writes into the *current effective* hooks dir (`.git/hooks`, or the
  `core.hooksPath` dir if set — T: it appended bd blocks into a versioned `.githooks/*`).
  Non-bd hook present: bd injects its block into the existing file and leaves a one-time `.backup` (R, source).
  Doc: "content outside the markers is preserved across installs and upgrades"
  (https://github.com/gastownhall/beads/blob/main/docs/reference/git-integration.md).
- `bd doctor` is unusable here: "not yet supported in embedded mode" (T). Do not rely on it in a check script.
- bd's docs name lefthook, husky, pre-commit, prek, hk as "detected" managers and say to add bd steps
  to their config, with an `hk.pkl` example calling `bd hooks run ...` (R, same URL). That is the recipe pattern below.

## 1. Two bugs in bd's native injection (T, the reason for the recipes)

- **Appended block swallows a failing hook (lefthook, husky, hand-written scripts).** bd appends its block
  at the END of the file. If the file before it has no trailing `exit`/`exec`, the block's exit 0 becomes the
  hook's exit status. Result: a failing check does NOT block the commit (commit landed, rc=0).
  Reproduced: lefthook-first + `bd init`; lefthook + `bd hooks install` (also with `--chain`); husky-first + `bd init`;
  a hand-written `false` pre-commit + `bd init`. pre-commit/prek are safe because their scripts `exec` at the
  end and bd injects *before* that.
- **Last writer wins, silently.** Plain `pre-commit install`, `pre-commit install -f`, `prek install`, `prek install -f`,
  `husky` (npm `prepare`), `lefthook install --force` each drop or bypass bd's block/hooks dir with exit 0 and no warning
  (bd calls = 0 on the next commit). `bd hooks install` run last restores it for pre-commit/prek only.

## 2. Results: manager x install order

Key: "blocks" = a manager check that fails stops the commit; "bd ran" = shim logged `hooks run pre-commit`.
Rows with `bd init` mean default init (hooks + hooksPath). `S` = `bd init --skip-hooks`.

| Manager | Order | hooksPath after | Outcome (all T) |
|---|---|---|---|
| pre-commit | manager, then `bd init` | abs `.beads/hooks` | works: blocks + bd ran. bd copies pre-commit's script into `.beads/hooks/pre-commit` and injects its block before the `exec`. Tracked copy has a machine-local `INSTALL_PYTHON=` path. Re-running `pre-commit install` now refuses |
| pre-commit | `bd init`, then manager | abs `.beads/hooks` | **refuses**: "Cowardly refusing to install hooks with `core.hooksPath` set." Only way: unset hooksPath, install, `bd hooks install` (works, leaves dead tracked `.beads/hooks`) |
| pre-commit | S, manager, `bd hooks install` | empty | works: blocks + bd ran. Later `pre-commit install` (plain or -f) silently strips bd; `bd hooks install` restores |
| pre-commit | S, `bd hooks install`, manager | empty | works: pre-commit moves bd's file to `pre-commit.legacy` and runs it ("migration mode"): blocks + bd ran |
| pre-commit | S, manager with bd as config entry | empty | **works, stable** (recipe A). 3x reinstall + `-f`: identical hook md5; bd still runs |
| prek | manager, then `bd init` | abs `.beads/hooks` | works like pre-commit. Plain `prek install` afterwards is allowed (writes into hooksPath dir) and overwrites bd's block: bd calls 0 |
| prek | `bd init`, then manager | abs `.beads/hooks` | no refusal. prek moves bd's file to `pre-commit.legacy` and runs it: works. A second `prek install` replaces it again, dropping bd |
| prek | S, manager, `bd hooks install` / reverse | empty | works both orders; plain re-run of `prek install` drops bd's block (reverse order keeps it via `.legacy`) |
| prek | S, bd as config entry | empty | **works, stable** (recipe A) |
| lefthook | manager, then `bd init` | abs `.beads/hooks` | **BAD**: bd copies lefthook's script, appends its block: failing check does not block (rc=0, commit landed). lefthook also prints "Custom hooks paths are not supported by default" |
| lefthook | `bd init`, then manager | abs `.beads/hooks` | lefthook **refuses** (prints `--force` / `--reset-hooks-path` / unset options). `--force`: renames bd's file to `pre-commit.old`, lefthook installed, blocks, **bd never ran**. `--reset-hooks-path`: unsets hooksPath, lefthook goes to `.git/hooks`, `.beads/hooks` dead, bd never ran |
| lefthook | S, `bd hooks install`, then manager | empty | lefthook renames bd's hook to `pre-commit.old` and does not run it: blocks, bd never ran |
| lefthook | S, manager, then `bd hooks install` (also `--chain`) | empty | **BAD**: bd block appended after lefthook's script: failing check swallowed |
| lefthook | S, bd as config entry | empty | **works, stable** (recipe B): blocks + bd ran; reinstall x3 same md5 |
| husky | manager, then `bd init` | abs `.beads/hooks` | **BAD**: hooksPath moves off `.husky/_`; bd copies all 14 husky stubs into `.beads/hooks` (tracked), replaces the pre-commit shim with the user hook body, appends block: failing husky hook swallowed (rc=0) |
| husky | `bd init`, then manager | `.husky/_` | husky overwrites hooksPath; bd's hooks silently orphaned (bd calls 0); husky blocks. Same after every `npm install` (husky `prepare`) |
| husky | S, bd as script lines | `.husky/_` | **works** (recipe C); bd line must be FIRST (husky runs `sh -e`: a failing check above it means bd never runs, T) |
| none (hand-written hook) | script first, then `bd init` | abs `.beads/hooks` | script copied to `.beads/hooks/pre-commit`, bd block appended: failing `false` swallowed unless script ends with explicit `exit $?` (then blocks, but bd never ran) |
| none | S, versioned `.githooks/` + relative hooksPath | `.githooks` | **works** (recipe D): blocks + bd ran; relative path survives clone/move |

Fresh clone (T, recipes A-D plus pre-commit-first/`bd init`): nothing is active after `git clone`
(hooksPath empty, `.git/hooks` empty): pre-setup commit runs zero hooks, silently. After the documented setup
command each manager runs bd (`bd calls = 1`). Default `bd init` is worse: hooksPath is an absolute path of the
original machine, so even bd's own hooks need `bd hooks install --beads` in every clone, and the tracked
`.beads/hooks/*` carry stale machine paths. `bd hooks run pre-commit` in a clone with no Dolt DB exits 0 (T), only a
`.beads has permissions 0755 (recommended: 0700)` warning on stderr.

## 3. Recipes (one per manager)

Common rule for every recipe: **bd's hooks are wired in the manager's own versioned config, never by bd.**
Run `bd init --skip-hooks` (add `--skip-agents` only if you don't want AGENTS.md; unrelated). Never run
`bd hooks install` and never `bd init` without `--skip-hooks` in a repo that has a manager.
Already ran default `bd init`? Remedy is `git config --unset core.hooksPath` plus removing `.beads/hooks`
(`bd hooks uninstall` exists, R); this exact cleanup was not tested.

All five bd events were exercised in A, B, C, D (commit, prepare-commit-msg with arg, branch checkout with 3 args,
merge, push with remote name/url): every `bd hooks run <event> <args>` fired with the right arguments (T).

### A. pre-commit (Python) and prek: identical `.pre-commit-config.yaml`

```yaml
default_install_hook_types: [pre-commit, post-merge, pre-push, post-checkout, prepare-commit-msg]
repos:
- repo: local
  hooks:
  - id: bd-pre-commit
    name: bd pre-commit
    entry: bd hooks run pre-commit
    language: system
    always_run: true
    pass_filenames: false
    stages: [pre-commit]
  - id: bd-post-merge
    name: bd post-merge
    entry: bd hooks run post-merge
    language: system
    always_run: true
    pass_filenames: false
    stages: [post-merge]
  - id: bd-pre-push
    name: bd pre-push
    entry: bd hooks run pre-push
    language: system
    always_run: true
    pass_filenames: false
    stages: [pre-push]
  - id: bd-post-checkout
    name: bd post-checkout
    entry: sh -c 'bd hooks run post-checkout "$PRE_COMMIT_FROM_REF" "$PRE_COMMIT_TO_REF" "$PRE_COMMIT_CHECKOUT_TYPE"' --
    language: system
    always_run: true
    pass_filenames: false
    stages: [post-checkout]
  - id: bd-prepare-commit-msg
    name: bd prepare-commit-msg
    entry: bd hooks run prepare-commit-msg
    language: system
    always_run: true
    stages: [prepare-commit-msg]
  # ...the repo's real checks follow; a failing one blocks, and bd still runs (no fail_fast)
```

Install, in order: `bd init --skip-hooks` then `pre-commit install` (or `prek install`). No bd step afterwards.
Gotchas (T): a modified config must be `git add`ed or both tools abort the commit; `prek` ships patches to `~/.cache/prek`.

### B. lefthook (`lefthook.yml`)

```yaml
pre-commit:
  commands:
    bd:
      run: bd hooks run pre-commit
post-merge:
  commands:
    bd:
      run: bd hooks run post-merge {0}
pre-push:
  commands:
    bd:
      run: bd hooks run pre-push {0}
post-checkout:
  commands:
    bd:
      run: bd hooks run post-checkout {0}
prepare-commit-msg:
  commands:
    bd:
      run: bd hooks run prepare-commit-msg {0}
```

Install: `bd init --skip-hooks` then `lefthook install`. Gotcha (T): lefthook skips a command when nothing is staged
("no matching staged files"), so an empty commit or a bare `git hook run pre-commit` does not reach bd; harmless
(bd only exports when `.beads` files are staged) but it makes a dynamic check need a staged file.

### C. husky (Node repos only)

`package.json`: `"scripts": {"prepare": "husky"}`. One file per event in `.husky/`, bd line **first**:

```sh
# .husky/pre-commit   (same one-liner for post-merge, pre-push, post-checkout, prepare-commit-msg)
if command -v bd >/dev/null 2>&1; then bd hooks run pre-commit "$@"; fi
# ...real checks below
```

Install: `bd init --skip-hooks` then `npm install` (runs `husky`, sets `core.hooksPath=.husky/_`, relative, gitignored dir).

### D. no manager (versioned dir)

`.githooks/<event>` (chmod +x), one per event:

```sh
#!/bin/sh
if command -v bd >/dev/null 2>&1; then bd hooks run pre-commit "$@" || exit $?; fi
# ...real checks; end failing steps with `|| exit 1`
```

Install: `bd init --skip-hooks` then `git config core.hooksPath .githooks` (relative, portable). Do not run
`bd hooks install` afterwards: it appends bd blocks into the versioned scripts (T), duplicating the call.

Fallback if only `pre-commit`/`prek` is wanted with bd's own injection (T, works but fragile): `bd init --skip-hooks`,
manager install, `bd hooks install`, in that order, every time; any later manager install drops bd silently. Not prescribed.

## 4. Verification signals for a check script

Static, deterministic (T unless marked):

| Manager | `git config --local core.hooksPath` | Config must contain (grep -F) | Installed-hook signature | Must NOT exist |
|---|---|---|---|---|
| pre-commit | empty | `bd hooks run pre-commit` in `.pre-commit-config.yaml` (+ `default_install_hook_types`) | `$(git rev-parse --git-path hooks)/pre-commit` contains `File generated by pre-commit` | any `BEGIN BEADS INTEGRATION`; tracked `.beads/hooks` |
| prek | empty | same file | contains `File generated by prek` | same |
| lefthook | empty | `bd hooks run pre-commit` in `lefthook.yml` | `.git/hooks/pre-commit` contains `lefthook` | same |
| husky | exactly `.husky/_` | first non-comment line of `.husky/pre-commit` runs `bd hooks run pre-commit` | `.husky/_/pre-commit` exists | same |
| none | exactly `.githooks` | `.githooks/pre-commit` contains `bd hooks run pre-commit` and is executable | n/a | same |

Universal negatives: `git ls-files .beads/hooks .beads-hooks` empty; `git config --local core.hooksPath` is not absolute and does not
contain `.beads`; `grep -rl 'BEGIN BEADS INTEGRATION'` over the hooks dir, `.husky`, `.githooks` finds nothing (the recipes never let bd write hooks;
a hit means someone ran `bd init` or `bd hooks install` and the swallow/last-writer hazards are back).
`.beads/config.yaml` should exist; `export.auto` is informational (read with `bd config get export.auto`).

Dynamic (pre-commit, prek, husky, none; T): put a fake `bd` first on PATH that appends `$*` to a file and exits 0, then
`git hook run pre-commit`; the log must contain `hooks run pre-commit` (git >= 2.36). For lefthook stage one file first, or stay static.
A deeper probe: add a throwaway failing entry and assert `git commit` exits non-zero while the log still shows bd (proved in the lab for A, B, C).

## 5. Verdicts and blueprint default

| Option | Verdict | Reason |
|---|---|---|
| bd native hooks (`bd init` default, `bd hooks install`) in a repo with any manager | ❌ | silent swallow of failing checks (lefthook, husky, hand scripts), absolute hooksPath, tracked stale `.beads/hooks`, last-writer-wins |
| bd native hooks in a repo with no manager | ❌ for shared repos | absolute hooksPath breaks in every clone; use recipe D |
| A: pre-commit + config entry | ✅ | tested all orders/reinstall/clone; Python-only runtime |
| A: prek + config entry | ✅ **blueprint default** | same config and behaviour as pre-commit (T), single Rust binary, installable with `uv tool install prek`, no Node, handles any language; fallback = swap binary to pre-commit with no config change. Risk: pre-1.0 (0.5.5) |
| B: lefthook + config entry | ✅ | works, parallel, any language; needs a Go/npm/brew binary; empty-staged skip quirk |
| C: husky + script lines | ✅ for Node-only repos | works if bd line is first and `bd init --skip-hooks`; but Node dependency and `prepare` resets hooksPath |
| D: `.githooks` + relative hooksPath | ✅ | zero dependencies, portable; no staged-file/parallel/format features of a manager |
| pre-commit/prek with bd's injection (`bd hooks install` last) | untested at scale, fragile | works in T but every manager reinstall silently removes bd |

Default for a polyglot shelf repo: **prek with recipe A**. One config file, verifiable by grep, survives reinstall, and the bd
behaviour is proven for pre-commit-compatible runners. Decision rule: JS-only repo with husky already present -> C; no checks wanted -> D.

## 6. Not covered / untested

- `bd hooks uninstall`, worktrees, Windows, `--shared` (`.beads-hooks/`) mode, hk/overcommit/simple-git-hooks.
- Server-mode Dolt and a configured Dolt remote (hooks would then rarely import JSONL; export path unchanged).
- Whether bd changes the `.old`-chain or injection placement in releases after 1.1.2.
