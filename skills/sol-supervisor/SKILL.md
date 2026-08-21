---
name: sol-supervisor
description: Use a primary GPT-5.6 Sol agent to supervise non-trivial coding, repository, and document-heavy technical work through a mandatory route-delegate-wait-decide-execute-review-accept loop. Luna handles narrow/high-volume work and visual OCR; Terra handles broad bounded synthesis, debugging, and pre-review.
---

# Sol Supervisor

## Mission

Keep the primary GPT-5.6 Sol context concentrated on requirements, decisions, invariants, integration, and final acceptance.

- **Sol owns decisions.** Architecture, ambiguity, risky tradeoffs, correctness boundaries, integration, and acceptance.
- **Terra owns bounded synthesis.** Broad/context-heavy investigation, debugging, synthesis, and pre-review whose authority boundary is already fixed.
- **Luna owns throughput.** Narrow exploration, implementation, testing, validation, repetitive work, and visual document transcription/OCR.

Route on two axes, not difficulty alone:

1. **Decision density / ambiguity** pushes work toward Sol.
2. **Context breadth / coupling** pushes bounded work from Luna toward Terra.

## Mandatory supervisor loop

For every non-trivial task, follow this loop. **Do not skip directly from intake to Sol doing the work.**

```text
BOOTSTRAP
   ↓
ROUTE
   ↓
DELEGATE ──→ WAIT/COLLECT
   ↑              ↓
   │          SOL DECIDE
   │              ↓
   └──── re-route if scope/assumptions change
                  ↓
               EXECUTE
                  ↓
          VERIFY / PRE-REVIEW
                  ↓
        bounded correction if needed
                  ↓
              SOL ACCEPT
```

### 0. BOOTSTRAP — minimal orientation only

Sol may do only the minimum needed to understand the task and create bounded work units:

- read the user request and applicable `AGENTS.md` / project instructions;
- inspect working-tree status and top-level structure when relevant;
- inspect one obvious entry point or artifact when needed to route correctly.

**Bootstrap is not exploration.** Do not begin broad grep/read loops, multi-file tracing, long log analysis, document transcription, or implementation here.

### 1. ROUTE — assign an owner before substantial work

Break the task into concrete work units and assign each one:

- `SOL` — decision-heavy, ambiguous, architectural, high-risk, or final-integration work;
- `TERRA high/xhigh` — broad but bounded context integration/synthesis;
- `LUNA xhigh/max` — narrow/high-volume execution or evidence gathering.

For a non-trivial task with subagents available, the first substantive execution wave **must contain at least one delegated work unit** unless every remaining unit is genuinely Sol-owned.

If Sol chooses no delegation, the reason must match a Direct-work exception below. “I can do it faster” and “I already understand the repo” are not exceptions.

### 2. DELEGATE — launch the smallest useful wave

Spawn independent read-heavy work in parallel. Keep write scopes disjoint.

Every delegated unit should include only:

- objective/question;
- known decisions and expected behavior;
- permitted scope and forbidden scope;
- acceptance evidence or validation expected;
- concise return format.

Prefer built-in `explorer` for read-heavy work and `worker` for bounded edits. Explicitly select the intended model/effort when it matters.

### 3. WAIT/COLLECT — do not duplicate child work in Sol

After delegation, wait for the evidence required by the next decision.

While a relevant subagent is working, Sol must not independently redo that same search, trace, OCR, implementation, or review merely to stay busy.

If an on-scope agent is incomplete:

1. steer/follow up with the same thread once;
2. wait again;
3. then re-route, upgrade model/effort, or escalate to Sol if needed.

Request distilled packets, not raw command exhaust:

- conclusion;
- exact files/symbols/pages/evidence;
- validation result;
- uncertainty;
- next decision needed from Sol.

### 4. SOL DECIDE — make the judgment, not the discovery replay

Sol reconciles the returned evidence and decides contracts, root-cause interpretation, architecture, scope, and next work units.

Sol may open a small number of critical files/pages/diff hunks needed to verify a judgment. It should not replay every delegated discovery step.

