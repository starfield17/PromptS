---
name: iterative-patch-verification
description: A workflow for improving AI-written software through repeated, bounded patch commands, independent source verification, adversarial regression tests, and explicit correctness closure. Use when a stronger lead agent directs a local coding agent through architecture repair, recovery logic, state machines, persistence, concurrency, messaging, barriers, or release-hardening work.
version: 1.0.0
---

# Iterative Patch Verification

## Purpose

Use this skill to drive an existing software project from "the tests pass" toward "the critical invariants actually hold."

The workflow separates two roles:

- **Lead Agent**: owns architecture, invariants, acceptance criteria, source review, adversarial tests, and stop decisions.
- **Local Coding Agent**: implements a bounded patch, adds tests, runs validation, commits changes, and reports limitations.

The Local Coding Agent is treated as a capable implementation worker, not as the final authority on correctness.

## Core Loop

```text
Establish baseline
-> group related defects
-> write a bounded patch command
-> local agent implements and reports
-> review the report
-> inspect the actual source
-> add adversarial regression tests
-> classify remaining findings
-> issue a smaller correctness patch
-> repeat until stop conditions are met
```

## Activation Criteria

Use this skill when several of the following are true:

- The codebase was written or heavily modified by AI.
- One-shot prompts have produced incomplete or misleading fixes.
- The project contains state machines, persistence, recovery, concurrency, messaging, workers, barriers, or process control.
- A local coding agent can edit and test the repository but is not consistently reliable at architecture-level reasoning.
- There is an architecture manual, acceptance checklist, incident report, or merged defect list.
- The user wants serial patching, source-level verification, or a correctness-closure process.

Do not use this workflow for trivial scripts, visual-only edits, or projects where no source or tests can be inspected.

## Non-Negotiable Principles

1. **Implementation and acceptance must be separated.**
2. **A completion report is a lead, not proof.**
3. **Unknown is not success.**
4. **A passed test suite does not prove an uncovered invariant.**
5. **Each patch must have a narrow scope and explicit exclusions.**
6. **Every confirmed bug should be restated as a reusable invariant.**
7. **Critical persistence and lifecycle errors must propagate; they must not be silently ignored.**
8. **Do not add new features while P0 correctness issues remain.**
9. **Do not continue creating blockers after only P1 hardening remains.**
10. **The repository must be clean and committed before final acceptance.**

## Role Responsibilities

### Lead Agent

The Lead Agent must:

- Read the architecture and acceptance material.
- Build a requirement-to-code matrix.
- Classify findings into P0 and P1.
- Group issues by common root cause.
- Produce patch commands that explain direction, invariants, tests, and exclusions.
- Review Local Agent reports for hidden limitations.
- Inspect the source and Git state.
- Run uncached tests, race checks, and static checks.
- Create temporary adversarial regression tests.
- Remove temporary review artifacts after testing.
- Decide whether to issue another correctness patch or stop.

### Local Coding Agent

The Local Coding Agent must:

- Reproduce the specified failure before changing production code when practical.
- Make the smallest coherent change that satisfies the invariants.
- Reuse existing abstractions instead of creating parallel systems.
- Add regression tests for the exact failure modes.
- Run the required validation commands.
- Commit all intended source and tests.
- Remove temporary artifacts and stale binaries.
- Return a structured completion report with known limitations.
- Leave a clean working tree.

## Standard Workflow

### Stage 0: Baseline

Before issuing the first patch:

1. Extract or open the repository.
2. Record the current commit.
3. Check whether the working tree is clean.
4. Run the normal test suite without relying on cache.
5. Run race, sanitizer, lint, type, or static checks appropriate to the language.
6. Read the architecture manual and defect list.
7. Map requirements to concrete modules, states, artifacts, and commands.

Minimum baseline evidence:

```text
HEAD
working-tree status
test result
race/sanitizer result
static-check result
known artifacts or stale binaries
initial P0/P1 matrix
```

Use `checklists/baseline.md`.

### Stage 1: Cluster Defects by Root Cause

Do not split work mechanically by issue number.

Prefer clusters such as:

```text
Persistence and commit boundary
Worker attempts and recovery
Process-tree cancellation and drain
Message lifecycle and durable outbox
Wave preflight and barrier verification
Capability truthfulness
IPC and CLI outcome semantics
Correctness closure
Release hardening
```

