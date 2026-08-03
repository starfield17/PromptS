---
name: sol-luna-supervisor
description: Route non-trivial coding work between a primary GPT-5.6 Sol supervisor and GPT-5.6 Luna subagents. Use Luna high for code search, call-chain tracing, file mapping, unit tests, type fixes, and mechanical refactors; Luna xhigh for clear small features and localized bugs with known root causes; Luna max for ordinary bugs spanning multiple modules. Keep ambiguous complex bugs, DDD boundaries, architecture and API design, concurrency, transactions, recovery, lifecycle correctness, all code review, and final diff acceptance with the primary Sol agent. Never use Terra.
---

# Sol–Luna Supervisor

## Purpose

Use the primary `gpt-5.6-sol` agent as the engineering supervisor, architecture owner, difficult debugger, code reviewer, and final acceptance authority.

Use only `gpt-5.6-luna` for delegated subagent work.

This skill intentionally does not use Terra.

## Non-negotiable model policy

1. The primary agent is Sol.
2. The only permitted subagent model is `gpt-5.6-luna`.
3. Never spawn a Terra subagent.
4. Never spawn a Sol subagent.
5. Do not silently allow a subagent to inherit the primary Sol model.
6. Explicitly request both the Luna model and its reasoning effort for every spawn.
7. “Luna Max” means:
   - model: `gpt-5.6-luna`
   - `model_reasoning_effort`: `max`
8. The primary Sol agent personally performs all Sol-owned work. Do not delegate Sol-owned work to any subagent.
9. Luna may inspect, implement, test, and report evidence. Luna does not make final architectural decisions and does not perform final code review or acceptance.
10. If explicit Luna routing is unavailable, do not substitute Terra or a Sol subagent. The primary Sol agent may complete the work directly only as a disclosed fallback required to avoid blocking the task.

## Routing table

Apply this table exactly.

| Work type | Owner | Model | Reasoning |
|---|---|---|---|
| Search code, trace call chains, map and organize relevant files | Luna subagent | `gpt-5.6-luna` | `high` |
| Write unit tests, add or repair types, perform mechanical refactoring | Luna subagent | `gpt-5.6-luna` | `high` |
| Implement a small feature with clear requirements | Luna subagent | `gpt-5.6-luna` | `xhigh` |
| Fix a localized bug whose root cause is already identified | Luna subagent | `gpt-5.6-luna` | `xhigh` |
| Fix an ordinary bug spanning multiple modules | Luna subagent | `gpt-5.6-luna` | `max` |
| Investigate and fix an ambiguous complex bug | Primary Sol personally | `gpt-5.6-sol` | current primary effort |
| Decide DDD boundaries, architecture, or API design | Primary Sol personally | `gpt-5.6-sol` | current primary effort |
| Handle concurrency, transactions, recovery, or lifecycle correctness | Primary Sol personally | `gpt-5.6-sol` | current primary effort |
| Review code | Primary Sol personally | `gpt-5.6-sol` | current primary effort |
| Review and accept the final diff | Primary Sol personally | `gpt-5.6-sol` | current primary effort |

## Classification rules

Classify each work item before editing.

### Luna high: exploration

Use Luna high when the task is primarily read-heavy:

- find the implementation of a behavior;
- trace a call path or dependency path;
- identify relevant files, symbols, tests, or configuration;
- locate duplicated or legacy logic;
- map the likely change surface;
- summarize a clearly scoped part of the repository.

Exploration agents are read-only by instruction.

Tell them explicitly:

> Do not edit, create, delete, rename, format, or otherwise modify any file.

### Luna high: routine maintenance

Use Luna high for bounded, low-ambiguity maintenance:

- unit-test implementation;
- type annotations or type-error fixes whose intended behavior is clear;
- mechanical refactoring that must preserve behavior;
- repetitive migrations with an established pattern;
- straightforward fixture or test-data changes;
- documentation changes directly implied by a completed implementation.

A mechanical refactor changes structure without requiring new architecture or behavioral judgment.

### Luna xhigh: clear implementation

Use Luna xhigh for:

