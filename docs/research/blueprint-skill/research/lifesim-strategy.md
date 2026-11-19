# Prompt: build a reusable "start and run a software project" skill from the lifesim bootstrap

Paste everything below this line to the agent that owns reusable strategies and skills.

---

## 0. Your role and goal

You own reusable strategies and skills for starting and running software projects with AI agents. You have never seen the lifesim repository or the conversation this prompt condenses. Everything you need is in this prompt; repository paths appear only as citations so the owner can look things up, never as content you must fetch.

Your goal: turn the material below into a reusable **project-start skill** (entry file, per-stack reference files, templates, state-file format, anti-pattern list; the exact deliverable is in section 13). The skill must let a fresh agent take a greenfield project from "idea and owner" to "first vertical thread of code under a green gate", on any stack, without re-learning what this project learned.

Source project: **lifesim**, a desktop life-sim (Sims 3-like) for Mac and Windows, built almost entirely by coding agents under one owner. Stack at the time of writing: Godot 4.7.2 .NET client over a C# (.NET 10) engine-free simulation library using Friflo.Engine.ECS, in-process first, client/server split later. Design knowledge lives in a typed vault (`design/`: pillars, systems, options, decisions, research, runbooks). Work queue is beads (`bd`). The bootstrap of the real code was paused mid-way on 2026-10-10 (section 11 says why).

How to read the material: every principle carries the owner's own words where they exist, the reason, the evidence, what was rejected and why, and a generalisation. Items marked **[game-specific]** apply to simulations and games; the general form is written beside them. Items marked **[unaccepted]** are agent proposals the owner has not ruled on; include them in the skill as proposals, never as rules.

Register for the skill you write: plain words, structure over prose, no diagrams in agent-facing files (literal trees, tables, schemas and commands are fine), every rule with its reason, every "done" with its check.

---

## 1. Provenance tiers (read first; this is itself a lesson)

Not every principle below has verbatim owner words. The project recorded decisions with a `decided_by` field and a `## Provenance` section quoting the owner. Four tiers exist, and the skill must carry them, because the project's gate 1 failed once on exactly this confusion (section 10, anti-pattern 2):

| Tier | Meaning | How to treat it |
|---|---|---|
| **T1 verbatim** | The owner said these words (dictation or chat). | Quote them. The rule is the owner's. A `decided_by: owner` file with no Provenance quote is an owner decision whose words did not survive; say so, never quote its body as his. |
| **T2 "yes to the recommendation"** | The agent wrote a recommendation worded so that "yes" accepts it exactly as written; the owner answered "yes" or "yes to the rest of the questions". | The *text* is the agent's wording; the *acceptance* is the owner's. Quote the recommendation and mark it T2. |
| **T3 "as relayed by the session"** | The owner answered in a form the session summarised; no verbatim text survives. | Treat as owner-accepted but flag that the wording is reconstructed. |
| **T4 session decision** | The agent chose; recorded with `decided_by: session`; the owner may overrule. | A proposal with a reason. Never present it as the owner's rule. |

Every principle below is tagged with its tier.

---

## 2. The strategy in one table

| Phase | Question it answers | Exit gate | Artefacts |
|---|---|---|---|
| A. Discover | Who is this for, what must it feel like, what may it never do, what hardware and platforms, what is first? | A one-page vision; every proposed feature can be rejected by citing a pillar; a gate review (lens audit, persona critique, blind re-audit) passed by the owner | pillars, vision, decisions, options, glossary, a layered question tree with status |
| B. Decide | Which stack, which architecture, which language, which boundaries? | Each pick cites the five proofs (section 4.B.1); every decision has provenance; nothing is chosen from memory | research folders with Findings first; decisions with provenance; refused options recorded |
| C. Spike | Does the risky claim hold on the target machine? | Every numeric claim a decision rests on is replaced by a measurement; the spike ends in a written verdict with conditions | throwaway prototype, research README with results, platform-catches entries, beads for follow-ups |
| D. Bootstrap | Can an agent write correct code here without being told twice? | `just check` (format, build with analyzers as errors, tests, content; design lint proposed, section 8) is green; each gate has been seen red once on purpose; a state file says what is done | repo skeleton, strict tooling, banned-API lists, architecture tests, scenario runner, per-folder AGENTS.md, code-structure runbook, `bootstrap.yaml` |
| E. Build | One thin vertical thread first, then features by accepted requirement | The thread passes one scenario, one golden log, one architecture test, one property test, one save/load round trip, and renders once in the client | the thread; then modules per design system, each with its scenario written first |

The order is not optional. The project's own history: platform was reopened after layer-1 design had been "done" (browser to desktop), which cost dozens of file edits (section 10, anti-pattern 1); research verdicts made before the owner stated his criterion were reversed (anti-pattern 4); the first code was written only after three research passes and two spikes.

---

## 3. Phase A: Discover (the layered design process)

**[game-specific in its areas, general in its shape.]** The project ran a five-layer design process before code. The shape generalises to any product: feelings first, behaviour second, rules third, onboarding fourth, numbers last (MDA order).

### 3.1 Layers and gates

| Layer | Decides | Gate (exit test, can be failed) |
|---|---|---|
| 1 Vision | pillars, player fantasy, target user, experience goals, tone, fail state, scope, monetization limits, session shape, platform | a one-page vision; every option gets keep/park/refuse citing a pillar; each persona can say why they would use it, or the owner records which persona is knowingly lost |
| 2 Core | the minute-to-minute loop and the systems that make it (needs, decision-making, time, personality, relationships, events) | a short unattended run of a prototype or seeded log produces one story a persona would retell; for three sampled actions the cause is readable from what the user sees |
| 3 Structures | economy, content format, UI information model, art style, architecture incl. the client/server split | a vertical slice runs at target quality on the target machine; a seeded sweep shows every resource has a source and a sink |
| 4 Experience | onboarding, pacing, retention, accessibility | strangers reach the goal without help |
| 5 Tuning and business | numbers, monetization, live ops | — |

