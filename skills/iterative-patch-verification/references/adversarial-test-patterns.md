# Adversarial Test Patterns

## State Machine

- Replay a terminal state followed by a non-terminal state.
- Keep the same state while mutating immutable content.
- Regress a timestamp or retry counter.
- Start a new attempt while an old result remains.
- Resolve one of several pending decisions.

## Persistence

- Fail journal append.
- Fail snapshot replacement after journal append.
- Corrupt a complete middle record.
- Leave an incomplete final record.
- Fail persistence of the fail-closed status itself.
- Restart between each step of a multi-artifact publish.

## Process and Recovery

- Return permission denied from process inspection.
- Remove PID identity fields.
- Reuse a PID with a different start token.
- Exit the parent while leaving a child alive.
- Ignore graceful termination.
- Make force kill fail.
- Deliver `Exited` while output streams remain open.

## Messaging

- Deliver an instruction, restart, and flush again.
- Change delivery mode in a same-state replay record.
- Inject a resolution before the answered state.
- Queue two questions and answer only one.
- Terminate the task with queued instructions remaining.
- Fail projection deletion.

## Barrier

- Evaluate warnings, change the workspace, then accept.
- Change a report after evaluation.
- Add a pending question after evaluation.
- Reuse an old attempt's report.
- Change only metadata while keeping the canonical envelope.
- Remove one file from a multi-file report artifact set.
- Produce final warnings and exercise both accept and reject.

## CLI and IPC

- Kill the supervisor while the run is non-terminal.
- Reuse the supervisor PID.
- Make disk state older than IPC state.
- Disconnect IPC during wait.
- Compare JSON outcome, human output, and process exit code.
