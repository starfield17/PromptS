# P0 and P1 Classification

## P0

A finding is P0 when it can make the system claim a false fact, corrupt durable state, perform duplicate work, lose required work, or leave a required control path unreachable.

Examples:

- Recovery starts a second worker while the first may still be alive.
- Cancellation reports completion without process-tree proof.
- A terminal message revives after replay.
- A delivered instruction can be delivered again.
- A barrier accepts stale facts.
- A required warning decision has no accept path.
- A persistence failure is returned as success.
- A terminal run retains queued messages.
- A shipped binary does not match the reviewed source.

P0 blocks phase acceptance.

## P1

A finding is P1 when the critical semantics are safe, but the system is not yet ready for broad release or efficient operation.

Examples:

- A request blocks until a long-running session completes.
- Outcome reasons are unstructured strings.
- Summary output omits secondary information.
- Real external-harness contracts remain unverified.
- An API is ambiguous but current critical callers use safe specialized methods.
- Recovery is conservative but requires manual repair.

P1 should be completed before release when relevant, but it does not always block the target architecture phase.

## Escalation Rule

A reported limitation is P0 if it violates an invariant required by the current acceptance target. The word "limitation" does not lower severity.
