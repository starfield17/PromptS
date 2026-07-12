# Stop Conditions

## Stop the P0 Patch Loop When

- All target requirements have concrete implementations.
- All confirmed P0 findings have permanent regression tests.
- Full tests pass without cache.
- Race, sanitizer, lint, type, and static checks pass.
- Critical adversarial scenarios pass.
- The current commit is present in the delivered package.
- The working tree is clean.
- No stale binary or test artifact remains.
- Remaining findings are P1.
- Further plausible attacks do not break a critical invariant.

## Do Not Stop When

- Only the Local Agent's report has been reviewed.
- Tests pass but no adversarial tests cover the changed invariant.
- The working tree contains uncommitted production fixes.
- A warning state asks for acceptance but no acceptance route exists.
- Recovery treats unknown state as proof of exit.
- Critical errors are logged but returned as success.
- A generic status predicate causes a critical caller to act on the wrong semantic category.

## Transition to P1 Hardening

Create a separate P1 plan for:

- non-blocking operation,
- structured reason codes,
- real external-system contracts,
- summary completeness,
- observability,
- performance,
- maintainability,
- and operational repair tooling.