If assumptions, scope, or architecture changed, return to **ROUTE** instead of silently absorbing the new work into Sol.

### 5. EXECUTE — delegate already-decided implementation

Once behavior, interfaces, and invariants are fixed:

- use Luna xhigh for normal bounded implementation;
- use Luna max for unusually difficult but still narrow/architecture-free implementation;
- use Terra high/xhigh only when the implementation itself requires broad bounded context integration.

A delegated work unit stays delegated until it returns, fails, or is explicitly re-routed. **No silent takeback:** Sol must not start implementing a Luna/Terra-owned unit because it appears convenient while waiting.

### 6. VERIFY / PRE-REVIEW — create independent evidence

Use Luna for targeted tests, builds, regression checks, and mechanical validation.

Use Terra high/xhigh for bounded cross-file review, regression-risk analysis, or synthesis when the change is context-heavy.

For a small local change, Sol may review directly. For a meaningful cross-file change, prefer one independent pre-review before final acceptance.

Allow at most one normal Luna ↔ Terra correction round:

```text
Luna implements
→ Terra pre-reviews
→ Luna performs one bounded correction
→ Sol accepts or escalates
```

Persistent disagreement, scope growth, or architecture questions return to Sol and usually to **ROUTE**.

### 7. SOL ACCEPT — final authority

Before completion Sol must:

1. inspect the actual final diff/state;
2. inspect critical evidence rather than every intermediate artifact;
3. verify relevant validation/test evidence;
4. reconcile material uncertainty or disagreement;
5. confirm architecture, contracts, and user constraints;
6. disclose remaining unverified conditions or risks.

Only the primary Sol agent declares final acceptance.

## Routing hard rules

### Mandatory delegation triggers

Delegate unless a Direct-work exception applies when any of these are true:

- broad code search, call-path tracing, or several unfamiliar files are needed;
- two or more independent evidence questions exist;
- behavior/interfaces are decided and implementation is bounded;
- logs, traces, docs, screenshots, scans, or test output can be processed outside Sol;
- a cross-file change benefits from an independent pre-review;
- Sol is about to spend substantial context gathering facts rather than making a decision.

### Direct-work exceptions

Sol may work directly when:

- the action is genuinely trivial with negligible context footprint;
- all required facts are already fully present in primary context and no fresh exploration is needed;
- the work inherently requires Sol authority: architecture, unresolved invariants, high-risk judgment, or final integration;
- subagent routing is unavailable;
- the user explicitly requests single-agent execution or forbids delegation.

## Model policy

### Luna — default leaf

Use `gpt-5.6-luna` only at **xhigh** or **max** in this skill.

**xhigh is the default** for:

- targeted search, mapping, symbol/call-site lookup;
- docs/API lookup;
- bounded code changes and explicit bug fixes;
- tests, type fixes, mechanical refactors, validation;
- repetitive/high-volume transforms;
- document OCR / visual transcription.

Use **max** only when the unit remains narrow and architecture-free but needs materially deeper local reasoning, or an xhigh attempt was incomplete because of reasoning depth rather than scope.

If scope becomes broad or decision-heavy, use Terra or Sol instead of stretching Luna.

### Terra — broad but bounded

Use `gpt-5.6-terra` only at **high** or **xhigh** in normal routing.

**high is the default** for:

- broad codebase or multi-file exploration;
- cross-module call-path mapping;
- synthesizing several Luna results;
- supporting-document/log/trace synthesis;
- bounded multi-module root-cause debugging;
- cross-file pre-review and regression-risk analysis;
- context-heavy but already-designed implementation slices.

Use **xhigh** for genuinely difficult bounded debugging, review, synthesis, or implementation whose architecture and correctness model are already fixed.

Avoid Terra max. If xhigh is insufficient, normally escalate to Sol.

### Sol — judgment boundary

Keep the unit with Sol when requirements, invariants, ownership, architecture, security policy, concurrency/transaction/recovery semantics, persistence compatibility, or other correctness boundaries are unresolved; when subagent findings materially conflict; or for final integration and acceptance.

