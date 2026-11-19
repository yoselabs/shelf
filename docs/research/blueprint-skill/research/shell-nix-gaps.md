# Shell and Nix gap roles: tests, coverage (2026-10-11)
Evidence key: T = run here (scratch clone of homelab, nothing committed); R = read, not run; U = untested.
Machine: Linux x86_64, no root, no userns, no KVM, no Docker. bats 1.14.0, kcov 43+dfsg-3 (Ubuntu noble deb, extracted), nix 2.20.6 via nix-portable (proot).

## shell.tests -> standard
| step | result | key |
|---|---|---|
| subject | tools/host-target.sh (sourced helper: override, candidate probing, port precedence, fatal errors); stubs for `python3`, `ssh` on PATH | T |
| green | `bats tests/shell/host-target.bats`: 7 of 7 ok, exit 0 | T |
| red | planted: SSH_PORT precedence swapped -> case 4 fails, exit 1; "single candidate" test flipped -> cases 1,2,4,6 fail, exit 1 | T |
| bats-support/assert | not needed: plain `[ ]`/`[[ ]]` carry every assertion; nothing to pin. If a repo adds them: mise cannot pin them, vendor under tests/shell/vendor | T/R |
| missing dir | `bats tests/none/` exits 1 ("does not exist"), so a recipe over a missing tree is red, not silently green | T |
Gotchas: a sourced script that `exit`s must run in a child `bash -c` (else it kills bats); bats runs in the current dir, so `BATS_TEST_DIRNAME` locates stubs; failures print the `[[ ]]` expansion, noisy but enough.
Role: `tool` bats 1.14.0, `config` tests/shell/*.bats + mise.toml `bats`, gate text `bats`, recipe `shell-test` (dependency of `check`, like `scripts`). Not tested: whether the engine's `path` glob matches `tests/shell/*.bats` (R, profile text says "files the path matches"). Per the coordinator, exec-bit loss in a deploy bundle is a deploy-path test, out of scope.

## shell.coverage -> na (kcov works, but is not pinnable)
| step | result | key |
|---|---|---|
| install | not in mise registry or aqua; upstream last release v43 (2024-07-23), source only; Ubuntu 24.04 universe deb 43+dfsg-3 needs libdw1t64 (apt, not mise) | T/R |
| run | `kcov --include-pattern=tools/host-target.sh out bats tests/shell/host-target.bats`: no root, no ptrace; 32/38 lines = 84.21%; kcov passes bats' exit code through (1 on a red test) | T |
| floor | 80% floor: 7 tests exit 0 (84.21); 1 test only (34.21) exit 1 (out/kcov-floor.sh) | T |
Verdict: `na` (reason in roles.toml). ADR 0024 forbids a tool that mise cannot pin; revisit if aqua adds kcov.

## nix.tests -> two tiers
| step | result | key |
|---|---|---|
| eval test | tests/nix/udev-rule.nix reads `nixosConfigurations.bee.config.services.udev.extraRules` (git+file flake, `?dir=hosts/bee`) and asserts `KERNEL!="nvme*"` and `ID_PATH}=="*usb*"` | T |
| green | exit 0, "ok: bee udev rule excludes nvme..." | T |
| red | removed the nvme filter: exit 1 "udev rule lost KERNEL!=..."; removed the usb filter: exit 1 | T |
| trap | my first regex had `ID_PATH=="..."` for `ENV{ID_PATH}=="..."`: the test failed red on the REAL file. A red test is only evidence after green on real code | T |
| nix 2.20: `getFlake "path:...?dir="` rejected (unsupported parameter dir); `git+file://` works. first proot run died "ptrace Bad address"; `PROOT_NO_SECCOMP=1` runs were stable (3 of 3) | T |
| not timed; eval only, first run fetched nixpkgs + inputs from cache.nixos.org/GitHub | U |
Eval can catch (config values): udev rule text, firewall rules, option values, assertions, unit definitions (the 2026 udev-filter incident, lessonslearned section 1, is a rule-text bug: eval-catchable). Needs a VM (boot-time behaviour): coldplug replay (`udevadm trigger --action=add`), mount ordering, `nas-automount@` unit timing, "udev worker blocked" (lessonslearned 2026-08-03: a real reboot proved it). Eval proves the rule says X; only a VM shows the system does the right thing at boot.
VM tier: `pkgs.testers.runNixOSTest` as flake checks; needs /dev/kvm. R: GitHub changelog 2023-02-23 says hardware acceleration on LARGER Linux runners; a secondary source (Lix install-action, "KVM support out of the box") implies standard runners. Not verified for standard `ubuntu-latest`: U. Evidence needed: a CI job running `ls -l /dev/kvm` (add the udev-rule step from the changelog if absent) and one `nix build .#checks.x86_64-linux.<vm>` green and red on a planted bug. Job shape: separate workflow, path-filtered to hosts/**, installs nix, enables kvm, builds checks; not in local `just check`.
Mac/Docker run must show: eval test red/green with the repo's pinned nix (arm64 Linux VM has no KVM, so VM tier cannot be shown there).
Role: eval tier standard (tested, one host, one module); VM tier untested (text in roles.toml says so). Nix is a stack with no coverage notion (unchanged).

KVM on runners, tested 2026-10-12 (https://github.com/yoselabs/shelf/actions/runs/38185504352): a standard `ubuntu-latest` runner has `/dev/kvm`, but the runner user cannot open it (`test -r && test -w` exit 1, run 38184748760); after the udev rule `KERNEL=="kvm", GROUP="kvm", MODE="0666"` and `udevadm trigger --name-match=kvm` it can. So the VM tier needs no larger runner; a first `runNixOSTest` seen red and green is what remains.
