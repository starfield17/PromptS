# <repository>

<one line: what this repository is>

## Commands

```text
<install>
<test>
<typecheck / lint>
<boundary check>          # the one that fails on a forbidden import
```

## Hard rules

Everything here is enforced by the boundary check. If you think one is wrong,
say so — do not work around it.

- Cross-module imports go through a module's public surface. Never its internals.
- No cycles between modules.
- <repo-specific rule> — enforced by <check name>

## Map

| Directory | Owns | Depends on |
|---|---|---|
| `modules/<a>` | <capability> | `core` |
| `modules/<b>` | <capability> | `core`, `modules/<a>` (public only) |
| `core` | <the small set of genuinely shared, stable concepts> | — |

Read the nearest `AGENTS.md` before a non-trivial change. Not every module has
one; absence means the module is small enough to read directly.

## Where things are that are not obvious from the map

- <the one directory whose name misleads>
- <generated code, and what regenerates it>
- <the seam a newcomer always gets wrong>

---

Keep this file to one screen. Anything that would be equally true in another
repository does not belong here.
