# Architecture Map

## Capability map

| Module | Owns | Public contract | Allowed deps | Forbidden deps |
|---|---|---|---|---|
| `<module>` | `<responsibility>` | `<api>` | `<deps>` | `<deps>` |

## Variation points

| Boundary | Contract | Implementations | Why abstraction exists |
|---|---|---|---|
| `<backend>` | `<interface>` | `<impls>` | `<real variation>` |

## Global invariants

- No circular module dependencies.
- Cross-module imports target public contracts only.
- Shared/core remains minimal.
- Architecture checks run in CI.
