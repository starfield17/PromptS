# Task: <task-id>

## Role
<role>

## Objective
<objective>

## Context
<context from Codex>

## Scope
You may inspect:
- <path>

You may change:
- <path>

## Out of scope
Do not modify:
- <path>

## Permissions
- May edit files: <yes/no>
- May run tests: <yes/no>
- May install dependencies: <yes/no>
- May access network: <yes/no>
- May create new files: <yes/no>

## Expected output
Write your final answer to:

```text
.CC_subagent/runs/<task-id>/result.md
.CC_subagent/runs/<task-id>/status.json
.CC_subagent/runs/<task-id>/changed-files.txt
.CC_subagent/runs/<task-id>/patch.diff
```

## Required final sections
Your `result.md` must include:

1. Summary
2. Findings
3. Changes
4. Tests
5. Risks
6. Recommended next steps
7. Unresolved questions

## Completion criteria
<how Codex should know this task is complete>

## Important instructions
- Work only inside your isolated workspace unless the task explicitly says otherwise.
- Be honest about uncertainty.
- Report failed commands.
- Do not hide dead ends.
- Prefer minimal changes.
- Do not modify unrelated files.
