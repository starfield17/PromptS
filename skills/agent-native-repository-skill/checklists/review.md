# Architecture Review Checklist

Use selectively.

- [ ] Could the change be contained in fewer modules?
- [ ] Did the change add a new dependency edge?
- [ ] Is any module importing another module's internals?
- [ ] Did a new abstraction appear without a real variation point?
- [ ] Did shared/core grow unnecessarily?
- [ ] Can an important rule be enforced automatically?
- [ ] Are tests close to the changed behavior?
- [ ] Would a capable agent understand this area from local context?
- [ ] Is there a simpler design with equal correctness?
