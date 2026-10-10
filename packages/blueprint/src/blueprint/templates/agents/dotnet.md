# .NET conventions

Stack: dotnet (.NET 10 SDK, C# 14). The gate is `make check`; this file is what to know before writing code.

## Tools per role

| role | tool | configured in |
|---|---|---|
| toolchain | `global.json` pins the SDK (`rollForward latestPatch`); NuGet lock files committed, locked mode in CI | `global.json`, `Directory.Build.props` |
| formatter | CSharpier (layout only; no `dotnet format`) | `.config/dotnet-tools.json`, `.csharpierignore` |
| linter | SDK analyzers `latest-all` + Meziantou + Roslynator + Sonar, warnings as errors | `Directory.Build.props`, severities in `.editorconfig` |
| types | nullable enabled, nullable warnings are errors | `Directory.Build.props` |
| dependencies | central package management, transitive pinning, NuGetAudit as errors | `Directory.Packages.props` |
| tests | xunit.v3 on Microsoft.Testing.Platform, one test project per layer; CsCheck for properties | `global.json` |
| coverage | no proven .NET floor yet: do not claim one | - |
| spelling | typos with a committed config | `typos.toml` |
| architecture | BannedApiAnalyzers (`BannedSymbols.*.txt`) + ArchUnitNET tests | see [architecture.md](architecture.md) |
| hooks | prek: `dotnet csharpier check` and `typos` on staged files; `make check` on pre-push | [gate.md](gate.md) |

Do not add StyleCop (its layout rules fight CSharpier) or Roslynator.Formatting (a second layout owner).

## Run

```bash
make check    # the gate: whole repo
make build    # dotnet build -warnaserror
make test     # dotnet test --solution <sln> --no-build   (no --nologo: the runner rejects it)
make fmt      # csharpier format
```

## Code rules

| rule | why |
|---|---|
| Settings and versions live only in `Directory.Build.props` and `Directory.Packages.props`; a `.csproj` carries neither | One place to read and to bump |
| Never `#pragma warning disable` or `[SuppressMessage]`: add a path-scoped `dotnet_diagnostic` line to `.editorconfig` with a reason | Suppressions stay visible and scoped |
| No `!` null-forgiving outside tests | It silences the check that finds nulls |
| `// why:` on a non-obvious decision (units, determinism, a workaround with a link) | The code cannot say why |
| `<summary>` on public types and entry points of library projects: contract and invariants, not every member | Agents read contracts; per-member noise hides them |
| No file headers; no comment that restates the code | Noise |
| One type per file, file named after the type | Navigation by name |
| Core projects take no clock, random, thread or environment directly; pass them in | Determinism and tests |

## Layout and naming

| thing | convention |
|---|---|
| Projects | `src/<Name>.<Layer>/`, tests `tests/<Name>.<Layer>.Tests/`, architecture tests `tests/<Name>.Architecture/` |
| Names | types, methods, properties `PascalCase`; private fields `_camelCase`; interfaces `IName`; async methods end `Async` |
| Test names | `Behaviour_when_condition`; never after a bead or fix |

## Traps

- The Godot-style `OnX` callback flagged CA1822 or S2325: see [godot.md](godot.md); elsewhere make the method static.
- A lock file out of date after a package bump: run `dotnet restore` and commit every `packages.lock.json`.
- NuGetAudit failing offline: `NU1900` is excluded from errors on purpose; other audit warnings stay errors.
- `dotnet build` on pre-commit is too slow; the hook runs formatter and spelling only.
- Two architecture-test libraries in one repo: keep one (ArchUnitNET).
