# Repository Map

## Purpose

<one paragraph describing the repository>

## Architecture

This repository is organized by capability. Keep changes local to the owning module whenever possible.

### Modules

- `<module-a>` — <responsibility>
- `<module-b>` — <responsibility>
- `<core>` — <small set of truly shared stable concepts>

## Dependency policy

Allowed:

```text
<module-a> -> <core>
<module-b> -> <core>
```

Forbidden:

```text
<module-a> -> <module-b>/internal
<module-b> -> <module-a>/internal
```

No circular module dependencies.

## Public versus internal

Cross-module imports must use explicit public contracts. Do not import another module's internal implementation.

## Canonical checks

```text
<unit-test command>
<type/lint command>
<architecture-test command>
```

## Local instructions

Read the nearest module `AGENTS.md` before making non-trivial changes in that module.

## Design bias

Use the simplest implementation that preserves boundaries and correctness. Add abstractions only for real variation points or domain complexity.
