# PRx: <Patch Name>

## Goal

This patch only addresses:

1. <confirmed problem>
2. <confirmed problem>
3. <confirmed problem>

Do not address:

- <excluded P1 item>
- <unrelated feature>
- <large refactor>

## Required Invariants

1. <invariant>
2. <invariant>
3. <invariant>

## Problem 1: <Name>

### Current Failure

Describe the current behavior and why it violates the architecture.

### Implementation Direction

Describe the correct model and expected state flow. Prefer architecture-level guidance over line-by-line code.

### Required Tests

- <test that fails before the fix>
- <recovery or persistence test>
- <concurrency or replay test>

## Problem 2: <Name>

Repeat the same structure.

## Cross-Module Requirements

- Reuse existing commit, journal, worker, router, process, or barrier abstractions.
- Do not create a second implementation of an existing subsystem.
- Propagate critical errors.
- Preserve compatibility unless the patch explicitly changes the contract.
- Keep state changes replayable.

## Completion Report

Report:

1. exact code locations,
2. the new state or lifecycle rules,
3. tests added,
4. validation results,
5. commit hash,
6. final working-tree status,
7. known limitations.

## Required Validation

```bash
<full tests without cache>
<race, sanitizer, or concurrency checks>
<lint, type, or static checks>
git diff --check
git status --short
```

The final working tree must be clean.
