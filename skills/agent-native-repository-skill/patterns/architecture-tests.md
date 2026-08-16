# Architecture Tests

## Purpose

Architecture tests convert repository policy into executable guardrails.

They should fail early when an agent introduces a forbidden dependency or boundary violation.

## What to test

Prioritize high-value structural rules:

1. module dependency direction;
2. forbidden imports into internals;
3. dependency cycles;
4. domain-to-infrastructure violations;
5. plugin contract conformance;
6. package visibility conventions.

Avoid writing fragile tests that encode incidental file locations without architectural meaning.

## Characteristics

Architecture tests should be:

- fast;
- deterministic;
- easy to run locally;
- easy to interpret when failing;
- included in CI;
- expressed close to the actual repository model.

## Failure messages

Prefer:

```text
ARCHITECTURE VIOLATION:
modules.training may depend on core and model_api only.
Found forbidden import: modules.deploy.internal.runtime
```

over:

```text
assertion failed
```

The test should teach the next agent how to fix the violation.

## Layered enforcement

Use language features first when possible:

- Go `internal/`;
- Rust crate/module visibility;
- TypeScript package exports;
- Python package structure and import rules.

Use lint/static analysis for rules the language cannot express.

Use tests as the final safety net.