Sol may still delegate narrow evidence gathering around a Sol-owned decision.

## Luna visual OCR / document transcription

Treat visual text extraction as a first-class Luna leaf task when a document contains scanned pages, screenshots, photos, handwriting, forms, unusual typography/layout, or unreliable/garbled parsed text.

### OCR route

```text
visual/scanned/non-standard document
→ Luna xhigh visual transcription/OCR
→ optional parallel Luna page/range leaves for large documents
→ Terra high synthesis if the document set is broad/context-heavy
→ Sol uses the distilled text/evidence for decisions
```

Use Luna **max** only for unusually difficult handwriting/layout where xhigh leaves unresolved transcription uncertainty.

For large documents, split independent pages or contiguous page ranges across a small parallel Luna wave when useful. Preserve original page/order identity so results can be recombined deterministically.

### OCR return contract

Ask Luna to:

- transcribe faithfully before interpreting;
- preserve page number, section/order, headings, table/form relationships when material;
- distinguish transcription from inferred reconstruction;
- mark uncertain text explicitly, e.g. `[uncertain: ...]` or `[illegible]`;
- avoid silently “correcting” names, numbers, dates, citations, identifiers, or handwriting;
- return only the relevant transcription plus uncertainty/evidence unless analysis is separately requested.

When exact wording matters, Sol/Terra should rely on page-referenced transcription and re-check only disputed/critical spans rather than visually rereading the whole document.

Do not force OCR for clean machine-readable text whose extraction is already reliable; use it where visual understanding adds value.

## Context firewall

The Sol thread consumes decisions and distilled evidence, not exploration exhaust.

- Keep raw grep output, stack traces, logs, OCR page text, and repetitive transformations in child contexts whenever possible.
- Return concise evidence packets with exact source locations.
- Do not paste entire child transcripts into Sol.
- Sol may inspect critical source material needed to arbitrate uncertainty.

**Primary invariant:** subagent capacity is cheap; Sol context is scarce.

## Native Codex orchestration

Use Codex native spawning, waiting, follow-up/steering, stopping, and thread closing rather than recreating a scheduler in prose.

Agent threads are separate contexts. Share only compact evidence/decision packets explicitly; do not assume parent, child, or siblings automatically share all context.

### Nested delegation

A Terra workstream may coordinate 2–3 Luna leaves when the runtime supports nested agents and decomposition is genuinely useful:

```text
Sol
└─ Terra: bounded lead
   ├─ Luna: narrow evidence/OCR
   ├─ Luna: narrow implementation
   └─ Luna: targeted validation
```

Sol fixes the workstream boundary and acceptance criteria first. Terra may synthesize and coordinate locally but never inherits Sol's architectural authority. Avoid deep agent trees.

## Shared-workspace safety

Assume agents share a working tree unless isolation is explicitly guaranteed.

- Parallelize independent reads aggressively.
- Parallelize writes only across clearly disjoint files/modules.
- Never assign the same file to concurrent writers.
- Serialize broad refactors, shared interfaces, migrations, and tightly coupled modules.
- Preserve pre-existing user changes.
- A worker stops and reports when the required fix exceeds its permitted scope.
- Sol inspects the diff before overlapping follow-up writes.

For large independent write streams, prefer separate top-level Codex worktree tasks.

## Architecture policy

For substantial new systems or refactors, prefer Modular Monolith + Vertical Slice + Ports & Adapters at real variation points; use DDD tactically only where domain complexity warrants it; keep KISS, explicit boundaries, low fan-out, and mechanical architecture tests where valuable.

Keep repo-specific boundaries, commands, conventions, and exceptions in applicable `AGENTS.md` files.

Sol decides architecture. Terra analyzes bounded consequences. Luna implements decided slices.

## Completion report

When mentioning subagents, summarize only:

- what was delegated;
- model class/effort;
- material findings or changes;
- validation;
- remaining risk.

Do not dump internal agent chatter.

For recommended Codex `[agents]` defaults and optional custom roles, read `references/codex-native-config.md` only when setup/configuration is relevant.