Fix lower-level dependencies before higher-level behavior.

### Stage 2: Convert Bugs into Invariants

Rewrite each bug as a rule that can be tested across the codebase.

Examples:

| Bug | Invariant |
|---|---|
| A cancel path ignores an error | Every critical termination and persistence error is returned and recorded. |
| An answered message reappears after restart | A terminal message can never replay into a non-terminal state. |
| A barrier accepts stale warnings | Acceptance must re-collect current facts and match the current input hash. |
| Recovery resumes after an inspection error | Only typed process-not-found evidence proves exit; unknown inspection forbids resume. |
| A delivered instruction is sent again | Delivery-pending and lifecycle-nonterminal are distinct concepts. |
| A parent process exits while a child remains | Parent exit does not prove process-tree exit. |

Patch commands and review tests should be written against invariants, not only against function names.

### Stage 3: Write a Bounded Patch Command

A patch command must contain:

- A short goal.
- The confirmed problems.
- The required invariants.
- High-level implementation direction.
- Acceptance tests.
- Explicit exclusions.
- Required validation commands.
- Required completion-report fields.

Do not over-specify every function unless the Local Agent is repeatedly failing to understand the architecture. Prefer:

```text
direction + invariant + evidence
```

over line-by-line implementation instructions.

Use `templates/patch-command.md`.

### Stage 4: Local Agent Implementation

The Local Agent should follow:

```text
reproduce
-> implement
-> add regression tests
-> run targeted tests
-> run full validation
-> commit
-> clean the tree
-> report
```

Strongly related changes may be placed in one commit. Artificial commit splitting is less important than correctness and a clean final state.

### Stage 5: Completion-Report Review

Review the report before opening the code.

Look for:

- Missing requested items.
- Claims not supported by tests.
- Limitations that are actually unresolved P0 issues.
- "Fallback," "best effort," "lightweight," "temporarily," or "unverified" paths.
- A claimed full lifecycle that only performs a one-shot operation.
- A claimed recovery path that silently becomes a fresh retry.
- A claimed current-facts check that only hashes an old artifact.
- A claimed process-tree exit that only observes a parent process.
- A claimed durable transition that mutates memory before persistence.

Use `templates/completion-report.md` as the required report format.

### Stage 6: Source-Level Verification

Never stop at report-level acceptance for critical work.

#### Delivery checks

```bash
git log -1 --oneline
git status --short
git diff --check
```

Verify:

- The claimed commit exists.
- The tree is clean.
- Regression tests are committed.
- No temporary run directories, logs, archives, or stale binaries remain.
- Any shipped binary matches the current source revision.

#### Test checks

Run uncached commands appropriate to the repository.

Example for Go:

```bash
go test -count=1 ./...
go test -race -count=1 ./...
go vet ./...
```

Repeat sensitive packages several times where concurrency or recovery is involved.

#### Code review searches

Search for patterns that often hide correctness gaps:

```text
_ =
_, _ =
direct snapshot mutation
time.AfterFunc
os.Remove
TerminateSession
TreeExited
ProcessExited
RunDegraded
IsPending
currentAttempt
latestAttempt
Descriptor().Capabilities
old artifact hash
string matching for typed errors
```

Not every ignored result is a bug, but every persistence, state-transition, cancellation, or termination error must be justified.

Use `templates/source-review.md`.

### Stage 7: Adversarial Regression Tests

For every positive claim, construct a negating scenario.

Examples:

| Claim | Adversarial test |
|---|---|
| Terminal messages never revive | Replay `queued -> answered -> queued`. |
| The whole process tree exited | Exit the parent while keeping a child alive. |
| Acceptance uses current facts | Evaluate, mutate the workspace, then accept. |
| A report belongs to the producing attempt | Publish from attempt 1, start attempt 2, then verify. |
| Errors are propagated | Inject disk-full, permission, unavailable IPC, or failed atomic write. |
| Delivered instructions are not repeated | Mark delivered, restart, then flush the outbox. |
| Recovery resumes only dead workers | Return a typed permission error from process inspection. |
| Same-state journal records are idempotent | Keep status unchanged while mutating payload or route. |
| A warning can be accepted | Produce final warnings and exercise accept and reject paths. |

