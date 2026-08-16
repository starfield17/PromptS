# Rust Architecture Enforcement

Rust's module system and crate boundaries are strong architecture tools.

## Use visibility deliberately

Prefer:

- private modules by default;
- `pub(crate)` for crate-local contracts;
- `pub` only for deliberate public API;
- workspace crates when a boundary deserves independent compilation/ownership.

Do not split into many crates merely to imitate microservices or layers.

## Dependency policy

Use Cargo workspace dependencies plus a dependency graph checker/script when strict edges matter.

A small workspace may look like:

```text
crates/
  core/
  training/
  inference/
```

Only introduce this split when the capabilities are large enough to benefit from independent crate boundaries.

## Traits

Use traits for genuine polymorphism or external boundaries.

Avoid trait-per-struct ceremony.