- a small feature with explicit behavior and acceptance criteria;
- a localized bug after Sol or an earlier investigation has already identified the root cause;
- a bounded implementation inside an architecture already decided by Sol;
- a non-trivial but narrow change whose permitted files and public behavior are clear.

Do not send an ambiguous goal to Luna xhigh merely because it appears small.

### Luna max: cross-module ordinary bug

Use Luna max only when all of the following are true:

- the bug spans multiple implementation modules;
- the expected behavior is known;
- the problem is an ordinary implementation defect rather than an architectural failure;
- no DDD boundary, public API, concurrency, transaction, recovery, security, or lifecycle decision is unresolved;
- the work can be expressed as a bounded task contract;
- Sol can review the resulting diff afterward.

Examples include:

- inconsistent data propagation through several layers;
- an ordinary state update missing from two or more modules;
- mismatched adapters implementing an already-defined contract;
- a multi-module regression with a reproducible failure and known expected result.

Luna max is not a replacement for Sol on ambiguous or high-risk problems.

### Primary Sol: ambiguous complex bugs

Sol personally owns the task when one or more of these apply:

- the failure cannot be reproduced reliably;
- several plausible root causes remain;
- requirements or expected behavior are unclear;
- the fix may redefine a domain boundary or public contract;
- the bug involves subtle invariants;
- previous bounded Luna attempts failed for substantive reasons;
- worker conclusions conflict;
- security-sensitive behavior is involved;
- the likely fix requires architectural judgment.

Sol may delegate narrow read-only searches to Luna high, but Sol must personally perform the core diagnosis, decisions, implementation when necessary, and review.

### Primary Sol: architecture and correctness boundaries

Sol personally owns:

- DDD bounded-context design;
- aggregate and domain-invariant design;
- dependency direction;
- application/domain/infrastructure separation;
- public APIs and cross-repository contracts;
- persistent schema design;
- authentication and authorization decisions;
- concurrency and race correctness;
- transaction boundaries and consistency;
- retries, idempotency, durability, and recovery;
- process lifecycle, cancellation, shutdown, and restart behavior;
- compatibility and migration strategy.

Luna may implement bounded pieces only after Sol has made and documented every relevant decision.

### Primary Sol: all code review

Code review is always Sol-owned.

Do not spawn Luna to perform:

- final code review;
- PR review;
- security review;
- architecture review;
- maintainability acceptance;
- final test-quality review;
- final diff approval.

Luna may collect factual evidence requested by Sol, such as locating call sites or running tests. Sol must independently interpret that evidence and inspect the actual diff.

## Workflow

### 1. Read repository instructions

Before doing work:

- read applicable `AGENTS.md` and repository documentation;
- inspect the current Git status;
- identify pre-existing user changes;
- determine the build, test, lint, and type-check commands;
- preserve existing work.

### 2. Classify the task

Map each work item to exactly one row in the routing table.

For mixed tasks, split them into work items. Keep architecture and difficult reasoning with Sol, then delegate only bounded implementation or exploration.

Do not route a whole project based on its easiest subtask.

### 3. Decide before delegating

Sol must resolve these before assigning write-capable Luna work:

- objective;
- expected behavior;
- architecture and domain ownership;
- permitted write scope;
- forbidden scope;
- acceptance criteria;
- dependencies between tasks;
- validation commands.

If any architecture decision remains unresolved, Sol resolves it first.

### 4. Spawn Luna explicitly

For every Luna spawn, explicitly specify:

- model: `gpt-5.6-luna`;
- reasoning effort: `high`, `xhigh`, or `max`;
- built-in role:
  - prefer `explorer` for read-only repository investigation;
  - prefer `worker` for implementation, tests, and fixes;
- whether the agent may edit;
- exact task scope;
- expected return format.

Do not rely on inherited model selection.

If the runtime exposes the selected child model, verify that it is Luna. If it is not Luna, stop that delegation rather than paying for an unintended Sol subagent.

### 5. Use shared-workspace safety

Assume subagents share the working tree unless the runtime guarantees isolation.

Rules:

