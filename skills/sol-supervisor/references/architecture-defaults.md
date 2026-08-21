# Optional architecture defaults

This reference is **not** part of the supervisor's core routing policy. Repository instructions and existing architecture take precedence.

Read it only for greenfield work or substantial redesign where the repository provides no stronger architectural direction and Sol has decided that an explicit default is useful.

Possible defaults:

- prefer a modular monolith before distributed decomposition unless scale/ownership constraints justify otherwise;
- organize around coherent vertical slices where that improves ownership and change locality;
- use ports/adapters at real variation or integration boundaries rather than mechanically everywhere;
- use DDD tactically only where domain complexity warrants it;
- favor KISS, explicit boundaries, low fan-out, and mechanically testable architectural constraints.

These are starting heuristics, not supervisor invariants. Sol owns unresolved architecture decisions.
