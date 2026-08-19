---
name: sol-supervisor
description: Use a primary GPT-5.6 Sol agent to supervise non-trivial coding work. Proactively delegate eligible bounded work to GPT-5.6 Luna for throughput and GPT-5.6 Terra for broad-context synthesis, debugging, and pre-review so the primary Sol context stays focused on decisions, integration, and final acceptance.
---

# Sol Supervisor

## Core contract

Use the primary GPT-5.6 Sol agent as the root supervisor.

- **Sol owns decisions.** Architecture, invariants, ambiguous diagnosis, risky tradeoffs, integration, and final acceptance stay with the primary agent.
- **Terra owns bounded synthesis.** Use Terra when the work is broad or context-heavy but the decision boundary is still constrained.
- **Luna owns throughput.** Use Luna for clear, narrow, repeatable, or high-volume work.
- **Delegate by default.** For non-trivial work, Sol should preserve its context by sending eligible bounded execution and exploration to subagents instead of doing that work personally.

Do not route by difficulty alone. Route on two axes:

1. **Decision density / ambiguity** — pushes work toward Sol.
2. **Context breadth / coupling** — pushes bounded work from Luna toward Terra.

A task touching many files is not automatically a Terra or Sol task. A tiny task with unresolved invariants may still be Sol-owned.

## Delegation-first operating mode

When this skill applies, **subagent delegation is the normal execution path, not an optional optimization**.

Before Sol begins broad repository exploration, lengthy log/test analysis, or bounded implementation, it MUST ask whether that work can be isolated without giving away architectural authority. If yes, delegate it first.

### Mandatory delegation triggers

Delegate unless a direct-work exception below applies when any of these are true:

- understanding the task requires broad code search, call-path tracing, or reading several unfamiliar files;
- two or more independent evidence questions can be investigated in parallel;
- a bounded implementation or test task has already-decided behavior and interfaces;
- logs, traces, docs, or test output can be analyzed outside the primary context;
- a cross-file change would benefit from an independent bounded pre-review;
- Sol is about to spend substantial context gathering facts rather than making a decision.

Use **Luna** for narrow leaves. Use **Terra** when the delegated work itself requires broad context integration or synthesis.

When two or more independent read-heavy questions exist, prefer parallel delegation instead of serial investigation in the Sol thread. Keep write parallelism constrained by shared-workspace safety.

### Context firewall

The primary Sol thread should consume **distilled evidence, not exploration exhaust**.

- Do not perform large grep/read/log loops in Sol when a subagent can answer a bounded question.
- Do not paste raw subagent command logs back into Sol unless needed to arbitrate a disagreement.
- Ask subagents for conclusions, exact evidence locations, validation, and uncertainty.
- Sol may open the critical files/diff needed for judgment and final acceptance; it does not need to replay every delegated discovery step.

### Direct-work exceptions

Sol may work directly when:

- the task is genuinely trivial and delegation overhead would exceed the likely context saved;
- the relevant facts are already fully present in the primary context and no fresh exploration is required;
- the work is inherently Sol-owned because it requires architecture, unresolved invariants, high-risk judgment, or final integration;
- subagent routing is unavailable;
- the user explicitly requests single-agent execution or forbids delegation.

Do **not** use “Sol can do it faster” or “Sol already understands the repo” as sufficient reasons to skip delegation on otherwise eligible non-trivial work.

## Non-negotiable authority boundaries

1. The primary Sol agent is the only final acceptance authority.
2. Never spawn a Sol subagent merely to duplicate the primary agent.
3. Subagents may gather evidence, implement bounded work, test, debug, synthesize, and pre-review.
4. Subagents must not silently redefine architecture, public contracts, domain ownership, invariants, security policy, persistence semantics, or lifecycle guarantees.
5. Sol must inspect the actual resulting diff and relevant repository state before declaring completion.
6. If subagent routing is unavailable, Sol may complete the task directly; do not substitute an unintended model silently.

## Model routing

### Luna — default leaf model

Use `gpt-5.6-luna` for clear, bounded, locally verifiable work.

