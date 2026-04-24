# Epic Specification

> Parent coordination file for multi-deliverable work. Use when one `TODO.csv`
> would otherwise carry phases, subprojects, or dependency chains.

## Goal

- <overall delivery goal>

## Non-Goals

- <what the epic does not cover>

## Constraints

- <tech stack requirements, e.g., must use Python 3.12+>
- <style requirements, e.g., follow existing linting config>
- <resource limits, e.g., no new external dependencies>

## Risk Assessment

- <external dependency risks, e.g., third-party API availability>
- <breaking change risks, e.g., database schema migration>
- <performance risks, e.g., large dataset processing>

## Child Deliverables

- <child task 1>
- <child task 2>

## Dependency Notes

- <child 2 depends on child 1>
- `depends_on` uses `;` as delimiter for multiple IDs (e.g., `1;2`)

## Child Task Types

- `single-compact`
- `single-full`
- `batch`

## Done-When

- [ ] Every row in `SUBTASKS.csv` is `DONE`
- [ ] Final epic validation passes

## Example Layout

```text
.codex-tasks/20260313-billing-epic/
├── EPIC.md
├── SUBTASKS.csv
├── PROGRESS.md
└── tasks/
    ├── 20260313-api/
    ├── 20260313-frontend/
    └── 20260313-docs/
```