Rules that made this work (all from the project's runbook and skill, T4 process rules the owner has run with for 19 rounds and one passed gate):

- **Frontier only.** Ask only questions whose prerequisites are answered. A question that depends on another question in the same round waits.
- **Numbered questions, recommendation worded so "yes" accepts it verbatim.** "Yes to all" is a valid answer. A verdict, not a survey: if an option fails a pillar, say which.
- **Find facts yourself.** Never ask the owner a fact you can look up.
- **Decisions out of order stay** and are re-tested at their own gate; only a failed gate check reopens one.
- **Numbers never appear in design files.** A question that needs a number becomes "name the knob, its purpose and its safe range"; the value goes to data later.
- **A prototype binds nothing** (owner decision with no verbatim quote surviving; the decision text reads "the demo binds no design choice… design never cites the demo as a reason"). It may be a measurement harness.
- **Balance claims are computed, not asserted**: a claim about dominance or runaway resources needs a seeded run or reads "not assessed — no data".
- **"Not assessed — no data" is a valid result and never a pass.**

### 3.2 Gate review = three independent checks

1. **Lens audit**: one fixed question applied with a fixed procedure and fixed output block (`Verdict / Findings with file#section / Next question`), one lens at a time, written before the next starts. A finding without a file is dropped.
2. **Persona critique**: each persona runs in its own subagent with only its card and the files; never one "average user". Output: would use / delights / dealbreakers / missing / one question for the owner.
3. **Blind re-audit**: a fresh subagent with no transcript, no audit output, no recommendations; only the file list and the machine-checkable "Test-for" lines. Every disagreement with the main audit goes to the owner.

Evidence that this catches real things (gate 1 took four review rounds):
- r2's blind re-audit disagreed on one line (tuning numbers in options); the re-audit was right and the earlier ruling was reversed.
- r3's blind re-audit found two contradictions the main audit missed (a parked option still listed as live content; a pillar that refused nothing in its own name).
- r4's blind re-audit found a stale accepted decision (`babylon-renderer` still `accepted` after the engine moved) and a runbook status table that lagged owner decisions.
- "Skip if unchanged": a review records `git hash-object` of every file read; a later review reuses a check only when every hash still matches. Any changed hash means a full review, never a partial one.

**Generalisation:** one agent pass is provisional, always. The skill must schedule blind re-audits and persona critiques as separate fresh-context agents at every gate, and must record file hashes so reviews are reproducible.

---

## 4. Phase B: Decide (stack and architecture)

### 4.A How decisions are recorded (used in every phase)

Shape (the project's template; T4 process rule that the owner has accepted by use):

```markdown
---
title: <the choice as a sentence>
status: accepted | superseded
date: YYYY-MM-DD
decided_by: owner | session
about: [system/<slug>, pillar/<slug>]
derived_from: [research/<slug>]      # if research informed it
supersedes: [decision/<slug>]        # both directions, both in frontmatter
chooses: [option/<slug>]  refuses: [option/<slug>]
---
In the context of <area>, facing <the tension>, we decided <the choice>, to <the reason>, accepting <the cost>.

## Provenance
<Round, question number, and the owner's verbatim answer; or "session decision" with the reason>

## Decision
<the rule in plain words; knobs named, no numbers>

## Consequences
<what it settles, opens, unblocks; which beads it creates or supersedes>
```

Rules:
- One choice per file. Several answers to the same choice go in one file.
- `decided_by: owner` only for the owner's explicit answer ("yes" counts). Anything inferred or filled in is a separate `decided_by: session` decision or stays a question.
- Supersession: the new file lists `supersedes:`, the old file gets `status: superseded` and `superseded_by:`; never delete the old one; sweep documents that still quote it the same day.
- Write down what is **refused** and why, not only what is chosen; refused options come back otherwise.
- Ideas go to an options list, work goes to the tracker, decisions go to the decision log; nothing lives only in chat.
- Edit accepted text only on an explicit owner answer that says so.

### 4.B The owner's engineering principles (with quotes)

#### B.1 Stack picks favour proven, widely used tools that work together — T1

> "they should be compatible and should be well used and trained and played together… the community experiences, people complaining about problems, at the same time saying that they use it… it should be proven track."

Rule: a tool qualifies only if it (1) is compatible with the rest of the stack, (2) is widely used together with it, (3) models are well trained on it, (4) the community reports real use, complaints included, and (5) has a track record in shipped work. Each stack pick cites evidence for the five points in its research.

Evidence of use: the C# vs Rust research scored both languages against exactly these five criteria in a table (C#: native Godot language, Slay the Spire 2 shipped on Godot C#; Rust: gdext 0.x with announced breaking changes, no shipped Steam game found, a macOS hot-reload crash still open). Rejected: StyleCop.Analyzers (last release 2023, beta, fights the formatter), NetArchTest (last release 2021), DefaultEcs (dead 2023), Arch's add-on packages (pinned to an alpha of an older Arch; depend on a library abandoned in 2018).

Generalisation: the five proofs are stack-neutral. Put them in the skill as the mandatory table every stack pick fills in, with dates of last release and a shipped-work citation.

#### B.2 Every language starts with the strictest tooling and scenario-first tests — T1

> "for every tech stack… set up proper pre-commit hooks, proper code linters and use the most advanced and most strict ones, introduce structure and describe how should we structure the code and layers, and if it's possible use linters for architecture structure… the strictest ways to make things work for the AI agents… I don't want to write like hundreds and thousands of unit tests. I want… a hero test or integration test or contract test… testable with some simple scenario… maybe in Gherkin or something alternative."

Rule: before feature work, each language gets pre-commit hooks, the strictest linters and analyzers with warnings as errors, a written code-structure and layer rulebook, and architecture rules enforced by a tool where one exists. Tests are scenario-first: behaviour scenarios as text, integration and contract tests at the boundaries, few unit tests. Logic is tested headless, apart from visuals.

Why: the owner's stated purpose is to make things work *for AI agents*. Strictness is the substitute for a reviewer who remembers the rules.

Generalisation: fully general. Section 6 is the test strategy; section 5 is the per-stack checklist.

#### B.3 Simplicity, little code and strict patterns before optimisation — T1

> "I care more about simplicity, about having little code size and having strict and complete and good architectural patterns and design patterns which by the class itself would not make it possible to do something that's not idiomatic… optimization will come later."

And on save size, same round: "save size, I would say I don't care about save size for now… even if it will be very gigabyte of data… we'll optimize things much later."

Rule: prefer the simpler design and less code unless a measurement shows it fails. Patterns are strict and complete: types and class design make the non-idiomatic thing impossible, not merely discouraged. Optimisation (storage, caching, data layout) waits for a measurement that asks for it.

First application: research proposed compacting the life record (merging old repeats into runs, cold storage) and a build test on memory's share of the save; the owner refused both until a seeded long run measures the size. Compaction was parked as an option with a named trigger ("revisited when saves are measured too large").

Generalisation: fully general. The skill's rule: an optimisation needs a measurement attached to its bead; a proposal without one is parked with a trigger.

#### B.4 Patterns from day one; DI at one composition root; a hard presentation line — T1

> "all right, feel free to run those spikes. But I disagree on the DI. I think the DI early will help us interconnect many things… any software engineer in .NET would tell that DI has to be used… we need some advanced design pattern to be used for behavior… the line drawn between presentation layer and data layer should be clear."

Earlier: "I don't mind complexity in terms of number of architectural patterns… what matters is that if we [don't] use architectural patterns straight away then we'll have a lot of chaos."

This overrode the session's proposal of "no DI container in the simulation" (the session had argued a container was unnecessary for a few hundred objects). Lesson: the owner's criterion was *chaos after features stack up*, not object count; the session had optimised for the wrong criterion.

Rule (the accepted simulation architecture; items marked [game-specific] have their general form in section 7):
- ECS for simulation state; one code system per design system [game-specific; general form: one module per domain area].
- The world changes only through commands; every change emits an event.
- One deterministic step: world + commands + seed → world + events; banned APIs make non-determinism a build error.
- Ports and adapters: content, random numbers, clock, saves and presentation plug in from outside.
- Dependency injection with the platform's standard container at one composition root; system order stays an explicit literal array, never registration order.
- Architecture tests enforce the design's own dependency list.
- Saves hold data; formatters render sentences.
- The view reads snapshots and events and sends commands, nothing else.
- Refused for now: full event sourcing, threads or a job system inside the step, networking and rollback.

#### B.5 Run in one process first, behind the boundary the split will use — T1

> "for now, I wouldn't mind if we won't have the dedicated server. What if we will have the game and implement logic inside the game? And later on, we will decompose the logic into client server… more than totally acceptable for the first version… we don't want to make all the logic tied to visuals too much so that it would be really hard to test the logic… we should decompose layers for sure and game logic behaviors all should be testable."

Rule: first version is one process; the logic is an engine-free library reached only through commands in and snapshots/events out, the same boundary a server will have; all logic runs and is tested headless.

Consequence that mattered: the "server language" question became the "library language" question and was answered by the client's language (C#), because one language, one toolchain and no interop layer won on the five proofs. The earlier preference for Rust (T1, 2026-10-09: "Rust would be perfect but I wouldn't mind if you use the same programming language for both client and server") was superseded one day later (T1: "C sharp, yeah, inside Godot. Fine.").

Generalisation: fully general. Defer the process split, never the boundary.

#### B.6 Same-platform determinism required; cross-platform may differ if nothing breaks, and every difference is logged — T1

> "I wouldn't mind if we research how to make those consistent, but without sacrificing performance… in worst case scenario, if it runs slightly differently, but it won't break the game, I don't mind… if they'll transition to Windows and it will not break it will continue to work correctly although slightly differently that's fine… but we need to document that difference as a catch… platform specific catches… retain that memory in a project code base."

Rule: required: same seed and commands give the same events on the same platform (replay and save/load tests). Preferred: same results across platforms when it costs no meaningful performance. Allowed: small differences that break nothing; a save moved between platforms keeps working. Every known difference goes in a `platform-catches` runbook with the entry shape: *what differs · where (platform, version) · effect · how it was found · mitigation*.

What this reversed: the stack research had banned `Math.Pow/Exp/Log/Sin/Cos` outright in the simulation. The owner lifted the blanket ban; the implementation then routed all platform maths through one port (`Sim.Maths`) with a second banned-symbols list that only that project omits, so the boundary stays enforced without a per-file pragma (section 5.3).

Evidence the catches file earns its keep (entries written in one day): float maths may round differently on Apple silicon vs x64 (three backends measured: system maths 9–14 ns pow; lookup table 23 ns, believed cross-platform exact; Q32.32 fixed point 215 ns, exact by construction); Godot on Metal reports no GPU frame times; a windowed Godot run on macOS locks to 120 Hz; `lefthook install` refuses or replaces an existing hook when `core.hooksPath` is set; the Godot app bundle path differs per platform; `dotnet test` under Microsoft Testing Platform finds zero tests without one property.

Generalisation: fully general. Decide the determinism contract explicitly (what must match, what may differ, how it is tested) before code, and keep a platform-catches log from the first spike.

#### B.7 Saves store structured records; sentences are rendered — T1

> "we're not writing strings as a prose in a save file. We write JSON and then we interpret it programmatically … to display it to a player as a list of sentences"; "crucial for us to keep it in JSON representation internally… sentences is only the way to show it to a… player and to me, for debugging."

Rule: every stored thing is a record with a type id, a date where it applies, and fields that reference entities by stable id. Words are rendered from the record by a template per type, for the user and for debugging; the same record may be rendered differently later without changing the save. A requirement that says a system "writes a sentence" means it stores a record rendered as that sentence.

Generalisation: fully general for any persisted log, notice, audit trail or explanation. Store facts, render prose.

#### B.8 Builds on the owner's machines, no CI — T1

> "we don't need to run build game in the CI… I'll use my macOS and my Windows PC to build"

Consequence for tooling: the local gate must be fast and one word, with no machine-specific step inside it; machine-specific checks (the engine import) get their own command with an overridable path.

Generalisation: when there is no CI, the pre-commit hook *is* CI. It must call the same recipes as the gate so the two cannot drift.

#### B.9 Code in a private repository; the tracker syncs through it — T3

The owner created a private GitHub repository under his organisation and pushed; beads sync through it. Earlier the project had no remote, and the tracker warned on every write. Lesson: create the remote on day one even for a solo project; a tracker and a backup both need it.

#### B.10 The ECS verdict, reversed by the owner's criterion — T3 (Friflo), T1 (the criterion)

Sequence, because the sequence is the lesson:
1. Stack research (agent, one pass): "ECS: ❌ for now. A few hundred characters is a tiny load… use plain typed collections… revisit after profiling." Criterion used: performance need.
2. Owner (B.3 and B.4 quotes): simplicity and *strict patterns that make the non-idiomatic impossible*; "feel free to run those spikes". Criterion: structure, not speed. He explicitly reopened the ECS question and refused to let the research's verdict ride into the C# decision (the C# decision's own text records: "The research's ECS verdict is **not** part of this decision; the owner reopened it and decides it separately" — decision wording, not owner speech).
3. Spike (two libraries built side by side, 200 characters, 2000 ticks, same event-log hash across both): Friflo wins because it has the shapes the domain needs built in (links, reverse lookup, relations, value indexes); Arch has none of them in its core and its add-ons are dead; plain collections pass every test but the owner's criterion rules them out while an ECS works.
4. Owner accepts Friflo with three conditions (section 7.3).

Generalisation: **state the criterion before the verdict.** A research README must name the criterion it judged by, in its Findings, so the owner can swap the criterion without the agent having to redo the work.

#### B.11 Behaviour architecture — mostly T2 ("yes to the rest of the questions"); tier per bullet

These are [game-specific] in content; the general forms are in section 7.1.
- T2: Characters decide only on named events (action end, interrupt band crossed, reaction arrives, order queued, booked timer due), never by re-scoring every tick. One ordered wake-up queue keyed by (tick, stable id, sequence) books every future moment; a stable id is the saved id, never an ECS entity index.
- T2: No immediate ECS callbacks; systems write events into buffers drained at phase end in a fixed order, sorted by (tick, phase, stable id, sequence). Change filters for queries are allowed.
- T3: No per-object polling; an object with no stamp and no booking costs nothing per tick, as a tested invariant. Hazards follow the trap shape (detect, disarm, failed repair can fire it, one-shot vs resetting).
- T2 for fixed ticks and "speed is ticks per real second" (the research's question 1); T3 for the catch-up cap, the speed control showing the real speed reached, and the step on its own thread, single-threaded inside.
- T2 (owner also said, T1: "if it is the same split as in Unreal… something which modern engines suggest to use… I like this idea"): Utility chooses the action; each action runs as a small event-driven state graph; forks are scored by the same scorer; behaviour trees, GOAP and HTN are refused as decider and as library.
- T2: A performance spike runs before the first feature stage; the research's estimate (20 µs per decision) is replaced by the measurement.

The 2002 evidence behind "no polling": Neverwinter Nights ran a heartbeat script every 6 s on every object, area and module. An idle server climbed to 100% CPU from cheap scripts × count; a heartbeat that re-issued an action each cycle reset a 6-second animation forever (the dithering of re-deciding every tick). The engine's own advice was "use other types of event scripts when possible" and clear the script field. The project's cost table: re-decide every tick = 4 ms per tick (72% of a core at 3x, unbounded in the sleep skip); on events ≈ 0.01 ms average.

---

## 5. Phase C and D: spike, then bootstrap

### 5.1 Spikes (Phase C)

A spike is throwaway, answers named questions, runs on the target machine where the claim is about the machine, and ends in a written verdict with conditions. Run one when: the claim is a number (performance, size); two sources disagree; the tool is new to the agent; the cost of being wrong is a rewrite.

The project's spikes and what each caught:
- **Engine on Mac** (Godot 4.7.2 Metal, M3 Max): MetalFX spatial is free; temporal upscalers cost more than they save on a light scene; GPU timers return zero on Metal; windowed runs lock at 120 Hz; first launch spends 15 s compiling shaders (confirmed a warm-up screen requirement); headless C# runs a 1,000-agent × 10,000-tick loop in 115 ms (confirmed headless tests are viable). Extrapolation to the floor machine was marked as extrapolation.
- **ECS** (Friflo vs Arch): the same event-log hash across 5 processes, 3 maths backends, 2 runtime versions and both libraries; save at tick 500 → load → next 100 ticks equals the uninterrupted run; **Friflo's own serializer silently lost one of two relation types on load with `error=none`, and read a record-struct field back as default**. Both variants built clean and passed every in-memory test; **only the save/load hash test caught it**. Two probe programs were needed to isolate the bugs.
- **Mutation check of the scenario runner**: changing an expected tick (445→446), a score, or a direction made all four scenario cases fail. A test never seen red is a hypothesis.

Spike hygiene that paid off: its own `Directory.Build.props` stubs so root strictness does not leak into throwaway code; a CLI with `hash | saveload | bench | all | dump` so the Windows run is one command the owner can paste; results pasted into the README with hashes so another machine can diff.

### 5.2 The bootstrap plan (Phase D), .NET/Godot worked example

Written by a consulting agent before the bootstrap started, as a tree with one line per file saying why it exists:

```
lifesim.slnx                     one solution; `dotnet build` builds everything incl. the Godot view
global.json                      pins .NET SDK 10.0.301 and msbuild-sdk Godot.NET.Sdk 4.7.2
Directory.Build.props            strict settings for every project
Directory.Packages.props         central package versions; a csproj never carries a Version
.editorconfig                    rule severities + scoped suppressions, each with a reason
BannedSymbols.Determinism.txt    all Sim.*: Random, clocks, threads, unordered collections, hash seeds
BannedSymbols.PlatformMaths.txt  all Sim.* except Sim.Maths: Math.Pow/Exp/Log/Sin/Cos
BannedSymbols.HostIo.txt         all Sim.* except Sim.Composition: System.IO
justfile                         the task runner: `just check` is the repo-wide gate
lefthook.yml                     pre-commit calls `just` recipes, never its own command lines
.config/dotnet-tools.json        CSharpier as a local dotnet tool
src/
  Sim.Core/        ECS world, commands, events, snapshots, tick pipeline, RNG; Modules/<Name>/ per design system
  Sim.Maths/       the one place platform maths is allowed; ISimMaths port + SystemMaths adapter
  Sim.Content/     loads a pack from an IContentSource (no IO), validates against content/schema, types it
  Sim.Composition/ the one DI composition root; filesystem adapter; system order as a literal array
  Game.Godot/      Godot .NET project; thin view: snapshots/events in, commands out
tests/
  scenarios/*.yaml       scenario files (design sentence, seed, commands, expectations)
  Sim.Scenarios/         xUnit v3 theory over the YAML + golden event log + replay hash + save/load
  Sim.Architecture/      ArchUnitNET: module deps follow design `depends_on`; no engine in Sim.*
  Sim.Properties/        CsCheck: random command sequences keep invariants; save→load→save byte-identical
design/runbooks/code-structure.md   layers, allowed dependencies, where things go, how to add a system
src/AGENTS.md, tests/AGENTS.md      ten-line per-folder guidance (CLAUDE.md symlinks), pointing at the runbook
```

Strict settings (`Directory.Build.props`): `net10.0`, `LangVersion 14`, nullable on and as errors, `TreatWarningsAsErrors`, `AnalysisLevel latest-all`, `EnforceCodeStyleInBuild`, `GenerateDocumentationFile` (CS1591 off: "doc comments are for intent, not a tax"), `Deterministic`, central package management; analyzers for every project: built-in CA, Meziantou, Roslynator, SonarAnalyzer, BannedApiAnalyzers; an MSBuild target that fails the build if any `Sim.*` project resolves `GodotSharp`. A csproj sets only what it *is* (`IsSimProject`, `IsTestProject`, `AllowPlatformMaths`, `AllowHostIo`) and its references.

Gate: `just check` = CSharpier check → `dotnet build -warnaserror` → all tests → content validator (→ design lint, proposed). `lefthook.yml` runs `just fmt-check`, `just build`, `just test-fast`, `just content` with globs. `just godot-import` is separate (needs the app bundle; `GODOT` env var overrides the Mac default path).

The vertical thread (the only "feature" in the bootstrap): `AddCharacter(id, levels)` and `AdvanceTime(minutes)` commands → a Time module sets elapsed minutes → a Needs module lowers each need by `decay × minutes / 60` where `decay` comes from `content/needs/<id>.yaml` → `NeedChanged` events → canonical event lines → SHA-256 log hash → snapshot for the view → save/load through the project's own record adapter. One YAML scenario, one golden log, one architecture test, one property test, one Godot scene that steps the sim and prints events.

Scenario file shape (what a design requirement becomes):

```yaml
# needs.R1 — Needs decay over game time only (design/systems/needs.md).
text: >
  GIVEN a character's hunger at some level, WHEN five game hours pass, THEN hunger has fallen by
  five hours of its decay; WHEN a step passes with no time advance (paused), THEN hunger is unchanged.
seed: 7
commands:
  - { step: 1, add_character: { id: 1, needs: { hunger: 100, bladder: 100 } } }
  - { step: 2, advance_time: 300 }
  - { step: 4, advance_time: 60 }
run_for: 4
expect:
  - { need_changed: { step: 2, character: 1, need: hunger, from: 100, to: 95 } }
  - { final: { character: 1, need: hunger, level: 94 } }
  - { rejected: 0 }
```

The runner knows commands and expectation kinds, nothing about rules; it is extended only for a new command or expectation kind. The golden log is a text file of canonical event lines plus a hash; a diff writes `*.received.txt`, which is read and then accepted with `GOLDEN_ACCEPT=1 just test`. "Never accept a hash change you cannot explain."

### 5.3 Where the bootstrap improved on the research (each a reusable rule)

| Rule | Why |
|---|---|
| One task runner; hooks call its recipes, never their own command lines | the research put raw commands in the hook file; then the hook and `check` drift |
| One SDK pin file and one central package-version file | an upgrade is one diff |
| Two banned-symbol lists instead of a `#pragma` in one adapter | a pragma is a per-file exception an agent can copy; a second list that one project simply does not include needs no exception anywhere |
| No file IO in the content loader either; the filesystem adapter sits in the composition project | one ban list for every library project; content tests need no disk |
| Each gate is made red once on purpose (a banned call in the core, an illegal module reference, a wrong scenario number) and then green | a gate never seen red is a hypothesis |
| The architecture test parses the design vault's `depends_on` frontmatter | a design dependency change is a failing test, not a stale comment |
| The engine import stays out of `just check` | it needs the app bundle and a platform path; the default gate has no machine-specific step |
| Every suppression in one config file, path-scoped, with a one-line reason; never a pragma | suppressions are visible and reviewable in one place |
| Per-folder ten-line `AGENTS.md` with a `CLAUDE.md` symlink, pointing at one rulebook | agents read the folder they are in; the rulebook is the one place rules live |

Risks the plan named in advance (good practice: name them before starting): whether the engine's editor build accepts the new solution format and language version; hook chaining with an existing tracker hook (checked in a scratch repo first); three analyzers never run in the spike, expect a round of suppressions; the ECS relation API with a struct key is new; the golden-log tool's first run writes a received file that must be accepted by hand once.

### 5.4 Deriving the checklist for any stack (role table)

The research already wrote a second worked example for Rust. The skill should carry a role table and fill the third column per stack:

| Concern | .NET (used) | Rust (researched) | For stack X, find… |
|---|---|---|---|
| SDK/toolchain pin | `global.json` | `rust-toolchain.toml` [agent judgement; not in the research] | one file that pins the compiler and the engine SDK |
| Central dependency versions | `Directory.Packages.props` | workspace-level dependency table [agent judgement; not in the research] | one file; a package file never carries its own version |
| Formatter | CSharpier (`check` in hooks) | rustfmt with committed config | one opinionated formatter; disable layout lint rules that fight it |
| Strictest analyzers, warnings as errors | `AnalysisLevel latest-all`, nullable as errors, Meziantou, Roslynator, Sonar | `clippy::pedantic`, cherry-picked `restriction`/`nursery`, `-D warnings` | the strictest sets with a current release date; reject stalled ones |
| Banned-API mechanism | `BannedSymbols.*.txt` via BannedApiAnalyzers (RS0030 as error), applied per project | `clippy.toml` `disallowed-methods`/`disallowed-types` | a machine check that fails the build on a named symbol |
| Layer enforcement | project references; MSBuild target forbidding the engine assembly; ArchUnitNET inside an assembly | crate boundaries; `cargo-deny` `[bans]` with `wrappers` so only one crate may depend on the engine | first the build system's own boundaries, then an architecture-test library |
| Pre-commit | lefthook (cross-language, current) | lefthook | one hook runner that calls the task runner |
| Task runner and one-word gate | `just check` | `just check` | the same |
| Scenario tests | YAML files + one xUnit v3 theory + JSON Schema for the YAML | YAML + one integration test | one runner over text scenarios; Gherkin only if scenarios are not statistical |
| Golden logs | Verify (refused for now: sponsorship check fails the build) → a 30-line hand-rolled helper | insta | any tool that diffs a stored log; or a hand-rolled helper |
| Property tests | CsCheck (FsCheck alternative) | proptest | one shrinking property tester at the command boundary |
| Determinism bans | `System.Random`, clocks, `Stopwatch`, `Environment`, threading, `Dictionary`/`HashSet`, `GetHashCode`, `HashCode` | `HashMap`/`HashSet`, `Instant`/`SystemTime`, `thread_rng`, `f64::sin/exp/powf` | whatever the language's unordered, clock, random and platform-maths APIs are |
| Headless test host | `dotnet test` without the engine; engine `--headless` for view tests only | `cargo test` on the core crate | logic tests never need the engine binary |
| Unused dependencies | — | cargo-machete | a tool if one exists |

Derivation method for a new stack:
1. Fill the five proofs (B.1) for each candidate tool, with release dates from the package registry on the day.
2. Fill the role table; a blank cell is a risk to log, not a reason to skip.
3. Write the banned list for the language's own non-determinism sources (the list above is a checklist of *categories*).
4. Write the layer table (project/package → may reference → enforced by).
5. Build the vertical thread; make each gate red once.
6. Record every surprise in platform-catches and every deviation from the research with its reason.

### 5.5 State file and phase discipline (from the paused bootstrap agent, T4)

- A checked-in state file (e.g. `bootstrap.yaml`) listing each step with status (todo, doing, done, blocked on a human), its output path and its exit command. It survives context loss and shows what is done and what is not.
- A phase ends only when its check passes or the owner rules on it.
- Resume rule: read the state file first, report what is done and what is next in three lines, then continue.
- A "not done" vocabulary that cannot be mistaken for done: untested, blocked on owner, failed, deferred with a named trigger.
- Commit only when asked; never commit files an agent is still writing (the project took one commit while agents were still editing).
- Parallel agents get disjoint files; after a batch, one agent cross-checks for overlaps, duplicate terms and broken links.
- Update the project's top-level instructions the same day the stack changes; stale stack lines mislead every later agent.

### 5.6 Phase E: build, one system at a time (from the code-structure runbook)

Steps for every new module after the vertical thread:
1. Read the design system; implement only requirements with `status: accepted`.
2. Create the module folder with its commands, events, components and one system class implementing the step interface. One type per file.
3. Add the module to the architecture test's module→design-system map (the map must be complete or the test fails).
4. Register the system at the composition root and place it in the pipeline array where the design's order needs it.
5. Write the scenario first (`tests/scenarios/<requirement>.yaml`, requirement id in the comment). Extend the runner only for a new command or expectation kind.
6. If content is involved: schema, example file, loader typing, content record.
7. Run the gate. Every red is fixed, not suppressed; a suppression needs a path-scoped reason in the one config file.

Gate per module: its scenario green; the golden log accepted only after reading the diff; the architecture test passes; replay hash and save/load round trip unchanged for other modules.

Artefacts: the module, its scenario file(s), a golden log if the scenario is long, a content schema if new content, a row in the module map, and a bead closed with branch and commit metadata. A platform difference found on the way goes in platform-catches; a deviation from the runbook goes in the runbook's "Deviations, with reasons" section.

Rule when the runbook and the architecture test disagree: the test is right and the runbook is fixed.

---

## 6. Test strategy

Owner's criterion (B.2): scenario-first, few unit tests, headless. The smallest set the project settled on:

| Layer | What | Catches |
|---|---|---|
| 1. Scenarios | One text file per design scenario: the design sentence (for tracing), seed(s), a tick-stamped command log, run length, expectations over the event log and final snapshot (including sweep statistics: share, distinct count, "never"). One runner, one case per file and seed. Schema-validated. | behaviour against requirements |
| 2. Golden replay | For a few long scenarios the event log or its hash is stored. Same seed twice → same hash. Adding an entity leaves other entities' first N decisions unchanged. Per platform. | hidden non-determinism, unintended drift |
| 3. Contract properties | Any generated valid command sequence never throws and keeps invariants; an invalid command is rejected with an error event and changes nothing; save → load → save is byte-identical; save → load → run on equals the uninterrupted run (by hash). | boundary bugs, silent save loss |
| 4. Architecture | Layer rules from project references, banned APIs and an architecture-test library that reads the design's dependency list. | layer erosion by agents |
| 5. View | A scene loads; a snapshot maps to nodes. Few. | wiring only |

Unit tests only for pure maths and RNG.

Why YAML and not Gherkin (the owner asked for "Gherkin or something alternative"; the agent chose the alternative and the owner accepted, T2): the design's scenarios assert distributions over seed sweeps and refer to knobs by name; Gherkin would need regex step bindings that parse numbers and knob names, a growing glue layer. YAML scenarios have the same shape as the save and command log, so a failed scenario turns into a replay directly. Generating `.feature` files from the YAML `text` fields is a one-step conversion if readable living documentation is wanted later.

Rules:
- Write the scenario before the code; quote the requirement id in it.
- Tests build the system through the real composition root, never by constructing internals.
- Seed-sweep size and statistical tolerances are knobs in config, not test code.
- Nothing that only reads (inspector, hover text, UI) may ever draw a random number, or a replay diverges when someone looks.
- **Round-trip tests early.** The ECS spike's serializer loss was invisible to every in-memory test; only save → load → run-on → compare hashes caught it. Put that test in the vertical thread, before any feature.
- Mutation-check the runner: change an expected value and watch every dependent case fail.
- A seeded "stall detector" sweep for event-driven systems: a forgotten event makes an entity stall, not crash [game-specific; general form: for any event-driven design, test liveness under a seeded sweep].

---

## 7. Architecture rules and their enforcement

### 7.1 General rules (apply to any system with a core logic library and a shell)

| Rule | Enforced by |
|---|---|
| The core is shell-free: no engine/UI/framework types inside it | build-system reference rules; a build target that fails on the forbidden assembly; a banned namespace |
| Commands in; events and snapshots out; the shell never touches internal state | the shell holds only an interface; architecture test |
| One deterministic step: state + commands + seed → state + events | banned APIs for randomness, clocks, threads, unordered collections, hash seeds, machine state |
| Ports and adapters for content, randomness, clock, maths, IO, saves, presentation; adapters only at the host edge | per-project banned lists that the adapter project omits; project references |
| DI at one composition root; execution order an explicit literal, never registration order | the root is the only place that builds the system; tests go through it |
| One module per domain area; a module may use another only if the design says so | an architecture test that parses the design's own `depends_on` list; a module map that must be complete |
| Modules never call each other; they read this step's events and write their own | architecture test; event-buffer API |
| Stable ids in saves and in any ordering key; never runtime handles or indices | save adapter writes ids; round-trip test; an ordering key of (tick, stable id, sequence) |
| Before order-dependent work (event log, float sums, random draws), walk a sorted list, never a raw query | code rule in the runbook; per-system stable sort at system end; replay hash catches violations |
| Saves are the project's own records, never the library's serializer | a save adapter; the round-trip hash test |
| Numbers come from content or the command; a literal in logic is a bug unless it is a unit conversion | review rule; content validator |
| Behaviour lives in code; data names a rule and passes parameters; data never carries scripts or expressions | content schema with `additionalProperties: false`; a closed rule vocabulary checked at load |
| Event-driven by default; a timed clock only for what must move continuously; nothing polls | cost tables from research; a tested "no booking, no cost" invariant |
| No immediate callbacks on state change; events go to buffers drained at phase end in a fixed order | code rule; replay hash |
| Every suppression is path-scoped in one config file with a reason; no pragmas | review; grep |

### 7.2 Game-specific rules with their general form

| Game-specific | General form |
|---|---|
| ECS with components as public-field structs, one system per design system | any store; one module per domain area; data and logic separated |
| Utility AI chooses; per-action state graph runs; same scorer at forks; no BT/GOAP/HTN | one chooser; execution as small explicit state machines advanced only by named events; no second decider |
| Wake-up queue keyed (tick, stable id, seq) books every future moment | a priority queue of future work keyed by a total order on stable ids |
| Fixed tick length; speed = ticks per real second; catch-up cap; step on its own thread, single-threaded inside | a fixed logical step whose meaning never depends on wall time; the host decides cadence |
| Trap-shaped hazards; "no stamp, no booking, no cost" | event sources register once; idle objects cost nothing; chance rolled once at the moment of use |
| Proximity grid with two triggers (cell change, stamp change) | spatial or topical indexing with explicit triggers instead of per-tick scans |
| Detail tiers (watched vs low-detail lots) | level-of-detail for simulation cost by attention |

### 7.3 The three conditions on the chosen ECS (T3, from the spike)

1. Never save with the library's own serializer; go through the project's adapter with stable ids, with a test that saves, loads, runs on and compares hashes.
2. Components hold public fields only; a key struct inside a component is a struct with fields, never a record struct (the serializer read record-struct fields back as default).
3. Sort before any order-dependent work that walks links, relations or query results (raw order differed between the two libraries; the sort is required, not optional).

Generalisation: adopt a library on *conditions* written in the decision, each tied to a test or a lint, not on trust.

---

## 8. Documentation ontology rules [unaccepted: research concluded, owner questions Q1–Q8 unanswered]

The lesson that produced this (anti-pattern 1): a technology named in many documents made a platform switch (browser/Babylon.js → desktop/Godot) touch dozens of files. A survey on 2026-10-10 counted **313 technology mentions outside research** in prose: 133 leaks, 129 belonging, 51 history. Four Babylon-era decisions were still `status: accepted` after the engine moved; two upscaler bindings were live at once; no decision bound the client engine at all (it was bound by a side-clause of the language decision). While the survey ran, another session rewrote the top-level agent file with a new stack sentence and wrote a runbook with 12 more mentions. "Without a rule and a lint, the next swap costs the same as the last."

The proposed ontology (present it as a proposal with this evidence):

- **Component**: one named, replaceable part of the build (entity store, upscaler, content format), owned by one tech system, as an *inline item* of that system (frontmatter list + body table), shaped like a requirement. No new file kind. Rejected: a `component` file kind (hundreds of tiny pages); glossary rows (cannot carry status or a decision link); one `stack.md` table (a second owner that drifts).
- **Binding**: the component's current implementation (a library, a language, a format, or `ours` = own code behind a port). Status: unbound / bound / retired. Ids `<system>.C<n>`, never reused.
- **Binding decision**: the one live decision that chose the binding; `about:` names the owning tech system; body carries `Binds: <id>`.
- **Where a technology may be named**: only in research; superseded decisions; parked/refused options; the platform-catches log; the Components table of a tech system; the Decision section of the decision a row cites; owner quotes under Provenance; the two tables of the code-structure runbook. Never in vision, pillars, glossary, player-facing systems, requirement text, skills, checklists, or the top-level agent files ("Stack: see the Components tables").
- **A technology swap touches four places**: a new binding decision; the old decision marked superseded; the component row; the code-map table cell. A lint proves nothing else needs to change.
- **Lint** (`check_design`): fails on a technology name outside allowed sites, a component without one live binding decision, a binding decision cited by zero or two rows, a superseded decision without both links, a decision or research without `about:`, a broken link, a package name in the code map that matches no binding. Runs in the gate and the hook once the migration reaches zero violations.
- **Code docs relate by pointer, not copy**: one runbook is the derived map (component → package); per-folder agent files are pointers; `docs/` holds how-to only.
- A fifth tech system `toolchain` (language toolchain, formatter, analyzers, task runner, pre-commit, scenario/architecture/property tests, content check) is proposed so tooling bindings have a home.

Generalisation: fully general for any multi-document project. Bind each replaceable technology in exactly one row and one decision; everything else names the component; lint it.

---

## 9. Decision recording rules (the project's conventions, T4 process rules in use)

- `design/` is the only record. Decisions, options, research, systems with requirements, glossary, runbooks. Never `CONTEXT.md`, `docs/adr/` or chat.
- Implement only requirements with `status: accepted`; never implement from an option. A requirement becomes accepted only through an owner decision.
- A requirement has an id (`<system>.R<n>`, never reused), a SHALL sentence naming its knob by path, and a GIVEN/WHEN/THEN scenario. Code and tests cite the id.
- Numbers live only in content or config; design files name the knob. Tuning numbers live on the thing they tune (`content/needs/hunger.yaml#decay`) or in one knob table per system (`content/<system>/knobs.yaml`) with type, default, range, unit, a sentence, and whether a preset may set it (T4).
- Content is YAML limited to what JSON can express, checked against JSON Schema with unknown fields as errors; data names a rule, never a script; example files carry `example: true` and placeholder numbers (T4).
- Frontmatter links are bare `kind/slug`; bodies use relative markdown links; every link must resolve.
- Research README: Findings first (verdicts with ✅/❌, each with the criterion), then evidence, then owner questions each worded so "yes" accepts it. Label evidence: `[provisional]` one source, `[unverified]` not checked today, `[design judgement]` reasoned, `[unsourced]`. Say "one pass, not cross-checked" when true.
- Work goes to the tracker (beads): `bd ready` for next work; a bead links its design doc (`--spec-id`); blocked-by-another-bead uses a dependency; shelved uses defer with a reason; blocked on a human uses status blocked plus a comment. Never invent a fake blocker. Supersede, never delete.
- Escalate to the owner when: a choice changes scope or a ranked principle; two owner decisions conflict; a spike contradicts a decision; anything leaves the machine (push, publish, accounts). Escalation is one question with a recommendation, never a menu.
- Ask the human only what is theirs: taste, scope, priority, risk appetite, money, anything outward-facing. Decide the rest and record it as a session decision the human can overrule.

---

## 10. Anti-patterns observed, with what fixed them

1. **Technology named everywhere; a platform switch touched dozens of files.** The browser → desktop move left 133 leaks and four dead-but-accepted decisions. Fix: the ontology in section 8 (components bound in one row and one decision; lint). General.
2. **An agent recorded the owner's questions as its own session decisions, and the gate failed.** Gate 1 review r2 asked six owner questions; only one got an owner answer; the session recorded four as `decided_by: session` files; r3's main finding was this process failure, and a session decision had also added scope, a revive cheat and a tuning number against accepted text. Fix: `decided_by: owner` only for an explicit answer; a session decision never cuts an accepted pillar's demand or adds scope; the gate checklist requires owner decisions by name. General: **never accept for the owner.**
3. **One agent pass treated as final.** Fix: blind re-audits and persona critiques in fresh contexts at every gate; "one pass, not cross-checked" stated in every research README; a second agent cross-checks anything a decision rests on. General.
4. **Research verdict judged by a criterion the owner did not hold.** ECS rejected on performance; owner's criterion was structure; adopted after a spike. Also DI: session said "unnecessary at this size"; owner said "chaos after features". Fix: state the criterion before the verdict; ask the owner for the criterion when it is taste or risk appetite. General.
5. **A library's serializer silently lost data; every in-memory test passed.** Fix: own save adapter with stable ids; save → load → run-on → hash test in the vertical thread; adopt on conditions tied to tests. General.
6. **Bit-exact cross-platform maths assumed, then traded against performance without a decision.** The research banned platform maths outright and assumed CI on both platforms (there is no CI). Fix: an explicit determinism contract (required / preferred / allowed), a maths port with a backend chosen at the composition root, and a platform-catches log from the first spike. General.
7. **Heartbeat/polling as the default scheduler.** NWN's production evidence; the project's own cost table. Fix: event-driven by default, wake-up queue, a tested "no booking, no cost" invariant, ticks only for motion. General for any simulation, scheduler or agent loop.
8. **Letting risky work run when the owner wanted a reusable skill first.** The bootstrap agent was paused mid-way with a failing test-discovery step, its state written to a checklist and a WIP branch, rather than pushed through. Fix: pause with a state file and a resume rule; the owner decides whether to continue or to extract the lesson first. General.
9. **Hooks with their own command lines drift from the gate.** Fix: hooks call the task runner's recipes.
10. **A per-file pragma as the sanctioned exception.** Agents copy it. Fix: a second banned list the adapter project omits.
11. **Stale top-level instructions after a stack change.** The agent file still said "Planned stack: TypeScript, Babylon.js" a day after the engine moved; the "no git remote" caveat outlived the remote. Fix: update entry-point files the same day; better, make them pointers (section 8).
12. **A decision overturned without sweeping its quotes.** Four renderer decisions stayed `accepted` after the engine decision; a rename (director → storyteller) also changed sentences where the word meant the player. Fix: supersede the same day; grep for the old term; the blind re-audit checks for it.
13. **Tracker setup surprises on a repo with no remote.** `bd init` made its own commit without the required trailer; auto-export is throttled to 60 s so a burst of creates looked lost; `lefthook install` would have replaced the tracker's hook. Fix: commit the tree before `bd init`; force export after bursts; append the hook call into the existing hook instead of installing a second one (`just hooks`). Tool-specific; the general rule is "run the onboarding in a scratch repo first and log friction".
14. **A commit taken while agents were still editing.** Fix: commit only when asked, after a parallel batch has been cross-checked.
15. **A prototype used as a reason for a design answer.** Fix: "the demo binds nothing" as an owner decision; candidate requirements re-derived from the design, not from what the prototype happens to do.

---

## 11. Open questions and the paused bootstrap

The bootstrap was paused on branch `wip/bootstrap` (94 files, 2,288 lines: the skeleton, the vertical thread, three test projects, runbook, per-folder agent files). It stopped while `dotnet test` found zero tests.

**The `dotnet test` lesson, recorded as open ("fix drafted, never seen green"):**
- Setup: .NET SDK 10.0.301, xunit.v3 4.0.2, `global.json` `"test": {"runner": "Microsoft.Testing.Platform"}`.
- Symptom: `dotnet test` exits 5 with "zero tests ran" and nothing names the cause.
- Two candidate causes/fixes are on the branch, neither verified passing: (a) `UseMicrosoftTestingPlatformRunner=true` in `tests/Directory.Build.props` (recorded in platform-catches as the fix); (b) a justfile note that passing `--nologo` to `dotnet test` under this runner is rejected as an unknown argument and also reports "zero tests ran" exit 5. The ECS spike had earlier found the VSTest path errors out on this SDK, which is why the platform runner was chosen.
- Generalisation: "a gate never seen red is a hypothesis" holds symmetrically: a fix never seen green is a hypothesis. The state file must say "drafted, unverified" for both, and a resuming agent must run the test and see it pass before closing the step.

Other open items (beads and research "not covered" lists):
- `lifesim-kg4`: performance spike at 200 characters, 3x speed, before the first feature stage (replaces the 20 µs estimate).
- `lifesim-me6`: agents working in Godot headlessly (the mac spike showed hand-written csproj + `dotnet build` works without the editor; not yet a workflow).
- `lifesim-4yo`, `lifesim-6rs`: character/animation pipeline; free colour and pattern per object part (renderer spikes).
- `lifesim-6lf`: the `content/time/knobs.yaml` table needs units the knob-table schema lacks (game seconds, ticks, milliseconds).
- `lifesim-e9x`: Verify sponsorship (the golden-log tool fails the build without a sponsorship property) or keep the hand-rolled helper.
- No decision binds the client engine (ontology Q2): one owner decision is needed that binds engine, upscaler and anti-aliasing and supersedes the four browser-era renderer decisions.
- `lifesim-sxh`: supersede the browser-era decisions after that engine decision (step 2 of the ontology migration).
- `lifesim-nrm`: seed-sweep harness for storyteller and autonomy.
- Windows run of the ECS spike pending: whether maths backend (a) differs across platforms; if so switch to (b).
- Whether Godot 4.7.2's editor build accepts `.slnx` and `net10.0` + `LangVersion 14` (fallback: a one-project `.sln` next to `project.godot`, or `net9.0`/13).
- The hook-chaining workaround (`just hooks` appends to the tracker's hook) is checked in a scratch repo, not yet in the real one.
- Ontology questions Q1–Q8 unanswered; the vault tool (a2kay) does not yet know the inline `components:` kind.
- Three analyzers (Meziantou, Roslynator, Sonar) never ran in the spike; the first real build will need a round of path-scoped suppressions.
- gdUnit4 view tests not set up; tests marked as needing the engine runtime are skipped silently when the binary lacks C# support, so any such skip must fail the gate.
- The shelf (shared Python micro-software) has no equivalent for a C# consumer; seams to revisit once code exists: seeded per-entity RNG streams, the client/server message protocol, a deterministic tick/event bus.

---

## 12. Reversal sequences (keep these as worked examples in the skill)

| Topic | Step 1 | Step 2 | Step 3 | Lesson |
|---|---|---|---|---|
| ECS | research ❌ on performance | owner: criterion is strict structure; "run those spikes" | spike ✅ Friflo with three conditions | state the criterion before the verdict |
| Platform maths | research: ban Pow/Exp/Log everywhere, CI on both OSes | owner: performance wins, log the catches | one maths port, a second banned list only the adapter omits | decide the determinism contract explicitly |
| DI container | session: none needed at this size | owner: "I disagree on the DI… chaos" | standard container at one composition root, explicit order | the owner's criterion was chaos, not size |
| Library language | 2026-10-09 owner: Rust preferred, same language acceptable | research: C# on the five proofs | 2026-10-10 owner: "C sharp… Fine." | a preference is not a decision until it meets the proofs |
| Scenario language | owner: "Gherkin or something alternative" | research: YAML, because scenarios are statistical and replay-shaped | owner accepted | take the owner's purpose, not the example tool |
| Save compaction | research: compact runs, budget test | owner: "I don't care about save size for now" | parked with trigger "when measured too large" | optimisation waits for a measurement |
| Client engine | browser + Babylon.js accepted | MetalFX required; native proof of concept | Godot proven by the Mac spike and used in code, but bound only by a side-clause of the language decision; no engine binding decision exists; four old decisions still accepted (leak) | supersede the same day; bind in one place |
| Behaviour layering | deep dive: per-action state graph "later" | layering research: a step list is a graph with no fork, one runner | owner: graphs from the first stage | a simpler unification can pull a "later" forward |

---

## 13. What you must produce

A reusable skill, in the shape the paused bootstrap agent asked for (its own words, items 43–47 of its checklist, plus the state-file item 32):

1. **A short entry file** with the phase list (discover → decide → spike → bootstrap → build), the gates, and the state-file format; **separate reference files per stack**; load only the stack in use. Include the .NET/Godot reference from section 5.2–5.3 as the first stack file and the Rust column of 5.4 as the second; the role table of 5.4 as the derivation template for any other.
2. **A fixed per-step template**: inputs, output path, exit command, who decides (owner / session), and the not-done vocabulary (untested, blocked on owner, failed, deferred with a named trigger; and "drafted, unverified" for fixes).
3. **A rule for resuming**: read the state file first, report done and next in three lines, then continue.
4. **The decision-recording rules** of section 4.A and 9, with the provenance tiers of section 1 and the template.
5. **The test strategy** of section 6 as a checklist with the round-trip test and the mutation check mandatory in the vertical thread.
6. **The architecture rules** of section 7.1 as a table with "enforced by" filled per stack; section 7.2 as a sidebar for simulations.
7. **The documentation ontology** of section 8 as a proposal file, with the lint spec, marked unaccepted by this owner until he answers; a generic version for projects without a vault.
8. **The gate-review method** of section 3.2 (lens audit, persona critique, blind re-audit, hash-pinned scope, "not assessed — no data") as a procedure any project can run.
9. **The anti-pattern list** of section 10 with what fixed each, and the reversal table of section 12 as worked examples.
10. **The owner's principles** of section 4.B, quoted, with tier tags, reasons, evidence, what was rejected and the generalisation, so a future agent can cite them without this prompt.

Constraints on your output: plain words; structure over prose; every rule carries its reason and its check; game-specific items marked and paired with their general form; unaccepted items marked; no diagrams in agent-facing files; no claim without its evidence class (verbatim / accepted / relayed / session / agent judgement).
