# Blueprint

The shelf's one skill for setting up, auditing and keeping any software repository to the owner's
standard: its concerns, the checks for each, the remediations, the per-stack answers, and the
culture files every repo carries. Terms here are the skill's own; general engineering words are
used in their ordinary meaning (owner rule, 2026-10-10: reuse accepted names from computer
science and software engineering before coining one).

## Language

### What blueprint checks

**Concern**:
One point of view a repository is judged from, such as type checking, CI, hooks or decision
records. The unit the checklist and the stack profiles are organised by.
_Avoid_: pillar (lifesim's product-design word), area, aspect, domain

**Checkpoint**:
One statement that must be true of a repository under one concern, with how to verify it and how
to remediate it.
_Avoid_: control, rule, check item

**Remediation**:
The steps that make a failing checkpoint pass, applied by the agent.
_Avoid_: fix-up, action

**Repo kind**:
What a repository fundamentally is: application, library or infrastructure. Picks which concerns
apply.
_Avoid_: project type, category

**Surface**:
A way an application is reached by its users: server (HTTP, MCP, RPC), CLI, or UI (web, desktop,
game).
_Avoid_: interface, entry point (an entry point is code; a surface is how users reach it)

**Trait**:
A property of an application that adds concerns, such as deployed, ships an image, holds secrets,
stores data, LLM-backed, or split into server and client processes. Kinds, surfaces and traits are
closed lists, extended by an ADR (ADR 0026).
_Avoid_: feature, flag

**Fact**:
Something detection reads from the repository that means one thing only, such as a Dockerfile
present or a workflow step that pushes an image. A fact turns checkpoints on by itself.
_Avoid_: signal (used loosely for both fact and evidence)

**Evidence**:
Something detection reads that points to a kind, surface or trait without proving it, with a
confidence: high or low. The agent judges low-confidence evidence itself or asks the owner.
_Avoid_: hint, heuristic, guess

**Classification**:
The repository's recorded kind, surfaces and traits, each with who decided it (detected, agent or
owner) and a justification; rejected evidence is recorded too, so it is not asked again.
_Avoid_: profile (the profile is the whole detected-plus-declared picture), tags

**Stack profile**:
The per-stack answers to every concern that has a stack answer: which tool, pinned how,
configured where, run by which target.
_Avoid_: pack, tech pack, preset (a preset is one config inside a profile)

**Concern registry**:
The full set of concerns and their checkpoints, shared by every direction of the skill.
_Avoid_: checklist, inventory (the inventory is the raw draft it is built from)

### How a run goes

**Direction**:
One path through the skill chosen at the start of a run, such as start or audit; directions share
the concern registry.
_Avoid_: mode, workflow

**Verdict**:
The result recorded for one checkpoint in one run: not set up, failing, passing, not applicable,
or not checked.
_Avoid_: status (statuses belong to work items), score

**Override**:
A recorded decision that one checkpoint does not hold, optionally only for a scope (a path, a
compose service), with a reason, who decided, and an expiry or an ADR. The one way to except
anything blueprint checks; a linter's own suppression (`# noqa`) stays the linter's, with a reason.
_Avoid_: exception, waiver, skip, exempt, lenient

**Interim path**:
A temporary route to compliance proposed for a legacy repository when full remediation today is
too costly; it carries an expiry and is the rare case, not the default.
_Avoid_: carve-out, workaround

### What a repo carries

**Constitution**:
The repository's own articles on how work is done there, citing the shelf constitution, and
pointed to from AGENTS.md.
_Avoid_: policy, guidelines

**Blueprint state**:
What blueprint keeps in a repository between runs: its overrides, the checkpoint-set hash it was
audited against, and the generated reports, all under `docs/blueprint/`.
_Avoid_: lock file, audit log