Temporary review tests should be removed after the review unless the user requests that they be committed. If they reveal a real bug, the next patch command must require permanent regression coverage.

Use `references/adversarial-test-patterns.md`.

### Stage 8: Classify Findings

#### P0: blocks phase acceptance

Typical P0 findings:

- State can become false or internally inconsistent.
- Data can be corrupted or replayed illegally.
- A second worker can start while the first may still be alive.
- Cancellation can claim success without proof.
- A message can be delivered twice.
- A barrier can accept stale facts.
- Critical errors are silently ignored.
- A terminal run leaves live or queued state behind.
- Recovery bypasses the state machine.
- A required decision has no reachable acceptance path.
- The repository ships an old binary that does not match source.

#### P1: required before release, but not always phase-blocking

Typical P1 findings:

- A CLI call blocks longer than necessary.
- Summary output omits non-critical details.
- Outcome reasons are unstructured strings.
- Real external-harness tests are not automated.
- The implementation is difficult to maintain.
- Recovery is safe but operationally inconvenient.
- A generic API has ambiguous semantics but critical callers use safer specialized APIs.

Use `references/p0-p1-classification.md`.

### Stage 9: Issue a Correctness Patch

When source verification confirms new P0 findings:

- Merge closely related confirmed findings into one small correctness patch.
- Require tests that fail before the fix.
- Prohibit unrelated P1 work.
- Require a clean commit and working tree.
- Ask the Local Agent to report exact code locations and remaining limitations.

Do not create a new feature PR to hide an unresolved correctness problem.

### Stage 10: Stop Conditions

Stop the P0 loop when all are true:

1. Every target architecture requirement has a concrete implementation.
2. All known P0 findings are closed.
3. Full uncached tests pass.
4. Race, sanitizer, lint, and static checks pass.
5. Adversarial tests for the critical invariants pass.
6. The latest code is committed.
7. The working tree is clean.
8. No stale binaries or test artifacts remain.
9. Remaining findings are genuinely P1.
10. The Lead Agent cannot construct another reasonable scenario that breaks a critical invariant.

Then produce a final acceptance report with explicit phase results.

Use `templates/final-acceptance.md`.

## Patch Scope Guidance

A useful progression for complex agent runtimes is:

```text
PR1  Persistence and commit boundary
PR2  Worker lifecycle, recovery, cancellation, and drain
PR3  Durable message router and instruction outbox
PR4  Wave preflight, barriers, and summaries
PR5  Effective capabilities and harness contracts
PR6  IPC-first reads and stable CLI outcomes
PR7+ Correctness closure based on source-level adversarial review
P1   Release hardening and real external-system validation
```

This is a pattern, not a mandatory numbering scheme.

## Evidence Hierarchy

Use the following order of trust:

1. Reproducible runtime behavior.
2. Focused regression tests.
3. Source-level control flow and state transitions.
4. Durable artifacts and event history.
5. Full test/race/static-check results.
6. Completion report.
7. Agent confidence statements.

A lower item cannot override a contradiction found in a higher item.

## Failure Handling

If the Local Agent claims completion but the package is dirty, uncommitted, or contains stale binaries:

- Separate implementation correctness from delivery cleanliness.
- Do not accept the delivery as final.
- Issue a small cleanup patch if the implementation itself is sound.

If the Local Agent cannot complete the full patch:

- Accept partial evidence.
- Keep successfully proven changes.
- Create a narrower next patch.
- Never invent success or ask the agent to hide limitations.

## Package Map

- `templates/patch-command.md`: command sent to the Local Coding Agent.
- `templates/completion-report.md`: required Local Agent response.
- `templates/source-review.md`: source-level verification report.
- `templates/final-acceptance.md`: final phase acceptance report.
- `checklists/`: focused review checklists by subsystem.
- `references/adversarial-test-patterns.md`: reusable negative test ideas.
- `references/p0-p1-classification.md`: severity guidance.
- `references/stop-conditions.md`: stopping and transition rules.
- `examples/phase-closure-workflow.md`: worked example.
- `scripts/validate_skill.py`: validates package structure, manifest, and English-only content.
- `manifest.txt`: complete relative file list.

## Final Instruction

Do not optimize for the fewest patch rounds.

Optimize for this property:

> Each round produces a small, reviewable, committed improvement whose critical claims can be independently disproved or confirmed.
