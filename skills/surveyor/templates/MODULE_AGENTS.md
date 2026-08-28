# <module>

<one line: the capability this module owns>

## Verify

```text
<test command scoped to this module>
```

## Public surface

Everything importable from outside this module:

```text
<file/package that defines the exports, and the names>
```

Anything not listed is internal and may change without notice. Callers that
reach past this surface are a bug in the caller.

## May depend on

- <module or package>

## Must not depend on

- <module or package> — <why; usually: it depends on us, and cycles are forbidden>

## Invariants

Things that must stay true, that reading the code will not tell you:

- <e.g. "IDs are assigned by the store, never by a caller">
- <e.g. "every write goes through `apply()`; direct field mutation breaks replay">

## Extension points

- <port/plugin contract, where implementations live, what a new one must satisfy>

---

Only create this file when a competent newcomer would get the module wrong
without it. A module whose code answers these questions does not need it.
