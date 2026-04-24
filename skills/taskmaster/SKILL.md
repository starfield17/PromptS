---
name: taskmaster
description: >
  Unified task execution protocol for Codex-only work. Supports Single Task,
  Epic Task, and Batch Task while preserving CSV truth-source, validation
  gates, context recovery, and Debug-First failure exposure.

  WHEN TO USE: user asks to "track tasks", "create todo list", "make a plan",
  "track progress", "long task", "big project", "build from scratch",
  "autonomous session", "跟踪任务", "自主执行", "长时任务", "从零开始",
  "任务管理", "做个计划", "大工程", or when a task clearly requires 3+
  ordered steps that produce file changes.

  DO NOT USE: single-step fixes, pure Q&A, code review, explaining code,
  search/research tasks, tasks with fewer than 3 steps, or tasks that do not
  produce file changes.
version: 5.0.0
---

# Taskmaster — v5 Task Protocol

## Purpose

Taskmaster is the default execution protocol for multi-step Codex work. v5
keeps the existing Debug-First core while expanding the skill into three task
shapes:

- **Single Task** — one deliverable, one shared context
- **Epic Task** — multiple child tasks with dependencies
- **Batch Task** — homogeneous row-level work executed through `spawn_agents_on_csv`

## Core Principles

1. The current truth artifact on disk wins over memory.
2. No step, subtask, or batch row becomes `DONE` without explicit validation.
3. Keep verbose reasoning in `PROGRESS.md`, `EPIC.md`, or batch output files, not in the chat.
4. Keep failures visible. Do not silently downgrade to manual or serial execution.
5. Keep planning CSVs and batch worker CSVs separate.
6. Build for Codex-only recovery: a cold restart must be resumable from files alone.

## Shape Router

| Shape | Use when | Truth artifacts | Example |
|---|---|---|---|
| **Single Task** | One deliverable with shared context | `TODO.csv` or `SPEC.md + TODO.csv + PROGRESS.md` | Fix one OAuth redirect bug |
| **Epic Task** | Multiple deliverables, modules, or dependency chains | `EPIC.md + SUBTASKS.csv + PROGRESS.md` | Ship billing dashboard across API, UI, docs |
| **Batch Task** | Same instruction template across independent rows | `TODO.csv + batch/BATCH.md + workers-input.csv + workers-output.csv` | Audit 80 Markdown files for frontmatter |

### Router Rules

- Start with **Single Task** when the user wants one deliverable and progress can stay in one shared context.
- Promote to **Epic Task** when one `TODO.csv` starts carrying phases, subprojects, or independent deliverables.
- Use **Batch Task** only when rows are independent, share one instruction template, and success can be expressed in structured output fields.
- An **Epic Task** can contain `single-compact`, `single-full`, or `batch` child tasks.
- A **Batch Task** must not be used for heterogeneous roles, cross-row dependencies, or shared write scopes.

## Single Task

Single Task preserves backward compatibility with the old LITE/FULL behavior by
supporting two execution profiles.

### Compact Single

Use Compact Single when the task is short, linear, and does not need recovery
logs or cached research artifacts.

- **Files**: project-root `TODO.csv` only
- **Template**: [compact_todo_template.csv](assets/compact_todo_template.csv)
- **Status set**: `TODO | IN_PROGRESS | DONE`
- **Best for**: short documentation edits, tiny cleanup passes, quick rename tasks

Compact Single example:

```csv
id,task,status,completed_at,notes
1,Locate root cause,IN_PROGRESS,,
2,Implement fix,TODO,,
3,Run verification,TODO,,
```

### Full Single

Use Full Single for all code changes, long-running tasks, or any work that must
survive a context reset. This is the default single-task path.

- **Files**: `.codex-tasks/<task-name>/SPEC.md`, `TODO.csv`, `PROGRESS.md`, `raw/`
- **Templates**:
  - [SPEC_TEMPLATE.md](assets/SPEC_TEMPLATE.md)
  - [PROGRESS_TEMPLATE.md](assets/PROGRESS_TEMPLATE.md)
  - [todo_template.csv](assets/todo_template.csv)
  - [perf_todo_template.csv](assets/perf_todo_template.csv)
