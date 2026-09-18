# 0015 — Ergonomics is a capability: the surface promotes, and `any-*` is not only about swapping backends

- **Status:** decided (2026-09-18)
- **Expires:** 2027-09-18 (re-justify once at least two `any-<domain>` pieces exist whose value is the surface rather than a backend swap — if every one of them turned out to be a thin restatement nobody adopted, the third trigger below is manufacturing packages and should be cut)
- **Track:** governance / the promotion model
- **Distilled into:** agent-loop.md `WORKFLOW: SEAM` (a third trigger — the ergonomics complaint; and the PROMOTE direction gains the surface-shape rule), `WORKFLOW: PROMOTE` step 3 (the shape sub-step), `WORKFLOW: RECONCILE` (the bag-of-functions question)

## The fork

`SEAM` fires on two triggers today: *about to write substrate glue*, and *just fixed a bug whose
root cause was a dependency* (resolution 0012, the sharp edge). Between them sits a third case that
fires neither, and it is the most common one of the three:

> The dependency is correct, documented, correctly used, and did not bite you. It is just
> **verbose**. You wrote six lines and a comment to get one value, and while writing them you
> thought *"why isn't this a method?"*

Nothing in the loop hears that. There is no bug to trace, no glue to write — the library works, you
simply had to say too much to use it. So the six lines get written inline, or into a private
`_helpers.py`, and they get written again in the next app. The thought that would have promoted the
piece is the one thought the loop discards.

The seeding case (a2kay, 2026-09-18): `src/a2kay/core/links.py` — 122 lines that hand-roll
CommonMark fenced-block and inline-code range detection so that a `[[wikilink]]` inside a code span
is not mistaken for a link, then hand `re.Match` objects to five call sites. No markdown library is
wrong here and none was fought. The file exists because reading links out of a markdown body, with
code spans excluded, is not a method on anything — so a2kay grew its own, privately, and the five
consumers inside one app each re-derive `.group(1)` is the anchor.

## What was pushing against it

Three existing rules each read, from inside a session, as a reason not to do this:

- **Resolution 0008** (name for the deliverable) and **resolution 0012**'s sizing rule ban
  `logging-extra` / `httpx-utils` — a package named after the library it patches. Correct, and it
  is easy to over-read as *"a package that exists to improve one library is the disease."*
- **Constitution III** (leave it smaller) and **Article VIII** (deletion is a virtue) read as
  anti-growth. A surface whose whole point is to *accumulate* methods over years looks like the
  accretion those articles warn about.
- **`any-lib`** is glossed as *"stop caring WHICH backend"*, and its exemplars (`anyllm`,
  `anyembed`, `any-browser`) all have several interchangeable backends. A domain with exactly one
  sane library therefore looks like it has no `any-*` to build.

None of the three actually forbids the case. All three obscure it, which is the same thing at 2am
in the middle of a feature.

## The rule

> **An ergonomics gap is a promotion trigger.** If a dependency is correct and you still had to
> write an expression you wish were a method, that expression is substrate — promote it. "Stop
> caring about X" (the capability litmus) includes *how much you must type to use X*, not only
> which implementation is underneath.

Three clauses follow from it.

**1. `any-*` is a domain promise, not a backend-swap promise.** The `any-` prefix means *the
consumer stops caring about this whole domain*. A backend swap is the most visible way to earn it;
an ergonomic surface over a single library earns it just as well. `any-markdown`, `any-datetime`,
`any-archive` are legitimate names with one, two, or zero third-party implementations underneath —
the count is an implementation detail, which is the exact thing the name promises the consumer will
stop tracking.

**2. The names get *more* generic, never library-shaped.** This upholds 0008 rather than bending it:

```
  ✅ any-markdown      the domain. the library underneath may change, split, or be ours
  ✅ any-datetime      (and note timefmt already exists — check before minting a sibling)
  ❌ markdown-it-extra  named for the origin library
  ❌ datetime-utils     "utils" names nothing a consumer can want
```

The test from 0008 is unchanged — read the name cold, does it say what you get. The change is that
"improves one library" is no longer evidence you are naming an origin; `any-<domain>` states a
deliverable even when exactly one library realizes it today.

