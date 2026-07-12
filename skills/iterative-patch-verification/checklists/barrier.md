# Preflight and Barrier Checklist

## Preflight

- [ ] Every used harness is registered and probed.
- [ ] Installation, authentication, compatibility, and capability failures are classified.
- [ ] Multi-task waves declare parallel responsibilities.
- [ ] Placeholder responsibilities are rejected.
- [ ] Failed preflight starts no workers.
- [ ] Preflight facts are persisted.

## Barrier

- [ ] Reports are re-read from disk.
- [ ] Report metadata, canonical envelope, and markdown integrity are bound.
- [ ] Reports bind to the producing worker attempt.
- [ ] Pending decisions block verification.
- [ ] Actual workspace changes are captured.
- [ ] Scope and ownership are evaluated from real changes.
- [ ] High-risk changes are classified.
- [ ] Failed, blocked, warning, passed, and cancelled are distinct.
- [ ] Warning acceptance re-collects current facts.
- [ ] Acceptance binds actor, reason, verification, and input hash.
- [ ] Input changes invalidate old acceptance.
- [ ] Wave warnings and final-run warnings both have reachable accept and reject paths.
- [ ] Waiting for a decision uses a non-terminal run state.
