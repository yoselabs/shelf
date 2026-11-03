# Rubric

Contents: tests per verdict · naming · vendoring · evidence · bead bodies

## Tests per verdict

Run in order; the first yes decides.

1. **Product test.** Would the owner lose differentiation by someone else owning this code? Is it
   glue on the host's own contracts? Yes: **skip**. Write the one-line reason.
2. **Shelf test.** `rg` the shelf's `packages/` and catalog for the concept, not the name. Does a
   package already do the job?
   - Host reimplements it: **adopt**. Host vendors it but never imports it: **adopt**.
   - Package covers most; host adds a generic piece: **evolve**.
3. **Depth test.** Imagine deleting the module. Does the complexity reappear across several callers
   or in one place? Interface nearly as big as the body: shallow, **skip**.
4. **Promote test.** Generic, deep, no shelf equivalent: **promote**. One consumer is enough.

Each row carries the reason it fails the other three verdicts. "Interesting" is not a reason.

## Naming

- `any-<domain>`: swappable backends behind one interface (any-agent, any-browser).
- A wrapper of exactly one external tool takes the tool's name (git-porcelain, beads-client).
- Check `ls $SHELF/packages` for a sibling before inventing a name.

## Vendoring

Stdlib-only hosts vendor via the shelf's vendor tool. A package for them must be stdlib-only, with no
import of the host. Say so in its bead.

## Evidence

Each verdict names: file paths, line or file counts from a command you ran, and the shelf package or
catalog line it was compared against. Subagent numbers are leads until you re-run them.

## Bead bodies

Context: what the module does and where. Acceptance Criteria: observable outcomes, including "host
deletes N lines" and "the shelf package gains tests for X". Touches: paths in host and shelf.
