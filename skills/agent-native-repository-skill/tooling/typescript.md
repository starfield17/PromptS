# TypeScript Architecture Enforcement

## Useful mechanisms

- package/module boundaries;
- `exports` maps;
- ESLint restricted imports;
- dependency-cruiser or similar dependency rules;
- TypeScript project references for larger monorepos;
- interface/type contracts at real boundaries.

## Example restricted import rule

Conceptually:

```text
modules/training/**
  must not import
modules/deploy/internal/**
```

Prefer explicit package exports so internals are difficult to import accidentally.

## Monorepo caution

Do not create one package per tiny feature.

Use workspace/package boundaries when they represent meaningful ownership, build, release, or dependency boundaries.
