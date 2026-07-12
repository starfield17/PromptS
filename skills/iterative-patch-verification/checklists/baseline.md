# Baseline Checklist

## Repository

- [ ] Archive extracts successfully.
- [ ] Current commit is recorded.
- [ ] Working-tree state is recorded.
- [ ] Untracked files are reviewed.
- [ ] Stale binaries and generated artifacts are identified.
- [ ] The package contains the commits claimed by the Local Agent.

## Tests

- [ ] Tests are run without relying on cache.
- [ ] Race, sanitizer, or concurrency checks are run.
- [ ] Static, type, lint, or vet checks are run.
- [ ] Sensitive packages are repeated when timing or concurrency matters.
- [ ] Test failures are separated from environment limitations.

## Requirements

- [ ] The architecture manual is read completely.
- [ ] The defect list is read completely.
- [ ] Requirements are mapped to code modules and artifacts.
- [ ] Current P0 and P1 findings are separated.
- [ ] The first patch cluster is selected by dependency order.
