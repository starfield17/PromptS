# Architecture Doctrine

## Objective

The repository is optimized for **local, safe, verifiable change**.

The design target is not maximum abstraction, maximum purity, or maximum reuse. The design target is low cognitive and context cost for both humans and coding agents.

## Why locality matters

A feature that crosses global `controllers/`, `services/`, `repositories/`, `models/`, and `utils/` layers may be conceptually organized but operationally expensive for an agent. Every additional directory increases retrieval, dependency tracking, and omission risk.

Prefer capability ownership:

```text
modules/
  training/
  inference/
  datasets/
```

with local layering only when the module requires it.

## Architecture proportionality

Use the least architecture that preserves correctness and ownership.

### Level 0: straightforward program

Use functions, modules, and tests. Stop there if the code remains coherent.

### Level 1: capability modules

Introduce modules when distinct capabilities have distinct responsibilities, lifecycles, or dependencies.

### Level 2: explicit ports

Introduce ports when infrastructure varies or must be isolated.

### Level 3: domain model

Introduce DDD concepts only for meaningful domain rules.

### Level 4: multiple deployables

Split repositories or services only when deployment, scaling, security, organizational ownership, or release independence actually requires it.

Do not jump directly to Level 4 because the system might grow someday.

## Low fan-out

A change should have a small blast radius.

Good signs:

- one module owns the behavior;
- tests are adjacent;
- interfaces are narrow;
- configuration is local unless truly global;
- extension points are explicit.

Bad signs:

- one feature touches many unrelated global layers;
- shared utility modules accumulate domain logic;
- adding one backend requires editing a central switch in many files;
- unrelated modules import each other's internals;
- configuration objects know every subsystem.

## Explicit ownership

Every concept should have an owner.

If ownership is unclear, do not immediately promote the concept to `shared/`. First decide which capability is responsible for its lifecycle and semantics.

Shared code should represent a genuinely shared, stable concept—not merely code that appears twice.

## KISS before purity

Prefer a direct implementation when it is easier to understand and verify.

A small amount of duplication is often cheaper than a premature abstraction that couples unrelated modules.

## Agent-native documentation

Documentation should act as a map, not a textbook.

Root instructions answer:

- what exists;
- where to go;
- what must never be violated;
- how to run checks.

Local instructions answer:

- what this module owns;
- what is public;
- what is internal;
- how to extend it;
- how to verify it.

## Mechanical truth beats prose

If a rule matters, prefer expressing it in code, tooling, types, visibility, package layout, or CI.

Documentation explains intent. Tooling verifies reality.
