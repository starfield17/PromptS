# Messaging Checklist

- [ ] Message states have an explicit transition table.
- [ ] Terminal messages cannot transition out.
- [ ] Same-state replay is truly idempotent.
- [ ] Immutable fields cannot change during replay.
- [ ] Counters and timestamps are monotonic.
- [ ] Delivery mode is legal only for instructions.
- [ ] Delivery-pending, decision-pending, and acknowledgement-pending are distinct.
- [ ] Delivered instructions are not sent again.
- [ ] Instructions are persisted before delivery.
- [ ] Unsupported and failed delivery are durable.
- [ ] Next-turn delivery has a real trigger.
- [ ] Resume delivery has a complete worker lifecycle.
- [ ] Terminal tasks and runs expire remaining messages.
- [ ] Resolving one question does not unblock a task with other pending decisions.
- [ ] Top-level question files are projections, not authoritative history.
- [ ] Projection deletion errors propagate except for missing files.
- [ ] Message journal corruption enters fail-closed.
