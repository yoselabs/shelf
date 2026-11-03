# Reviewer brief

Copy everything below the line into each subagent prompt. Fill the three placeholders.

---

You review one seam of a codebase for code that belongs in a shared library shelf. Read-only: change
no file, run no tests, file no bead.

Host repo: <HOST_PATH>
Seam: <DIRECTORY AND MODULE LIST>
Shelf packages (name: one-line capability): <INVENTORY>

For every module in the seam, return one row:

`module | lines | callers (command + count) | what it does, one sentence | closest shelf package or none | generic? yes/no/partly | shallow or deep | your verdict: adopt/evolve/promote/skip | reason it fails the other three`

Rules:
- Run `wc -l` and `rg` yourself and paste the commands you ran; give counts only from them.
- Compare against the shelf by concept: read the package source when the capability line is close.
- Say "not sure" when you are; do not guess a count.
- A client for the host's own backend, or a UI on its API, is skip: glue.
- Finish with the three modules you are least sure about and what would settle each.
