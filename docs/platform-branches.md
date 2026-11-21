# Platform branches: ask for the capability, not the OS

Owner decision for bead shelf-tyld.24 (earlier audit: shelf-q6m0). The rule is enforced by
[tests/test_arch_platform_sites.py](../tests/test_arch_platform_sites.py); its table is the roster of owners, this page does not copy it.

## The pattern

1. **A platform fact has one named owner.** The owner is named for the fact, not the OS: process table, mount list,
   credential store, rusage unit. It is one module in one package; the OS is read only inside it, and it answers the
   fact in the app's terms (`proctable.boot_id()`, `peak_bytes(usage)`), never "which OS".
2. **Everywhere else asks for the capability.** Is `sandbox-exec` on the PATH (`child_env.find`), does `/proc/mounts`
   exist, does the Keychain tool answer. A capability probe works on a fake PATH in a test and survives a new OS; an
   OS name does neither. If the question is "is this macOS", the question is wrong.
3. **An app edge passes a fact in only where the fact must vary per app.** Example: the injected `env` (PATH, HOME)
   decides where a tool is looked for. A fact that does not vary per app (the rusage unit) is never a parameter.
4. **The test enforces it.** In `packages/*/src`, any OS read (`sys.platform`, `os.name`, `os.uname()`,
   `sysconfig.get_platform()`, `platform.system()` and kin, or an OS-name literal: `darwin`, `linux`, `win32`,
   `Windows`, `nt`, `Darwin`, `Linux`) outside a listed module fails. Each row carries `fact`, `owner`, `why`; every
   row of a fact names the same owner; a row whose module stops reading the OS must leave.

To add a fact: write the owner, list it with the reason it cannot be a capability. Tests fake the owner
(`monkeypatch` `proctable.boot_id`), never the OS name.

## Recorded refusals

- **No `any-platform` package.** The facts differ (a process table, a mount list, a credential store, a unit); it would own
  none of them and every caller would still keep its own per-OS table. A fact that two packages need gets an owner named
  for the fact (`any-sandbox`), not for the OS.
- **No injected `Host` value** (a `Host("darwin")` passed down). Every API would gain a parameter, every caller would
  thread it, and the branch would still sit at the far end. The capability question needs no parameter.
- **No Windows.** The shelf runs on macOS and Linux; no Windows path exists or is tested. A consumer that must run on
  Windows redoes this verdict.

## Follow-ups from the audit (all done in this change)

| Follow-up | Result |
|---|---|
| stream-proc `owned` read the OS twice | `proctable` exposes `boot_id` and `inspect`; `owned` reads no OS; its row left the table |
| any-agent opencode `supported()` read the OS | asks `find("sandbox-exec", env, ["/usr/bin"])`; now an instance method (needs `env`) |
| anyllm `claude.exe` Windows name | deleted: no consumer, no Windows path |
| any-speech `_child` duplicated the rusage unit | stream-proc `peak_bytes(usage)` is the one owner; the row left the table |
