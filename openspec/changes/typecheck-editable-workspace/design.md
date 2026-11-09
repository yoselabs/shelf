## Context

`project-includes = ["packages", "tools"]` already selected the intended roots. Pyrefly added interpreter-discovered editable `src` roots to the exclusion list, silently removing all 312 production Python source files. The existing root-relative dot-directory exclusion was not the cause in this visible worktree.

## Decision

Set `disable-project-excludes-heuristics = true` under `[tool.pyrefly]`. Pyrefly 1.3.2 supports this setting and its matching CLI option. This removes environment-derived exclusion heuristics while preserving dependency discovery and every explicit exclusion. No positional-path override is used: Pyrefly documents that positional-file mode ignores configured project exclusions.

Reference: https://pyrefly.org/en/docs/configuration/#disable-project-excludes-heuristics

## Verification

Before configuration repair, the regression fixture reported the planted tool error but omitted the planted editable-source error. The fixture creates a temporary Python environment without pip and a `.pth` pointing at its own source directory; it changes no shared environment or package source. It copies the real project configuration and invokes the installed checker in project mode. The expected diagnostics include both source and tool assignments and exclude the deliberate benchmark runner.

The actual project diagnostic run before production corrections checked 631 files: all 636 Python files under packages/tools except five intentional benchmark exclusions. It returned 94 production-source errors, 68 suppressed diagnostics, and one warning. The earlier normal run checked 319 files and returned zero errors with 61 suppressions. Those results establish coverage loss; they are not a final release-gate result.

## Risks

Removing heuristic exclusions also removes default node_modules/venv exclusions. The authored `packages` and `tools` scope currently contains no additional files selected by this change beyond the intended sources; root `.venv` is outside that scope. Explicit cache/dot-directory and benchmark exclusions remain intact. Future non-source content inside these roots must have an explicit exclusion if needed.
