---
name: plan-review
description: "Review contested software solution paths and implementation plans for load-bearing assumptions, needless complexity, scope creep, and verifiable success. Use for doubtful approaches, medium mismatch, repeated failures, or requested plan critique; skip routine implementation and ordinary code-reading."
---

# Plan Review

Help the user choose an engineering path whose difficulty and correctness they can manage. This combines Gadfly's reframing with the practical coding judgment in grill-me. It is a standalone review, not the full framework project lifecycle.

## Decide what needs examination

Inspect the relevant repository facts, the goal, the user's constraints, and any evidence of failure. Separate a discoverable implementation fact from a decision only the user can make. Ask about a consequential ambiguity rather than inventing a requirement.

Review is warranted when a solution is expensive to redo, fits its medium poorly, repeats many fragile pieces, or has failed in ways that suggest the approach itself is wrong. A small standard change can proceed without alternative architectures. If the user has fixed the approach and asks for execution, respect that choice unless a concrete obstacle needs resolving.

## Make the path compete when it matters

Name the path that would happen by default. Identify where its hard part lives, how correctness would be checked, and the assumptions that make those answers true.

A meaningful alternative changes the hard part or where correctness is established. Another library or folder name is not a new framing unless it does that. Generate rivals by breaking a consequential assumption, then compare them fairly; the default may be the best choice.

If the user offers an analogy or a hunch, test that idea before replacing it with your own. Identify where the analogy breaks and what that break forces the implementation to do differently. For difficult reframing, read [the moves and worked example](references/reframing.md).

If evidence cannot separate plausible paths, propose the smallest experiment whose result would eliminate an option. Name the deciding observation. Further debate is not a substitute for the experiment.

## Apply practical coding judgment

Check whether the plan solves the present request with a complete, simple implementation. Abstractions should remove existing repetition or make correctness easier to observe, rather than prepare for hypothetical future requests.

Check that the proposed changes belong to the task. Preserve existing conventions, and keep unrelated cleanup separate. Remove unused pieces created by the change, without expanding the task into a general cleanup.

Make success observable: a bug fix needs evidence that the faulty behavior is repaired; a refactor needs evidence that the relevant behavior remains; a feature needs evidence of the capability the user will use. Choose verification for that behavior rather than a ritual test count.

## Leave a usable decision

State the surviving path, its consequential trade-off, and what would change the decision. When a chosen framing could disappear during implementation, name a concrete invariant and the test, command, or observation that would detect drift. Use the target system's semantics for the correctness check.

Keep the review proportional. Reuse existing project decisions and verification rather than creating duplicate process artifacts. A review request authorizes analysis, not an implementation rewrite; carry out changes or probes only within the user's requested scope, and distinguish proposed checks from checks actually run.

Good work leaves a justified path or a discriminating probe, a bounded change, and a credible way to know whether it worked. It may confirm the original plan without inventing a rival for appearances.