- **Status set**: `TODO | IN_PROGRESS | DONE | FAILED`
- **Best for**: code implementation, bug fixes, refactors, multi-hour work

Full Single directory example:

```text
.codex-tasks/20260313-auth-fix/
├── SPEC.md
├── TODO.csv
├── PROGRESS.md
└── raw/
```

### Single Task Rules

- Re-read the active `TODO.csv` before every new step.
- Keep `TODO.csv` leaf-level only. Do not store phases, child projects, or batch rows there.
- Use `echo SKIP` only when validation cannot be automated, and record why.
- If retries hit 5, change strategy explicitly or promote the task shape.

## Epic Task

Epic Task is the parent coordination shape for large work that spans multiple
deliverables or dependency chains.

- **Files**:
  - `.codex-tasks/<epic-name>/EPIC.md`
  - `.codex-tasks/<epic-name>/SUBTASKS.csv`
  - `.codex-tasks/<epic-name>/PROGRESS.md`
  - `.codex-tasks/<epic-name>/tasks/<child-task>/...`
- **Templates**:
  - [EPIC_TEMPLATE.md](assets/EPIC_TEMPLATE.md)
  - [subtasks_template.csv](assets/subtasks_template.csv)
- **Status set**: `TODO | IN_PROGRESS | DONE | FAILED`
- **Best for**: multi-module features, staged refactors, long projects with clear child deliverables

Epic directory example:

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

Epic workflow:

1. Define the global goal and delivery boundary in `EPIC.md`.
2. Register child tasks in `SUBTASKS.csv` with `task_type`, dependencies, and `task_dir`.
   - `depends_on`: use `;` to list multiple dependency IDs (e.g., `1;2`). Empty means no dependency.
3. Execute each child task with its own Single or Batch protocol.
4. Bubble child validation back to `SUBTASKS.csv` and parent `PROGRESS.md`.
5. Close the Epic only when all child rows are `DONE` and the final validation passes.

Use Epic instead of a single `TODO.csv` when one task file starts reading like
project management instead of execution.

## Batch Task

Batch Task is for homogeneous row-level work that should be executed through
`spawn_agents_on_csv`. It can be a standalone task or a child inside an Epic.

- **Files**:
  - `.codex-tasks/<task-name>/SPEC.md`
  - `.codex-tasks/<task-name>/TODO.csv` for 3-5 high-level steps
  - `.codex-tasks/<task-name>/PROGRESS.md`
  - `.codex-tasks/<task-name>/batch/BATCH.md`
  - `.codex-tasks/<task-name>/batch/workers-input.csv`
  - `.codex-tasks/<task-name>/batch/workers-output.csv`
  - `.codex-tasks/<task-name>/raw/`
- **Templates**:
  - [BATCH_TEMPLATE.md](assets/BATCH_TEMPLATE.md)
  - [workers_input_template.csv](assets/workers_input_template.csv)
  - [workers_output_template.csv](assets/workers_output_template.csv)
- **Best for**: bulk file audits, bulk metadata updates, structured per-row analysis

Batch directory example:

```text
.codex-tasks/20260313-doc-audit/
├── SPEC.md
├── TODO.csv
├── PROGRESS.md
├── batch/
│   ├── BATCH.md
│   ├── workers-input.csv
│   └── workers-output.csv
└── raw/
```

### Batch Eligibility Checklist

Only use Batch Task when all of the following are true:

- One instruction template can describe every row.
- Rows are independent and can be retried independently.
- Output can be expressed as structured fields in `output_schema`.
- Writes are disjoint, or the batch is read-only.

### Batch Lifecycle

1. Identify a parent `TODO.csv` step that is truly row-level and homogeneous.
2. Create `batch/BATCH.md` and define:
   - instruction template
   - `id_column`
   - `output_schema`
   - `max_workers`
   - `max_runtime_seconds`
   - `output_csv_path`
3. Build `workers-input.csv` from real artifacts, not from plan steps.
4. Run `spawn_agents_on_csv` with explicit `id_column`, `output_schema`, `max_workers`, `max_runtime_seconds`, and `output_csv_path`.
5. Inspect `workers-output.csv`. Failed rows remain visible and may be retried with a filtered input CSV.
6. Merge the aggregate result into parent `PROGRESS.md` and only then mark the parent step `DONE`.

