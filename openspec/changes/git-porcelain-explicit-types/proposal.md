## Why

Explicit `pyrefly check packages/git-porcelain/src` reveals 18 errors hidden by ancestor-directory discovery in the normal gate. `shelf-66d2` repairs the package typing prerequisite; `shelf-j4qq` separately owns gate discovery. No global gate or severity changes belong here.

## What changes

Describe the existing immutable output contract as a readonly property only during type checking. Retain runtime dataclass fields, constructor order and the single inherited redaction method. Add concrete types to empty mappings and lists; express parser records as explicit pairs and remove the obsolete trailer ignore. Align the repository identity record documentation with its common-directory-derived root.

## Scope

Only `git-porcelain` source and this OpenSpec evidence. No new dependencies, public signatures, runtime modes, type escapes, release operations or consumer integration.