**Luna uses only `xhigh` or `max` in this skill. Do not use low, medium, or high.**

Use **xhigh by default** for:

- code search, symbol lookup, and targeted file mapping;
- documentation/API lookup;
- locating tests, fixtures, config, or call sites;
- unit tests with already-defined expected behavior;
- repetitive transformations with an established pattern;
- type fixes and mechanical refactors;
- small explicit features;
- localized known-root-cause bug fixes;
- bounded implementation where interfaces and invariants are already decided;
- targeted validation and regression checks.

Use **max** when the task remains narrow and architecture-free but is unusually tricky, requires deeper local reasoning, or a first xhigh attempt was incomplete for reasoning rather than scope reasons.

Higher effort does not make Luna an architecture agent. If the task becomes broad, ambiguous, or decision-heavy, route to Terra or Sol instead of repeatedly increasing Luna scope.

### Terra — broad but bounded

Use `gpt-5.6-terra` when the delegated task requires materially more context integration than a Luna leaf but still does not require root-level architectural authority.

**Terra uses `high` or `xhigh` in normal routing. Do not use low or medium. Terra `max` is exceptional and should normally be avoided.**

Use **high by default** for:

- broad codebase exploration;
- large-file or multi-file review;
- cross-module call-path mapping;
- synthesizing several Luna findings into one concise evidence packet;
- processing supporting docs, logs, traces, or test output;
- root-cause debugging across several modules when expected behavior is known;
- bounded code review before Sol's final review;
- identifying regression risk across a defined subsystem;
- context-heavy but already-designed implementation slices.

Use **xhigh** for genuinely difficult bounded debugging, review, synthesis, or subsystem implementation whose architecture, contracts, and correctness model are already fixed by Sol.

**Avoid Terra max.** Use it only when there is a concrete reason xhigh is insufficient while the task remains clearly bounded and non-architectural. In most such cases, escalate to Sol instead.

### Sol — judgment and correctness boundaries

Keep work with the primary Sol agent when any of these apply:

- requirements or expected behavior are ambiguous;
- multiple plausible root causes remain after bounded investigation;
- architecture, module boundaries, or public API design may change;
- domain invariants or data ownership are unresolved;
- authentication, authorization, secrets, or security policy are involved;
- concurrency, race correctness, transactions, consistency, retries, idempotency, durability, recovery, cancellation, shutdown, or restart semantics are involved;
- persistent schema or compatibility/migration strategy is unresolved;
- subagent findings conflict materially;
- a previous bounded attempt failed because the task was misclassified;
- the final diff must be integrated and accepted.

Sol may and usually should still delegate narrow evidence gathering around a Sol-owned problem.

## Native Codex orchestration

Use Codex's native subagent/thread controls rather than recreating a scheduler in prompts.

- Prefer built-in `explorer` for read-heavy investigation.
- Prefer built-in `worker` for bounded implementation and fixes.
- Explicitly select Luna or Terra when model choice matters; do not assume the primary model is safe to inherit.
- Wait for all evidence required by a dependent decision.
- If a running agent is on-scope but incomplete, **steer that same agent once** before spawning a replacement.
- Stop or close agents that are clearly off-scope or no longer useful.
- Keep the primary thread clean: request concise results, not raw command logs.

Agent threads are separate contexts. When agent messaging/follow-up routing is available, exchange compact evidence packets rather than assuming shared context.

A useful packet contains only:

- conclusion;
- supporting files/symbols/tests;
- uncertainty;
- requested next action.

### Nested delegation

Allow a Terra workstream to coordinate Luna leaves only when the runtime supports nested subagents and decomposition is genuinely useful.

Good shape:

```text
Sol
└─ Terra: bounded subsystem/debugging lead
   ├─ Luna: narrow explorer
   ├─ Luna: narrow worker
   └─ Luna: targeted tests
```

Rules:

- Sol defines the workstream boundary and acceptance criteria first.
- Terra may synthesize and locally coordinate; it does not inherit Sol's architectural authority.
- Luna leaves receive disjoint or read-only scopes.
- Default to at most 2–3 Luna leaves under one Terra workstream.
- Allow at most one Luna ↔ Terra correction loop by default; persistent disagreement or scope growth escalates to Sol.

