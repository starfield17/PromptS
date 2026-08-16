# Module Boundaries

## Goal

A module should be understandable and modifiable with minimal knowledge of the rest of the repository.

## Recommended shape

```text
modules/<capability>/
  AGENTS.md
  api/
  domain/        # only if useful
  ports/         # only if real boundaries exist
  adapters/      # infrastructure implementations
  internal/      # private implementation
  tests/
```

Do not create empty directories just to match the template.

## Public contract

A module should expose a deliberately small public surface.

Examples:

- exported package/module;
- facade;
- command/query contract;
- service interface;
- typed DTO/event contract.

Other modules must not import internal implementation paths.

## Dependency direction

Prefer a simple dependency DAG.

Example:

```text
training  ---> core
inference ---> core
autolabel ---> core
```

Forbidden:

```text
training ---> inference/internal
inference ---> training/internal
training <--> autolabel
```

## Shared/core discipline

`core` is a pressure vessel. Keep it small.

Promote code to shared/core only when:

1. at least two modules depend on the same stable concept;
2. neither module clearly owns it;
3. its semantics are genuinely identical;
4. moving it to shared reduces coupling instead of hiding coupling.

Never use shared/core as a convenience dump.

## Boundary violations to detect

- cross-imports into `/internal`;
- cyclic module imports;
- infrastructure imported by domain code;
- central registries that every feature edits;
- modules reaching into another module's database/storage details;
- direct imports of another module's adapter implementation.