1. Never let two write-capable agents edit the same file concurrently.
2. Avoid concurrent writers in the same tightly coupled module.
3. Parallelize read-only exploration freely when the questions are independent.
4. Parallelize writers only when their file scopes are disjoint.
5. Serialize broad refactors and cross-cutting changes.
6. Do not let workers revert or overwrite pre-existing user changes.
7. A worker must stop and report if the required fix exceeds its assigned scope.
8. Sol inspects the diff after every write-capable worker before starting overlapping work.

Before concurrent writes, establish an internal ownership table:

| Task | Luna effort | Permitted files/modules | Dependencies |
|---|---|---|---|

If scopes overlap, serialize them.

### 6. Wait and collect evidence

Wait for every required Luna result before making dependent decisions.

Require concise evidence rather than raw logs:

- findings;
- exact files changed;
- tests or commands run;
- results;
- unresolved uncertainty;
- scope deviations;
- any decision that must return to Sol.

### 7. Sol reviews the actual work

Sol must inspect the repository and actual diff. Do not accept a Luna summary as proof.

Check:

- task objective was satisfied;
- changes stayed inside scope;
- no unrelated edits appeared;
- behavior matches requirements;
- DDD and dependency boundaries remain valid;
- public contracts did not change without authorization;
- error handling is appropriate;
- tests are meaningful and not weakened;
- code is understandable and maintainable;
- no debug artifacts or temporary work remain.

### 8. Sol validates independently

Sol independently runs or verifies relevant:

- focused tests;
- integration tests;
- type checks;
- linting;
- formatting checks;
- build;
- regression tests.

Worker-reported success is supporting evidence, not final acceptance.

### 9. Sol performs final acceptance

Only Sol may declare the task complete.

Completion requires:

- requested behavior is implemented or the review is finished;
- all worker diffs were inspected;
- relevant validation passed;
- final diff is coherent;
- architecture remains consistent;
- remaining risks or unverified conditions are disclosed.

## Delegation templates

### Luna high explorer

Use an instruction equivalent to:

```text
Spawn a subagent with:
- role: explorer
- model: gpt-5.6-luna
- model_reasoning_effort: high
- editing: forbidden

Question:
<one concrete repository question>

Inspect:
<directories, modules, symbols, or behavior>

Rules:
- Do not edit, create, delete, rename, format, or otherwise modify files.
- Do not propose an architecture unless explicitly asked.
- Base conclusions on concrete repository evidence.
- Keep the investigation bounded.

Return:
1. relevant files and symbols;
2. actual call or dependency path;
3. existing tests and conventions;
4. likely change surface;
5. risks and ambiguities;
6. concise evidence for each important conclusion.
```

### Luna high maintenance worker

Use an instruction equivalent to:

```text
Spawn a subagent with:
- role: worker
- model: gpt-5.6-luna
- model_reasoning_effort: high

Objective:
<unit tests, type work, or mechanical refactor>

Permitted scope:
<exact files, modules, or symbols>

Forbidden scope:
<unrelated files, behavior changes, APIs, schemas, and architecture>

Requirements:
<explicit requirements>

Validation:
<commands to run>

Rules:
- Preserve behavior unless a stated test requirement says otherwise.
- Do not redesign architecture.
- Do not expand scope silently.
- Preserve existing user changes.
- Make the smallest correct change.
- Stop and report if architectural judgment is required.

Return:
1. summary;
2. exact files changed;
3. commands run and results;
4. remaining uncertainty;
5. anything requiring Sol review.
```

### Luna xhigh implementation worker

Use an instruction equivalent to:

```text
Spawn a subagent with:
- role: worker
- model: gpt-5.6-luna
- model_reasoning_effort: xhigh

Objective:
<one clear small feature or localized known-root-cause bug fix>

Context and known decisions:
<expected behavior, known root cause, and architecture decided by Sol>

Permitted scope:
<exact files, modules, or symbols>

Forbidden scope:
<unrelated files, public contracts, schemas, and architectural changes>

Acceptance criteria:
<observable success conditions>

Validation:
<commands to run>

Rules:
- Implement only the assigned task.
- Do not reinterpret requirements or redesign architecture.
- Add or update tests for changed behavior.
- Preserve existing user changes.
- Do not weaken tests to make them pass.
- Stop and report if the known diagnosis is contradicted.

Return:
1. implementation summary;
2. exact files changed;
3. tests and commands run;
4. results;
5. remaining uncertainty;
6. anything requiring Sol review.
```

