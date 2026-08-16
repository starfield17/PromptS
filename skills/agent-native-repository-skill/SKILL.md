---
name: agent-native-repository
description: Design and maintain agent-friendly software repositories with local context, explicit module boundaries, minimal abstraction, and mechanically enforced architecture rules.
---

# agent-native-repository

Use this skill when designing, creating, restructuring, or extending a software repository that will be maintained substantially by coding agents.

This is **not** an agent orchestration framework.

Do not use it to force planning rituals, brainstorming stages, subagent spawning, review ceremonies, or generic reasoning procedures. Frontier models should decide how to work.

The purpose of this skill is to shape the **repository environment** so an agent can make safe, local, verifiable changes without understanding the entire codebase.

## Core doctrine

Optimize for:

1. **Context locality** — one task should usually require one module or one vertical slice.
2. **Explicit boundaries** — modules expose contracts; internals stay internal.
3. **Low fan-out** — a small feature should not require touching many unrelated packages.
4. **Mechanical enforcement** — architecture rules should be executable whenever practical.
5. **Minimal abstraction** — create interfaces only at real variation points or hard boundaries.
6. **Proportional architecture** — architecture complexity must match actual problem complexity.
7. **Hierarchical context** — root instructions are a map; local instructions explain local rules.

Default bias:

> Modular boundaries + vertical slices + ports/adapters at real boundaries + DDD only where domain complexity warrants it + KISS everywhere.

Do not mechanically apply every pattern.

## 30-degree rule

Before adding a rule to the repository or to this skill, ask:

> If the next generation of coding models becomes twice as capable, does this rule still provide value?

Keep rules that encode information or enforcement the model cannot reliably infer, such as:

- repository-specific module contracts;
- allowed and forbidden dependencies;
- public versus internal APIs;
- project-specific extension points;
- architecture-test commands;
- generated scaffolds and templates;
- external tool integration;
- local invariants and conventions.

Avoid rules that merely tell a capable model how to think, such as:

- always write a plan first;
- always brainstorm alternatives;
- always spawn subagents;
- always perform a fixed review ritual;
- always decompose tasks using a prescribed template.

## Operating rule

**Model decides how to work. Repository defines what is allowed. Tests enforce the boundary. Skill supplies missing knowledge.**

## Architecture selection

Start from the simplest structure that preserves clear ownership.

### Small program

If the project is small and cohesive, prefer a simple structure over a framework:

```text
src/
  cli.py
  transform.py
  io.py
tests/
```

Do not introduce modules, ports, repositories, factories, or domain layers without a real need.

### Medium or growing application

Prefer capability-oriented modules:

```text
src/
  modules/
    training/
    autolabel/
    inference/
```

Each module may contain its own local layers if useful:

```text
training/
  api/
  domain/
  ports/
  adapters/
  tests/
```

Do not create global horizontal layers merely for symmetry.

### Complex domain

Use DDD concepts only when they model real complexity such as:

- invariants;
- state transitions;
- policies;
- domain terminology;
- aggregates with consistency boundaries;
- complex business rules.

Do not introduce DDD artifacts for simple orchestration or CRUD.

## Variation-point rule

Create a Port / Interface / Plugin when at least one of these is true:

- multiple implementations exist now;
- replacement is a stated near-term requirement;
- the dependency is external, unstable, hardware-specific, provider-specific, or difficult to test directly;
- the boundary protects the domain from infrastructure concerns.

Typical valid variation points:

- model backends;
- inference runtimes;
- storage engines;
- cloud APIs;
- hardware backends;
- message transports;
- external services.

Do not create speculative interfaces such as `ILogger`, `IClock`, `IPathProvider`, `IJsonSerializer`, or generic `Manager`/`Provider` abstractions unless they solve a concrete problem.

## Module boundary rule

Every significant module should have:

- a clear responsibility;
- a public API or contract;
- explicit allowed dependencies;
- explicit forbidden dependencies;
- tests close to the module;
- local instructions when the module is non-trivial.

Cross-module calls should target public contracts, never another module's internals.

Circular module dependencies are forbidden.

Prefer duplication over premature shared coupling when ownership is unclear.

Do not create dumping grounds such as `utils/`, `common/`, `helpers/`, or `misc/` for unrelated concepts.

## Mechanical enforcement

When practical, encode architecture policy as checks executable in CI.

Useful checks include:

- forbidden imports;
- dependency direction;
- dependency cycles;
- public/internal boundary violations;
- plugin contract conformance;
- type checks;
- local unit tests;
- integration contract tests.

Prefer an executable command such as:

```text
make architecture-test
```

over prose such as:

```text
Please remember not to import deploy internals from training.
```

Language-specific options are documented under `tooling/`.

## Hierarchical repository context

Root `AGENTS.md` should stay short and contain only repository-wide facts:

- repository map;
- module boundaries;
- global invariants;
- canonical commands;
- where local instructions live.

A non-trivial module may contain its own `AGENTS.md` with:

- responsibility;
- public API;
- internal structure;
- allowed dependencies;
- forbidden dependencies;
- invariants;
- extension points;
- test commands.

The nearest relevant instruction should carry the detail. Do not force an agent to load a giant repository manual.

## When modifying an existing repository

Do not force a rewrite into this architecture.

Preserve working structure unless a change materially improves locality, boundaries, verification, or maintainability.

Prefer incremental moves:

- isolate one capability;
- make one boundary explicit;
- add one architecture test;
- remove one speculative abstraction;
- introduce one local instruction file.

## Architecture review heuristics

Use these as optional checks, not a mandatory workflow:

- Could this change touch fewer modules?
- Did this introduce a new dependency direction?
- Did this expose internal implementation?
- Did this introduce an abstraction without a real variation point?
- Did a shared utility become a new coupling hub?
- Can the boundary be enforced automatically?
- Could another agent modify this area using only local context?
- Is there a simpler implementation with the same behavior?

## Reading map

Load references only when needed:

- `doctrine/architecture.md` — full architecture doctrine and trade-offs.
- `patterns/module-boundaries.md` — module ownership and dependency rules.
- `patterns/vertical-slice.md` — capability and feature slicing.
- `patterns/ports-adapters.md` — real variation points and adapter design.
- `patterns/ddd-lite.md` — when to use or avoid DDD concepts.
- `patterns/architecture-tests.md` — architecture-test design.
- `tooling/python.md` — Python enforcement options.
- `tooling/go.md` — Go enforcement options.
- `tooling/rust.md` — Rust enforcement options.
- `tooling/typescript.md` — TypeScript enforcement options.
- `templates/` — root/module AGENTS templates and architecture map.
- `checklists/` — optional project/review checklists.

## Final constraint

Do not turn this skill into an agent operating system.

If a proposed addition mainly instructs a frontier coding model how to reason, plan, delegate, or review, reject it unless it provides repository-specific information or an executable capability.
