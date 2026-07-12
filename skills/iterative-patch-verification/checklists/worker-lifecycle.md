# Worker Lifecycle Checklist

- [ ] Every execution has an immutable attempt identity.
- [ ] Old attempts are preserved.
- [ ] Fresh, recovery-resume, and explicit retry are distinct.
- [ ] Recovery processes every worker and task.
- [ ] Typed process-not-found evidence is required to prove exit.
- [ ] Inspection unknown does not trigger resume.
- [ ] PID reuse is detected with a start token.
- [ ] Parent exit does not prove process-tree exit.
- [ ] Process-group identity is real, not synthesized.
- [ ] Cancellation follows interrupt, graceful terminate, force kill, and verification.
- [ ] Unknown tree state produces unknown or orphaned, not exited.
- [ ] Result submission is followed by bounded drain.
- [ ] Session exit is observed in the same event loop as output streams.
- [ ] Active workers are always unregistered.
- [ ] Contexts and timers are released.
- [ ] Worker errors propagate to wave and run outcomes.