Example Batch step sequence:

```csv
id,task,status,acceptance_criteria,validation_command,completed_at,retry_count,notes
1,Build workers-input.csv,IN_PROGRESS,batch/workers-input.csv exists,test -f batch/workers-input.csv,,0,
2,Run spawn_agents_on_csv,TODO,batch/workers-output.csv exists,test -f batch/workers-output.csv,,0,
3,Merge row results,TODO,Failed rows are handled and summary is written,test -f PROGRESS.md,,0,
```

## Mixed Shapes

- A Single Task can promote to Epic when one execution stream stops being coherent.
- A Single or Epic child step can delegate homogeneous work to Batch.
- Use the **current layer's truth file** only:
  - `TODO.csv` for step planning
  - `SUBTASKS.csv` for child-task state
  - `workers-output.csv` for row results

### Mid-Task Shape Promotion

When complexity outgrows the current shape, promote in-place:

#### Single → Epic

1. Create `.codex-tasks/<task-name>/EPIC.md` from the existing `SPEC.md` goal.
2. Convert remaining `TODO.csv` rows into child task entries in `SUBTASKS.csv`.
3. Move the original `SPEC.md`, `TODO.csv`, `PROGRESS.md` into `tasks/<original-task>/` as the first child.
4. Create new child directories for the additional deliverables.
5. Log the promotion reason in the parent `PROGRESS.md`.

#### Single/Epic Step → Batch

1. Identify the `TODO.csv` or `SUBTASKS.csv` row that is actually N homogeneous items.
2. Replace it with a 3-step Batch sequence: build input → run workers → merge results.
3. Create `batch/` directory with `BATCH.md` and `workers-input.csv`.
4. The parent step stays `IN_PROGRESS` until the batch merge completes.
5. Log the delegation in `PROGRESS.md`.

## Validation Rules

- Re-read the active truth file before every new step.
- No parent task can claim success while a child subtask or batch row still fails its merge criteria.
- Keep retry counts explicit.
- Keep raw fetched material under `raw/` for Full, Epic, and Batch shapes.
- If the work is heterogeneous, use a dedicated multi-agent flow instead of forcing it into Batch.

## Context Recovery Protocol

Use the smallest artifact set that fully restores state:

- **Compact Single**: read `TODO.csv`, resume from the first non-`DONE` row.
- **Full Single**: read `SPEC.md`, `TODO.csv`, then the `PROGRESS.md` recovery block.
- **Epic Task**: read `EPIC.md`, `SUBTASKS.csv`, parent `PROGRESS.md`, then the current child task directory.
- **Batch Task**: read `SPEC.md`, `TODO.csv`, `batch/BATCH.md`, `batch/workers-output.csv`, then the `PROGRESS.md` recovery block.

Every recovery message must include:

1. `任务:` goal
2. `形态:` `single-compact | single-full | epic | batch`
3. `进度:` X/Y
4. `当前:` current step, child task, or failed row set
5. `文件:` active truth artifact path
6. `下一步:` exact next action

## Output Contract

Every status update must include:

1. `任务:` one-line goal
2. `形态:` current task shape
3. `进度:` X/Y steps or rows complete
4. `当前:` active step, child task, or batch stage
5. `验证:` latest validation command and result
6. `文件:` active task directory or truth artifact

## References

- [SPEC_TEMPLATE.md](assets/SPEC_TEMPLATE.md)
- [PROGRESS_TEMPLATE.md](assets/PROGRESS_TEMPLATE.md)
- [todo_template.csv](assets/todo_template.csv)
- [perf_todo_template.csv](assets/perf_todo_template.csv)
- [compact_todo_template.csv](assets/compact_todo_template.csv)
- [EPIC_TEMPLATE.md](assets/EPIC_TEMPLATE.md)
- [BATCH_TEMPLATE.md](assets/BATCH_TEMPLATE.md)
- [subtasks_template.csv](assets/subtasks_template.csv)
- [workers_input_template.csv](assets/workers_input_template.csv)
- [workers_output_template.csv](assets/workers_output_template.csv)
- [EXAMPLES.md](assets/EXAMPLES.md)