**3. Several libraries fused into one surface is the same move, not a different one.** Taking the
best half of two libraries and hiding the seam between them is `kind = "composite"` (`convert-md`
already does this with docling/pandoc/markitdown/trafilatura). Nothing new is needed in the
ontology for it — what is new is that *wanting a better surface* is sufficient reason to reach for
it, where previously only *needing several backends* was.

## The shape: a growing object is a legitimate deliverable

The loop's vocabulary — helper, wrapper, adapter, abstraction *over an API* — is function-shaped,
and function-shaped promotions produce a module of free functions that each take the raw type back
as their first argument. That is the shape a2kay's `links.py` has, and it is why five call sites
each hold a `re.Match`.

> **Where a domain has a thing, promote the thing — a type the consumer holds and passes around,
> which owns its own reading, its own laziness, and its own derived values — not a drawer of
> functions over someone else's type.**

```
  bag of functions                       the thing
  iter_body_wikilinks(body) -> Match     doc = Markdown.from_path(p)   # body read lazily
  link_anchor(match) -> str              doc.wikilinks                 # -> Sequence[WikiLink]
  sub_body_wikilinks(body, fn) -> str    link.anchor / link.name / link.span
  canonical_id(anchor) -> str            doc.replace_wikilinks(fn)     # -> Markdown
```

Two consequences the older articles do not cover:

- **Accumulating methods on one coherent type is growth, not accretion.** Constitution III's "leave
  it smaller" governs *dead code and duplication*; it never asked a capability to stay thin. A
  `Markdown` that gains a method a year, each one earned by a real consumer, is the shelf working —
  the kitchen-sink test at `RECONCILE` is *unrelated concerns fused*, not *many methods on one
  subject*.
- **Inherit almost never; wrap almost always.** Subclassing a third-party type inherits its
  breaking changes and its surprises — `datetime` arithmetic on a subclass returns base `datetime`,
  and an upstream field addition silently changes your type. Hold the library's object as an
  attribute and expose it (`.raw`, `.underlying`) so an escape hatch exists. Inheritance is
  justified only where the library is explicitly designed as a base class.

## The ambition this serves, and the guard that survives it

The stated aim is for the shelf to become **a standard library for the stuff a real app actually
needs** — the layer you reach for before writing anything, the way you reach for `pathlib` instead
of string-splitting a path. That ambition is the reason this resolution widens the trigger: a
standard library is judged by how little its users must type, and a shelf that only captures glue
and bug-lessons will never be reached for first.

It is also the exact ambition that could rot the catalog, so the guard from resolution 0006 stands
**unchanged and is load-bearing here**:

> **Extracted, never invented.** An ergonomics complaint counts only when *you already wrote the
> awkward expression in a real app*. "A standard library would have an `any-csv`" is not a trigger;
> it is how a catalog fills with empty packages nobody adopts.

So the ambition licenses **breadth of subject** (any domain an app touches is fair game for a
piece) and **richness of surface** (the piece may grow a real object). It licenses nothing about
**provenance**: every piece still starts as code an app needed and ran.

## The risk, named

Three, in descending order of likelihood:

1. **Trivial wrappers.** "I wish this were a method" is cheap to think and cheap to satisfy, and a
   one-line delegation that saves one line is not DEEP (constitution VI). The counterweight is
   already in place — *adopt* stays conservative, so a shallow piece nobody adopts shows up as an
   orphan at `RECONCILE` and gets deleted. The cost of the mistake is a demote; the cost of never
   promoting is the six lines rewritten in every app.
2. **Object-shape cargo-culting.** "Promote the thing" becomes a class wrapping one function.
   The test is whether the type carries *state worth holding* — a lazily-read body, a parsed tree,
   a cached derivation. Stateless and single-purpose is a function, and always was.
3. **`any-*` inflation.** The prefix currently marks a real, hard-won substrate-indifference
   (`anyllm`). Spreading it to every domain dilutes what it announces. Accepted deliberately: the
   dilution is the point — the prefix should mean "you stop caring about this domain", and the
   backend-swap reading was the narrower accident, not the definition.
