# Batch Configuration

> Configuration file for homogeneous row-level work executed through
> `spawn_agents_on_csv`.

## Batch Goal

- <what every row is trying to accomplish>

## Why This Is Batchable

- Same instruction template applies to every row
- Rows are independent
- Output is structured and schema-friendly

## Instruction Template

```text
Read {file_path}, apply {target_rule}, and report:
- status
- summary
- changed
- evidence_path
- error
```

## Execution Settings

- **id_column**: `id`
- **output_schema**: `{ "status": "string", "summary": "string", "changed": "boolean", "evidence_path": "string", "error": "string" }`
- **max_workers**: `<N>`
- **max_runtime_seconds**: `<seconds>`
- **output_csv_path**: `batch/workers-output.csv`

## Retry Strategy

- After the initial run, filter failed rows from `workers-output.csv` into `batch/workers-input-retry.csv`.
- Re-run `spawn_agents_on_csv` with `csv_path="batch/workers-input-retry.csv"` and append results back into `workers-output.csv`.
- Maximum **3 batch retries**. If rows still fail after 3 rounds, mark them as `FAILED` with notes and escalate to the parent task for manual resolution.
- Each retry round must be logged in `PROGRESS.md` with the count of remaining failed rows.

## Merge Strategy

- Parent task stays `IN_PROGRESS` until all rows pass or are explicitly accepted as `FAILED`.
- Failed rows remain visible in `workers-output.csv` — never delete or hide them.
- After final retry, write a summary block to `PROGRESS.md`: total rows, passed, failed, accepted-as-failed.

## Example Invocation Shape

```text
spawn_agents_on_csv(
  csv_path="batch/workers-input.csv",
  id_column="id",
  instruction="Read {file_path} ...",
  output_schema={...},
  max_workers=8,
  max_runtime_seconds=600,
  output_csv_path="batch/workers-output.csv"
)
```
