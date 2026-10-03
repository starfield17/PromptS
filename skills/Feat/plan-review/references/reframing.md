# Reframing Moves

Read this when an ordinary comparison does not expose a viable alternative, or an analogy hides an important mismatch. Use the move that addresses the actual difficulty; this is not a checklist.

| Move | Useful question | Boundary |
|---|---|---|
| Lift to the class | Is this repeated instance cheaper to solve with a generator or a translation layer? | Justify the generalization from repetition already present, not imagined future uses. |
| Change representation | What other representation exposes structure or removes coordination? | A metaphor must change implementation or verification. |
| Move correctness | Could this error be caught in a smaller, earlier unit? | The earlier check still needs to measure the real goal. |
| Freeze a variable | Which freedom can be removed without breaking the stated requirement? | Do not quietly discard user requirements to simplify the solution. |
| Start from the oracle | What would convincingly demonstrate correctness, and what architecture makes that observation possible? | A convenient reference is insufficient if it implements the wrong semantics. |

## An analogy with consequences

For “X is like Y,” identify the properties of Y the implementation relies on. Check whether X has them. A failed property matters when it forces a concrete design change; otherwise it is just a caveat.

For example, “spreadsheet formulas are like a virtual machine” breaks at loops and mutable state. That can force bounded unrolling and a static dataflow representation. The useful part of the analogy is a translation layer, not a promise that a spreadsheet can execute arbitrary instructions.

## Worked comparison

A plan to hand-write thousands of formulas has a large, opaque correctness problem: every formula must be right and errors appear in the final result. A compiler-style path moves the difficulty to a small set of translations from an intermediate representation, with each translation checked independently.

That alternative earns its place only if the actual task contains enough repetition. Its verification also needs the spreadsheet's string and numeric semantics, not merely the semantics of the language generating the formulas.

A useful invariant might be “all formulas are emitted by the translation layer.” A useful oracle could compare a reference implementation, the intermediate representation, and results from the target spreadsheet engine. Before recommending a command or test, inspect which engines and verification facilities the project actually has. Do not pretend a suggested check has run.

## Common counterfeit reviews

- Library swaps presented as new architectures, although the difficulty is unchanged.
- Judging a rival while generating it, so it never receives a fair comparison.
- Preferring a novel path because it sounds clever.
- Praising or replacing a user's hunch before examining its breakpoint.
- Adopting a frame that no later check can distinguish from the old path.
- Spending more on the review than the task can justify.
