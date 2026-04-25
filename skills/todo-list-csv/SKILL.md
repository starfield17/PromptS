---
name: todo-list-csv
description: >
  Use this skill when you need to modify a project (add/delete/modify files)
  and want to organically synchronize the update_plan with a CSV: create a
  "{Task Name} TO DO list.csv" in the project root directory, use
  TODO/IN_PROGRESS/DONE to drive the plan's pending/in_progress/completed,
  synchronize progress, and delete the file upon full completion.
---

# Todo List CSV

## Objective

When project modifications are needed, use a CSV file located in the project root to break down the work into checkable steps; continuously update it during progress; delete the CSV upon full completion to avoid leaving or committing temporary checklists to the repository.

## Trigger Conditions

- Starting any task that will modify project content (add/modify/delete files, adjust configurations, fix bugs, implement features, etc.)
- The task has multiple independently verifiable small steps and requires explicit tracking of completion status.

## Workflow (CSV + update_plan Dual-Track Synchronization)

### 0) Condition for Enabling update_plan

- When the task contains **≥2 independently verifiable steps**, call `update_plan` to establish a plan and continuously update it during execution.

### 1) Break Down Steps and Establish Plan (One-to-One Correspondence with CSV)

- Break down into 3–12 verifiable steps (start with a verb, avoid being too long).
- Immediately call `update_plan` to establish the initial plan: step 1 as `in_progress`, the rest as `pending`.
- Keep the text of each `step` in the plan **exactly the same** as the `item` in the CSV (for easy synchronization and auditing).

### 2) Create `{Task Name} TO DO list.csv` in the Project Root Directory

- Determine the "Task Name": preferably take a short title from the user's request; simplify if necessary (remove punctuation, truncate if too long).
- Calculate the "Project Root Directory": preferably use the Git repository root; for non-Git projects, use the current working directory as the root.
- Create the file in the project root directory: `{Task Name} TO DO list.csv`.

The CSV header is fixed as (first row):

`id,item,status,done_at,notes`

- `id`: Integer starting from 1
- `item`: Single to-do item (consistent with the plan's `step`)
- `status`: `TODO` / `IN_PROGRESS` / `DONE`
- `done_at`: Completion time (ISO 8601, leave blank if not done)
- `notes`: Optional notes (file path, verification method, PR/commit, etc.)

### 3) State Machine and Mapping (Core Constraints)

- Only allow state transitions: `TODO` → `IN_PROGRESS` → `DONE` (avoid jumping directly from `TODO` to `DONE`).
- Plan mapping: `TODO`→`pending`, `IN_PROGRESS`→`in_progress`, `DONE`→`completed`.
- At any moment, **at most 1 row** is `IN_PROGRESS`; as long as there are unfinished items, try to keep **exactly 1 row** as `IN_PROGRESS` (aligned with the plan's single `in_progress` step).

### 4) Synchronize During Progress (Synchronize Each Time an Item is Completed)

- After completing the current `IN_PROGRESS` item:
  1) Update the CSV (recommended to use the `advance` script to automatically "complete the current item and start the next one")
  2) Generate the plan payload from the CSV (`plan --normalize`)
  3) Call `update_plan` to synchronize the plan with the CSV

### 5) Mid-Process Changes and Pauses

- Adding steps: Only perform "appending," avoid reordering/renumbering; update both CSV and plan simultaneously.
- Pausing for feedback: Keep the CSV; keep the current plan step as `in_progress`, or add a "waiting for feedback" step and set it to `in_progress`.

### 6) Wrap-up and Cleanup

- Confirm all rows are `DONE`, then delete the CSV file (the `cleanup` script will refuse deletion if not all are DONE).
- Call `update_plan` to mark all steps as `completed`, ensuring the plan is closed within the conversation.

## Optional Automation Scripts

Use `scripts/todo_csv.py` to automatically create/update/clean up the CSV (preferred to avoid manual editing errors).

Example commands:

- Create a list (default first item as IN_PROGRESS): `python3 ~/.codex/skills/todo-list-csv/scripts/todo_csv.py init --title "Fix login bug" --item "Reproduce issue" "Add regression test" "Fix implementation" "Run tests/build"`
- Calculate path: `python3 ~/.codex/skills/todo-list-csv/scripts/todo_csv.py path --title "Fix login bug"`
- Generate `update_plan` payload from CSV (recommended with `--normalize`): `python3 ~/.codex/skills/todo-list-csv/scripts/todo_csv.py plan --file "{csv_path}" --normalize --explanation "Synced from TODO CSV"`
- Start a specified step: `python3 ~/.codex/skills/todo-list-csv/scripts/todo_csv.py start --file "{csv_path}" --id 2`
- Advance one step (complete current IN_PROGRESS and start next TODO): `python3 ~/.codex/skills/todo-list-csv/scripts/todo_csv.py advance --file "{csv_path}" --notes "Passed unit test"`
- Check progress: `python3 ~/.codex/skills/todo-list-csv/scripts/todo_csv.py status --file "{csv_path}" --verbose`
- Clean up after full completion: `python3 ~/.codex/skills/todo-list-csv/scripts/todo_csv.py cleanup --file "{csv_path}"`
