# Example: Phase Closure Workflow

## Initial Defect Set

Assume an agent runtime has these problems:

- Recovery resumes after any inspection error.
- Failed results are mapped to partial success.
- Cancellation does not confirm child exit.
- Messages can remain queued after task termination.
- Barrier warnings cannot be accepted.
- CLI wait exits zero for failed tasks.

## Patch Sequence

### Patch 1: Durable State Boundary

Invariants:

- Every durable transition uses one commit API.
- Journal append failures propagate.
- Replay can recover a journal-ahead-of-snapshot state.

### Patch 2: Worker Lifecycle

Invariants:

- Recovery is not retry.
- PID reuse is detected.
- Unknown process state forbids resume.
- Cancellation proves the tree state.

### Patch 3: Durable Messages

Invariants:

- Terminal messages do not revive.
- Instructions are persisted before delivery.
- Delivery-pending differs from lifecycle-nonterminal.
- Terminal tasks expire remaining messages.

### Patch 4: Barrier

Invariants:

- Verification re-reads reports and current workspace facts.
- Pending decisions block.
- Acceptance re-collects current facts.
- Final warnings have an accept and reject path.

### Patch 5: CLI and IPC

Invariants:

- Live IPC is preferred over stale disk.
- Disk fallback is explicitly degraded.
- Target failure produces a non-zero exit code.

## Adversarial Review

The Lead Agent adds tests:

```text
inspection permission denied -> must not resume
parent exits, child remains -> must not report tree exited
answered message followed by queued record -> replay corruption
delivered instruction followed by restart -> no second delivery
barrier warnings followed by workspace change -> stale acceptance
final warnings -> accept completes, reject fails
```

## Acceptance

The phase is accepted only after:

- all tests pass without cache,
- race and static checks pass,
- the adversarial tests pass,
- all changes and tests are committed,
- the package contains the reviewed commit,
- and only P1 work remains.
