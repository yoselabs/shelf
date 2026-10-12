# shelf-ij8: shell stack profile and a secrets concern

Verdict: built from drafts, both evidenced on one consumer (a homelab scratch copy, 18 tracked scripts, 18 sops files). `profiles/shell.toml` is `provisional`; `concerns/secrets.py` and `concerns/shell.py` (strict mode) are engine code with tests.

Evidence key: tested = run here (shellcheck 0.9.0, shfmt 3.14.1 via `mise exec shfmt@3.14.1`, gitleaks 8.30.1, sops 3.13.3); read = registry listing; untested.

## Shell
| role | answer | evidence |
|---|---|---|
| detect | >= 2 `*.sh` within 3 levels, or one of >= 10 lines; skip `.beads/hooks` | tested on a planted 2-line `exec` wrapper (does not fire); engine tests in test_shell_and_images.py |
| linter | shellcheck, default severity (style and up), each disable inline with a reason | tested: homelab's 18 scripts exit 0 at error, warning, info and style. Planted bad.sh: `-S error` exit 0 (misses SC2086, SC2115), `-S warning` and `style` exit 1 (SC2115, SC2086, SC2094, SC2002). So never `-S error` |
| formatter | shfmt 3.14.1 `-d`, style in `.editorconfig` | tested: planted ugly.sh exit 1 with a diff, good.sh exit 0. Homelab: defaults exit 1 (41 hunks); a 2-space editorconfig exit 1 (32 hunks, 15 files): a one-time `shfmt -w`. mise registry: `shfmt` = aqua:mvdan/sh (read) |
| types | strict mode, engine row `stack.shell.strict-mode` | a naive `-eu + pipefail` rule flags 6 of 18 homelab scripts: 3 are `set -uo pipefail` on purpose (a probe that "always exits 0, never gates"), 1 is /bin/sh `set -eu` (dash has no pipefail), 2 are sourced libraries (mode 644, no set). Hence: executable files only, /bin/sh needs `-eu`, a `# strict: no -e, <reason>` waiver |
| tests | bats-core 1.14.0 (aqua:bats-core/bats-core) | read, plus `mise exec bats@latest -- bats --version`; no .bats file run: untested |
| coverage | kcov | untested |
| toolchain, dependencies, spelling, architecture | na, reasons in the profile | |
| hooks, agent-guidance | shellcheck-precommit + a local shfmt hook / docs/agents/shell.md | hook ids read in homelab's .pre-commit-config.yaml |

Homelab findings the profile raises: the hook pins shellcheck v0.10.0 while nothing else pins it; no shfmt anywhere; 32-41 shfmt hunks; the gitleaks hook rev is v8.21.2 against 8.30.1 here.

## Secrets (sops + gitleaks)
| checkpoint | rule | evidence |
|---|---|---|
| applies | `.sops.yaml` or any tracked `*.sops` / `*.sops.*`, not `.sops.yaml` itself (the `*.sops.*` glob matches it) | tested: 18 files found in homelab; `.sops.yaml` was wrongly counted until excluded |
| secrets.encrypted | dotenv: a `sops_mac=ENC[` trailer and no assignment outside `ENC[`; yaml/json: a `sops:` key and `ENC[AES256_GCM,` values. No key needed | tested: 18/18 homelab green; planted `TOKEN=hunter2` red; a real file plus one appended plaintext line red. `sops filestatus` does not exist in 3.13.3 and `sops decrypt` without a key exits 1 either way, so it cannot tell broken from sealed |
| secrets.rule-coverage | each file matches some `path_regex` (`re.search`, as sops does) | tested: 0 of 18 uncovered; a planted `hosts/new/stacks/x.secrets.env.sops` uncovered. Rules are read by regex, not a YAML parser; first-match recipient correctness is not checked |
| secrets.scanner | gitleaks reachable from the gate text (recipes, and the hook config the gate runs); hook-only fails | the scan is the gate's job |
| the scan | `gitleaks git --no-banner --redact` (history: 1.9 s on 934 commits) | tested: homelab `dir` exit 1 (1 finding), `git` exit 1 (5 findings, generic-api-key, two in a removed snapshot); a clean staged run exit 0; a planted `AKIA` + 16 characters is aws-access-token, exit 1; sops ciphertext raised nothing. The shelf: 1 finding, a model id in a test, allowlisted in .gitleaks.toml |

gitleaks is required in every repo, not only sops repos: one pinned binary, about a second, and it catches what sops cannot (a key pasted into code, a committed `.env`). Pin it in mise.toml (ADR 0024) and drop a hook's separate rev, so one version rules.

Not tested: binary-format sops files; a `.sops.yaml` using `key_groups` or `encrypted_regex` (a partially encrypted dotenv would read as plaintext); `.gitleaks.toml` allowlists on homelab's findings; Windows line endings.

Tier split (a2kay, 2026-10-11): under five scripts in a repo whose main stack is another language is `shell-scripts` (shellcheck and strict mode only; no shfmt, hooks or shell.md). a2kay's one 88-line packaging script would otherwise have brought four new rows.

2026-10-12: ADR 0026 replaced this tier; a shell script of any count turns on the whole `shell` stack.
