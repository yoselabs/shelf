## Why

The project type gate reported green while omitting every editable workspace package source directory. In the observed Pyrefly 1.3.2 environment, interpreter discovery appended 74 editable roots to `project-excludes`. The normal check covered 319 files and omitted 312 source files. Disabling these exclusion heuristics checked 631 files and exposed 94 errors plus one warning; this is a gate coverage defect, not a hidden-ancestor diagnosis.

## What Changes

- Disable automatic project-exclusion heuristics in the root Pyrefly configuration.
- Preserve the declared includes, benchmark exclusions, strict preset, error settings, sub-config exceptions, and interpreter dependency discovery.
- Exercise the real checker against an isolated editable source, a tool, and an intentionally excluded benchmark runner.

## Capabilities

### New Capabilities

- `type-gate`: project checks cover editable workspace sources and tools while retaining declared exclusions.

### Modified Capabilities

## Impact

Root type-check configuration and one gate regression test. Production type corrections are separate bounded work coordinated through Beads. Tracking: `shelf-j4qq`.
