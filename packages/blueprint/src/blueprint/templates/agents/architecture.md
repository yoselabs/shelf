# Architecture

Layers are declared once, in one place, and enforced by a tool that fails the gate. A rule that is
only prose is not a rule.

## Layers

<!-- Agent fills {{layers}}: one row per layer, with the enforcing tool and its config path. -->

| layer | holds | may depend on | enforced by |
|---|---|---|---|
{{layers}}

## Rules

| rule | why |
|---|---|
| The **core is free of frameworks**: no UI, engine, web, database or OS API in the layer that holds the rules | Core logic stays testable without the substrate and survives its replacement |
| Dependencies point inward only; the shell depends on the core, never the reverse | One direction makes cycles impossible |
| Wire things in one **composition root**; the core receives what it needs | Swapping a dependency touches one file |
| Declare the layer map in one file the tool reads (`{{layer_config}}`); do not restate it in prose | Two copies drift |
| Banned APIs (clock, random, global state, network in the core) live in one list with a reason per entry | The list is checked; a sentence is not |
| A new dependency edge that the map forbids is a design change: ask the owner, update the map in its own commit | Silent edges rot the layers |
| Shared domain terms live in CONTEXT.md and are used in code names ([domain.md](domain.md)) | Names are the cheapest architecture |

## Where code goes

| you are adding | put it | check |
|---|---|---|
| A business rule | core, in the module that owns the concept | core imports no framework |
| A call to the outside (file, network, engine) | an adapter in the outer layer behind a core-owned interface | adapter imports core, not reverse |
| A screen, command or endpoint | the surface layer: parse input, call core, format output; no rules | no rule logic outside core |
| A cross-cutting helper | the lowest layer that needs it; if generic, promote it to the shelf | grep the shelf first |

One concept per file ([constitution.md](constitution.md) article 6).

## Changing a layer

Edit the map and enforcer config together; plant a forbidden edge, see the gate fail, remove it; record an ADR.
