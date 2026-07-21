# 0012 — Sharp edges are a promotion *trigger*, not just a promotion candidate

- **Status:** decided (2026-07-22)
- **Expires:** 2028-01-22 (re-justify once the bugfix trigger has fired from the loop in at least two consumers other than a2web — if it never fires, the trigger is unreachable and should be cut, not kept)
- **Track:** governance / the promotion model
- **Distilled into:** agent-loop.md `WORKFLOW: SEAM` (second TRIGGER + the sharp-edge test in the PROMOTE direction)

## The fork

The *category* was never missing. Doctrine idea 4 already names "an abstraction
over an awkward stdlib/library API" as promotable, and `SEAM`'s trigger already
lists "a wrapper over an awkward stdlib or third-party API". On paper this class
was covered twice over.

It still wasn't reaching the shelf. What is missing is not the category — it is
the **moment**.

Every existing trigger fires on *"you are about to write."* This class is never
discovered that way. The seeding case (a2web, 2026-07-22):
`a2web.log.add_handler` grew a `replace_existing=True` default because
`logging.getLogger()` is a **process-global** registry while `build_app()` runs
many times per process. Each rebuild stacked another OTel handler, so the Nth
build emitted N spans per event — no crash, no error, just silently multiplied
telemetry. It surfaced only because a single-span test passed alone and failed in
the full suite.

Nobody sat down intending to write a logging abstraction. Someone chased a
confusing bug for an hour, added six defensive lines, and moved on. **At write
time it looked like a bugfix, not like substrate** — so no trigger fired, and the
lesson stayed private to one repo.

That is the general shape, and it inverts the economics the existing triggers are
tuned for:

```
                  CHEAP to discover          EXPENSIVE to discover
 LOTS of code   │ boilerplate               │ a real subsystem
                │ → the existing triggers   │ → nobody misses this one
                │   already catch this      │
 LITTLE code    │ trivia — inline it        │ ★ SHARP EDGES
                │                           │ → the gap this resolution closes
```

Boilerplate is expensive to type and cheap to know. A sharp edge is the mirror
image: **the code is trivial and the discovery is expensive.** Which is precisely
why it must be promoted — what gets amortized is not the typing, it is the
debugging.

## The rule

A **sharp edge** is a place where a dependency — stdlib or third-party — is
*correct, documented, and used properly*, and a competent engineer still gets
hurt. Nothing is missing capability-wise (`logging` has both `addHandler` and
`removeHandler`); what is missing is a safe default, an idempotent variant, a
decoded failure, an interposed layer, or a lifecycle.

The test is one question, asked at **bugfix** time rather than at write time:

> **Did we learn this from a bug, or from the docs?**

From the docs → ordinary work. Write it, or fix it upstream.
From a bug → reading harder would not have saved us; the library's *correctness*
was never the problem. **The lesson is the asset**, and it belongs in the shelf so
no other consumer pays the same discovery twice.

A second, mechanical tell — greppable, and it needs no judgement:

> **A production symbol whose only caller is a test** — a `_reset_registry()`, a
> module global that exists to be monkeypatched. That is a sharp edge that was
> worked *around* instead of solved.

Five recurring kinds, all observed in a single consumer sweep (a2web, 2026-07-22),
offered as search patterns rather than as a taxonomy to be completed:

1. **Unsafe default** — the library does it, but defaults to the dangerous choice
   (`addHandler` appends unconditionally; `Handler.handleError` writes a traceback
   to `stderr`, fatal on a stdio-protocol server).
2. **Missing idempotence** — the operation is not safe to repeat, and real
   programs repeat it (attach-handler, apply-schema, register-signal).
3. **Opaque failure** — a rich failure collapsed into one uninformative signal, so
   every consumer writes the same decoder. *Three unrelated vendors in one sweep.*
4. **Leaked substrate** — a lower layer escapes the abstraction (a driver writing
   to the inherited OS stderr fd, bypassing `sys.stderr` entirely).
5. **No lifecycle** — the library assumes a short script; you run a long-lived
   server (idle reaping, non-daemon worker threads, teardown).

## What changes (propagated)

- `SEAM` gains a **second TRIGGER** — the bugfix moment — alongside the existing
  "about to write substrate glue" one.
- `SEAM`'s PROMOTE direction gains the sharp-edge test and the only-caller-is-a-test
  tell.
- A **sizing rule** (below), because this trigger has a specific failure mode.

## The risk, named

**The failure mode is junk-drawer packages.** When the framing is "the library is
missing something, let's fix it for everyone," the natural package name is
`logging-extra`, `httpx-extra`, `sqlite-utils` — and those attract anything
vaguely adjacent until the shelf rots. Resolution 0008 already forbids naming a
package for its *origin app*; a sharp edge makes it tempting to name one for the
*library it patches*, which is the same disease from the other direction.

So the sizing rule: **a sharp edge is normally a feature of a capability package,
not a package.** `add_handler`'s fix ships inside a typed-events package — one
about emitting typed events — never inside `logging-utils`. If no capability
package exists to host it, that is the signal to ask what capability you are
actually building; it is never the signal to create `<lib>-extra`.

Second risk: **over-firing.** Most bugs are our own logic, and those are not
sharp edges. The trigger is specifically a bug whose root cause is a
*dependency's* behaviour. If the shelf starts accumulating one-line "fixes" for
ordinary defects, the trigger is what needs tightening, not the workflow.

Third, and worth stating because it cuts against the shelf's own instinct: if the
sharp edge belongs to something **we own** (a shelf package, or a framework in the
same org), fix it *there*. Do not package a patch around your own house.
