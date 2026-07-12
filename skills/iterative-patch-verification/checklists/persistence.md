# Persistence and Recovery Checklist

- [ ] All durable state changes use one commit boundary.
- [ ] Direct mutation of committed snapshots is prohibited.
- [ ] Event or journal append failures propagate.
- [ ] Snapshot write failures propagate or enter fail-closed.
- [ ] Journal-ahead-of-snapshot state can be replayed.
- [ ] Incomplete final records are repaired or isolated.
- [ ] Complete invalid records are not treated as incomplete tails.
- [ ] Corrupt journals disable append.
- [ ] Corruption prevents new work.
- [ ] Fail-closed status persistence failures are themselves reported.
- [ ] Reducers validate legal state transitions.
- [ ] Replay rejects time, counter, identity, or payload regression.
- [ ] Atomic artifact sets have a commit marker or integrity hashes.
- [ ] Recovery does not bypass normal transition validation.