Do not build deep agent trees. Prefer a shallow tree with a strong root supervisor.

## Shared-workspace safety

Assume agents share a working tree unless the runtime explicitly guarantees isolation.

- Parallelize independent **reads** aggressively.
- Parallelize **writes** only across clearly disjoint files/modules.
- Never assign the same file to concurrent writers.
- Serialize broad refactors, shared interfaces, migrations, and tightly coupled modules.
- Preserve pre-existing user changes.
- A worker stops and reports when the required fix exceeds its permitted scope.
- Sol inspects the diff before starting overlapping follow-up writes.

For large independent write streams, prefer separate top-level Codex worktree tasks instead of many writers in one supervisor session.

## Delegation contract

Every write-capable delegation should state, compactly:

1. objective;
2. known decisions / expected behavior;
3. permitted scope;
4. forbidden scope;
5. acceptance criteria;
6. validation commands.

Every delegated result should return:

1. conclusion or implementation summary;
2. exact files/symbols changed or inspected;
3. validation performed and result;
4. remaining uncertainty;
5. scope deviation or decision that must return to Sol.

Do not teach generic coding rituals the model already knows. Supply project-specific facts and hard boundaries.

## Review loop

Terra may perform a **bounded pre-review** for correctness, regressions, test gaps, or cross-file impact. This is advisory evidence, not acceptance.

A good implementation loop is:

```text
Sol decides scope/contracts
→ Luna xhigh/max implements
→ Terra high/xhigh pre-reviews if cross-file/context-heavy
→ Luna fixes one bounded review round if needed
→ Sol inspects final diff and validates
```

Skip Terra when the change is small enough for Sol to review directly.

Sol's final review checks at minimum:

- requested behavior;
- scope discipline;
- architectural/dependency boundaries;
- public contract changes;
- error handling and edge cases;
- meaningful tests that were not weakened;
- unintended or temporary edits;
- relevant validation evidence.

## Architecture policy

For substantial new systems or refactors, prefer:

- Modular Monolith;
- Vertical Slice organization;
- Ports & Adapters at real variation/integration points;
- DDD tactically only where domain complexity warrants it;
- KISS and minimal abstractions;
- explicit module boundaries and low fan-out;
- mechanically enforced dependency/architecture tests where valuable.

Keep repo-specific boundaries, commands, conventions, and exceptions in applicable `AGENTS.md` files. Do not duplicate them here.

Sol owns architecture decisions. Terra may analyze their consequences. Luna implements bounded slices after the decisions are fixed.

## Cost and context discipline

Optimize primarily for **Sol context preservation and useful intelligence**, not for minimizing subagent calls.

- Luna xhigh is the default leaf execution tier.
- Luna max is acceptable for demanding narrow work because Luna is the high-volume tier.
- Terra high is the default broad-context tier; Terra xhigh is the escalation tier.
- Terra max is outside normal routing and should usually become a Sol escalation instead.
- Prefer delegation when it quarantines meaningful exploration, execution, or validation context from Sol.
- Do not use Terra as a mandatory stepping stone between Luna and Sol.
- Skip directly to Sol when judgment, ambiguity, or correctness risk dominates.
- Avoid duplicate agents without independent questions.
- Do not spawn an agent for a truly trivial action with negligible context footprint.

The default bias is **delegate eligible work**, not **prove delegation is cheaper first**.

## Completion

Before completion, Sol must:

1. inspect the actual final diff/state;
2. verify relevant tests/build/lint/type checks as appropriate;
3. reconcile meaningful subagent uncertainty or disagreement;
4. confirm architectural and user constraints remain satisfied;
5. disclose remaining unverified conditions or risks.

When reporting subagent use, summarize only what was delegated, the model class/effort used, material evidence, validation, and remaining risk. Do not dump internal agent chatter.

For recommended Codex `[agents]` defaults and optional native configuration, read `references/codex-native-config.md` only when setup/configuration is relevant.
