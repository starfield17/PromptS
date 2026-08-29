# Friction

Implementation is where design errors surface first. By default that information is destroyed at the end of the session: the agent works around the problem, the workaround ships, and the wrong rule survives to cause the same detour next month — with a different agent, which will invent a different workaround.

`FRICTION.md` is the reverse channel. It is the counterpart to `SPEC.md`'s `Found · Not doing`: that one collects work outside the scope, this one collects **rules that were wrong**.

## The bar for writing an entry

One of these actually happened:

- A stated rule — a prohibition in `SPEC.md`, a boundary in `AGENTS.md`, a documented invariant — turned out to be wrong, ambiguous, or inapplicable here.
- The design forced code you would not defend.
- The first approach that looked correct was blocked by something no document mentioned, and finding out cost real time.

None of those happened? Write nothing. This matters more than it sounds: a log with an entry per task is a form, forms get filled in with "no issues encountered," and once a file is 80% noise nobody triages it and the channel is dead. Rarity is what makes the entries worth reading.

Not friction: the task was hard; a test failed and you fixed it; you had to read three files; you disagree with a naming convention.

## Format

Append-only. Newest at the top, so triage reads down and stops at the line it recognizes.

```markdown
## 2026-08-28 · export: add tenant_id to the CSV header
constraint: modules/export must not import modules/billing (root AGENTS.md)
happened:   the tenant's display currency lives in billing.Tenant; the header needs it
workaround: passed currency in as a parameter, 3 call sites changed
proposal:   move Currency into core, or give export a port billing implements
```

Five fields, three minutes. Constraint first, because triage groups by constraint — the same rule appearing three times under different tasks is the signal, and it is invisible if entries are organized by task.

`proposal` may be `none — flagging only`. An entry with no proposal is still useful; an entry with no `constraint` is a diary.

## Triage

Not continuous. Batch it, at either of these two moments:

- `FRICTION.md` has ~10 untriaged entries.
- Before starting a tier-3 change in an area that has entries. The friction is about to become expensive, which makes this the cheapest possible moment to act on it.

Every entry leaves triage with exactly one of these outcomes:

| Outcome | When | What it produces |
|---|---|---|
| **Change the rule** | The constraint is wrong, or right for a reason that no longer holds | Edit `AGENTS.md` / `SPEC.md` / the check. The check changes too, or the rule was never real |
| **Change the code** | The rule is right and the code is on the wrong side of it | A tier-2 or tier-3 task, scheduled |
| **Clarify** | The rule is right but was read wrong, twice | One added sentence at the point of confusion — not a new document |
| **Close as noise** | One-off, or the friction was the author's | Delete the entry. Say nothing further |

Then move triaged entries to a `## Resolved` section with the outcome appended, or delete them. Either is fine; leaving them in place is not, because the count is the trigger for the next triage.

**The rule for the rule-change outcome:** if a constraint gets changed, the mechanism that enforced it changes in the same commit. A rule loosened in prose while the check still enforces the old version produces the worst state available — the agent is told one thing and punished for another, and it will learn to trust neither.

## What to do with a repeat

Two entries naming the same constraint is the threshold for acting. One is an anecdote; the second is evidence the rule is mis-specified rather than the situation being unusual.

Two entries naming the same *module* — different constraints, same place — mean something different: the boundary is probably in the wrong location, and that is a `surveyor` question, not a rule question.

## Feeding it back to producer

Entries whose proposal is "this constraint should not exist" and which survive triage are the input to the next round of spec work, alongside the `Found · Not doing` list. Those two lists together are the honest record of where the plan met the code — which is the only material a revised plan should be built from, and which is otherwise entirely lost.