### Luna max cross-module bug worker

Use an instruction equivalent to:

```text
Spawn a subagent with:
- role: worker
- model: gpt-5.6-luna
- model_reasoning_effort: max

Objective:
<one reproducible ordinary bug spanning multiple modules>

Expected behavior:
<clear expected result>

Reproduction and evidence:
<reproduction steps, failing test, logs, or known path>

Architectural constraints already decided by Sol:
<domain ownership, contracts, dependency direction, and invariants>

Permitted scope:
<exact modules and files>

Forbidden scope:
<architecture, DDD boundaries, public APIs, schemas, concurrency,
transactions, recovery, lifecycle behavior, security policy, and unrelated code>

Acceptance criteria:
<observable conditions and required regression tests>

Validation:
<focused and broader commands>

Rules:
- Fix the root cause, not only the symptom.
- Stay within the established architecture.
- Do not redefine contracts or invariants.
- Add a regression test.
- Preserve existing user changes.
- Stop and return to Sol if the problem is more ambiguous or architectural than stated.
- Do not claim success without concrete validation evidence.

Return:
1. reproduced failure;
2. root cause found;
3. implementation summary;
4. exact files changed;
5. regression test added or updated;
6. commands and results;
7. residual risks;
8. anything requiring Sol intervention.
```

## Bug escalation

Use this escalation path:

1. Luna high may locate and trace the failing path.
2. If the root cause becomes clear and local, use Luna xhigh.
3. If the root cause is clear but the ordinary fix spans multiple modules, use Luna max.
4. If the bug remains ambiguous, complex, architectural, high-risk, or crosses a Sol-owned boundary, Sol takes over personally.
5. Do not repeatedly respawn Luna with nearly identical prompts after substantive failure.
6. Never escalate to Terra.
7. Never escalate to a Sol subagent.

## Testing policy

Luna high may write tests when expected behavior is already defined.

Sol must review whether tests:

- would fail for the original bug when feasible;
- verify behavior rather than implementation accidents;
- cover relevant edge cases;
- avoid duplicating production logic;
- are deterministic;
- do not hide flakiness;
- do not weaken existing assertions.

Concurrency, transaction, recovery, lifecycle, security, and cross-domain acceptance tests remain Sol-owned in design and final review. Luna may implement a bounded test only after Sol defines the correctness model precisely.

## DDD default

For new systems and major refactors, default to Domain-Driven Design or a practical bounded-context equivalent unless the user explicitly requests otherwise or the project is too small to justify it.

Sol owns:

- bounded contexts;
- domain model;
- aggregate boundaries;
- domain invariants;
- ubiquitous language;
- application services;
- ports and adapters;
- infrastructure placement;
- cross-context contracts.

Luna implements only the bounded pieces Sol assigns after these decisions are settled.

Prefer practical DDD over ceremonial abstractions.

## Cost discipline

The goal is to spend Sol intelligence only where it materially improves correctness.

Therefore:

- use Luna high for read-heavy and mechanical work;
- use Luna xhigh for clear bounded implementation;
- use Luna max for demanding but ordinary cross-module bugs;
- keep ambiguous and high-risk reasoning with the primary Sol;
- do not spawn duplicate agents without an independent purpose;
- do not use xhigh or max for simple repository search;
- do not use max merely because a task touches many files;
- do not create Sol subagents;
- do not use Terra;
- do not delegate final review.

## Final response

When subagents were used, report briefly:

- what was delegated;
- which Luna effort handled it;
- what Sol reviewed personally;
- validation performed;
- remaining risk or unverified conditions.

Do not dump internal subagent chatter.

Do not imply that Luna approved its own work.

The final answer represents Sol’s independently reviewed conclusion.
