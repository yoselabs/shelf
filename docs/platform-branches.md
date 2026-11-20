# Platform branches: where they live, and why there is no `any-platform`

Verdict for bead shelf-q6m0 (OS-switch audit), written from the allowlist in
[tests/test_arch_platform_sites.py](../tests/test_arch_platform_sites.py), which fails the gate on any
platform read outside it (bead shelf-tyld.14). The allowlist is the table: this page does not copy it, it
judges it.

## Verdict per site

| Module | What it switches | Verdict |
|---|---|---|
| stream-proc `procmac`, `proctable` | libproc (macOS) vs `/proc` (Linux) process table | Legitimate. One adapter: `proctable` is the selector, the two natives sit behind it. Owner: stream-proc |
| stream-proc `owned` | `boot_id` per OS; `inspect_process` picks `procmac` or `procfs` | Move behind the selector. It repeats `proctable`'s choice twice; `proctable` should expose `boot_id` and `inspect`, and the row leaves the allowlist. Not done here: `tests/test_owned.py` fakes the OS by patching `owned.sys.platform` for both natives on one machine, so the move rewrites that seam. Owner: stream-proc |
| sqlite-store `filesystem` | `/proc/mounts` fs-type probe, Linux only, else `unknown` | Legitimate and local. A degraded answer, not two implementations |
| anyllm `claude_code_sdk` | `claude.exe` on Windows; macOS Keychain probe | Keychain: legitimate, it is knowledge of one CLI's credential store. The Windows name: suspect, the shelf runs on macOS and Linux (no Windows path is tested); delete it unless a consumer runs on Windows. Owner: anyllm |
| any-agent `harnesses/opencode` | `supported()` is `sys.platform == "darwin"` because the sandbox is `sandbox-exec` | Wrong question. The fact is "is `sandbox-exec` present", not the OS; ask `child-env.find("sandbox-exec", ...)` and drop the OS read. Owner: any-agent |
| any-speech `adapters/_child` | `ru_maxrss` is bytes on macOS, kilobytes on Linux | Legitimate and local: one unit constant beside the one `wait4` call that returns it |

## Is a shared dispatch package worth it? No.

Constitution VI and VII promote a shape only when it repeats. The five packages read the platform for five
different facts: a process table, a mount list, a credential store, a sandbox tool, an rusage unit.
Only stream-proc has the shape "one interface, one implementation per OS, chosen at the edge", and it
already holds it inside its own owner. A package named `any-platform` would own no fact; every caller
would still need its own table of per-OS answers. Recorded refusal.

## What would change this

- A third package needs the same fact as another (for example two packages both ask "is this macOS").
  Then the fact gets an owner named for the fact (`any-sandbox`, not `any-platform`).
- A consumer must run on Windows. Then the OS-name reads become a real dispatch and this verdict is redone.

## Follow-ups (small, each local to one package, none started)

1. stream-proc: `proctable` exposes `boot_id` and `inspect`; `owned` stops reading the platform; its row leaves the allowlist.
2. any-agent: `supported()` asks for `sandbox-exec` on the PATH instead of the OS.
3. anyllm: delete the Windows binary name if nothing uses it.
