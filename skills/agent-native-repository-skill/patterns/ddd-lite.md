# DDD-lite

DDD is a tool for domain complexity, not a repository default.

## Use DDD concepts when they carry meaning

Good reasons:

- domain invariants must be protected;
- state transitions have rules;
- language matters to correctness;
- multiple operations must remain consistent together;
- policies are more important than persistence details.

Useful concepts may include:

- value objects;
- entities;
- aggregates;
- domain services;
- policies;
- domain events.

Use only the concepts the domain needs.

## Avoid ceremonial DDD

Do not create:

- repository interfaces for every data access function;
- factories for trivial constructors;
- aggregates with no invariant;
- domain services that merely call another function;
- domain events that only mirror function calls;
- command/query layers for simple local operations.

## Decision test

If removing a DDD artifact would make a real domain rule harder to express or protect, keep it.

If removing it only makes the directory tree less symmetrical, remove it.
