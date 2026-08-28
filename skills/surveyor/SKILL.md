---
name: surveyor
description: Shapes a repository so a coding agent can change one part of it safely without loading the whole thing. Use whenever someone is starting a codebase that agents will maintain, or complains that an agent keeps breaking unrelated code, duplicating helpers, or touching a dozen files for a small change — and also when they ask where module boundaries should go, how to structure a growing project for AI, what to put in AGENTS.md or CLAUDE.md, or how to stop architecture from rotting. Output is a repository map of facts plus at least one command that fails on a boundary violation. Do NOT use this to decide what to build or plan a feature (that is the producer skill), to review a specific diff, or as a general source of design advice — this shapes the environment, not the work.
---

# Surveyor

The failure this prevents: an agent is asked to add one field to the export format. It reads forty files, edits nine, breaks two tests in a module it never opened, and adds a date helper to `utils/` that duplicates one already sitting in `common/`.

None of that is a reasoning failure. The repository made the wrong change easy to make and the right one hard to find. Surveyor changes the repository, not the agent.

## Step 0 — Decide whether to run at all

Skip it, say nothing about it, and just do the work when:

- The project is under roughly ten source files. Structure costs more than it saves.
- The user asked for a specific feature or fix. Boundary work is not a prerequisite for typing.
- There is no repository yet and no code — the question is what to build. That is `producer`.
- Boundaries already exist and a check already enforces them, and the complaint is about something else.

Run it when a change that should be local isn't, or when someone is about to create the structure that will decide this for the next two years.

**Budget: one new level of structure and one new command.** If the plan involves moving most of the files, it is the wrong plan — read `retrofit.md`.

## The one rule that governs everything else

Every sentence you are tempted to write into a repository instruction file is a fact, a rule, or an opinion.

| | What it is | Where it goes |
|---|---|---|
| **Fact** | True here, false elsewhere. "Auth lives in `modules/identity`." "Checks run with `make check`." | The map |
| **Rule** | Must never happen, and something breaks when it does. "`training` must not import `inference` internals." | A check. Prose only as a comment on the check |
| **Opinion** | True everywhere. "Prefer composition over inheritance." "Don't over-abstract." | Nowhere. Delete it |

Two tests decide which one you're holding:

- **Could this be false in a different repository?** If no, it's an opinion.
- **If someone violates it, does a command fail?** If no, it's an opinion in the imperative mood.

Deleting opinions is not tidiness. A capable model already holds them, so they carry no information — and they sit next to the facts, which the model *cannot* recover on its own, competing for the same attention. A repository manual that opens with three paragraphs of sound general advice has taught the agent that the file is skippable, and the agent is right.

This rule is also why this skill contains almost no design advice. Apply it to anything you are about to add here, too.

## Where boundaries go

The common mistake is cutting by **kind of code** instead of by **reason to change**. `controllers/ services/ repositories/ models/` is a filing system, not a set of boundaries: nearly every feature touches all four, so the agent must load all four, and the boundary protects nothing while costing four directories of navigation.

Cut where change stops propagating. Two tests for a proposed boundary:

> **The three changes test.** Name three changes plausibly coming in the next few months. If two or more cross the boundary, it is in the wrong place.

> **The local reading test.** Can a change inside this boundary be made correctly by someone who has read only this directory and the public contracts of its neighbors? If no, the boundary is decorative.

With git history the first test is measurable instead of guessed — files that change in the same commits belong on the same side. `retrofit.md` has a script.

A boundary is not a folder name. It consists of:

- a directory owning one capability;
- a public surface — one file or package that names everything exported;
- an internal region nothing outside may import;
- its tests, adjacent;
- a declared list of what it may depend on.

Only the last two make it real. The first three are naming conventions until something enforces them.

## How much structure

You must be able to name the event that pushed you up a level. "It might grow" is not an event.

| Level | Shape | Event that justifies moving up |
|---|---|---|
| **L0** | flat `src/` + `tests/` | One file does two jobs that change on different schedules |
| **L1** | `modules/` by capability, public surface each | Two capabilities with different dependencies or lifecycles |
| **L2** | ports at the edges | A second implementation exists now, or the dependency is external, unstable, or hard to test |
| **L3** | domain model inside one module | Real invariants, state transitions, policies — not CRUD |
| **L4** | separate deployables | Independent release, scaling, or security boundary is actually required |

Never skip a level in anticipation. Moving up late costs one refactor; moving up early costs a tax on every change forever, and the refactor anyway when the guess turns out wrong.

L3 and L4 apply to *one module at a time*. A repository is usually L1 with one module at L2 and nothing at L3.

## The artifact

Produce four things, and no more:

1. **Root `AGENTS.md`** — the map. Facts only, one screen. Template in `templates/ROOT_AGENTS.md`.
2. **Module `AGENTS.md`** — only for modules a newcomer would get wrong. Template in `templates/MODULE_AGENTS.md`.
3. **One command** that fails on a boundary violation.
4. **The dependency policy**, in whatever machine-readable form the language offers.

Order both instruction files by **reread frequency**, not by narrative. Commands and hard rules at the top — they get read every session. Rationale and history at the bottom, or nowhere.

**Definition of done:** write a forbidden import on purpose, run the command, watch it fail, then delete the import. A check that has never failed is not known to work — a misconfigured path glob silently passes everything, and that is the most common outcome of adding architecture tests.

## Enforcement

Prose enforces nothing. Pick the cheapest mechanism that fails the build:

1. **The language.** Go's `internal/`, Rust's crate graph and `pub(crate)`, package-private visibility. Free, zero config, cannot be bypassed or misconfigured.
2. **Build or lint config.** import-linter, dependency-cruiser, depguard.
3. **A test that inspects the source.** When nothing above fits.
4. Prose. Not an option.

Prefer 1 over 2 harder than feels natural. A large share of the boundaries people reach for architecture tests to protect could just be a directory the language already refuses to let you cross.

Working configurations, one file per language — read only the one you need:

- `enforcement/python.md` — import-linter contracts
- `enforcement/typescript.md` — dependency-cruiser, package exports
- `enforcement/go.md` — `internal/`, depguard
- `enforcement/rust.md` — workspace crates
- `enforcement/fallback.md` — a ~30-line import-walking test for anything else

## Existing repositories

Do not rewrite. Read `retrofit.md`. The short version: declare the boundary you want, count the violations that exist today, and fail the build only when the count goes **up**. That converts a six-month migration into something that starts protecting you this afternoon, and it lets an agent do the cleanup incrementally without a flag day.

## Self-check before you finish

- Did I write anything that would be equally true in someone else's repository? Delete it.
- Is there a rule stated in prose that no command checks? Either make it executable or drop it.
- Did I make the check fail on purpose and watch it fail?
- Did I add structure without being able to name the event that required it?
- Could an agent correctly change one module having read only that module and its neighbors' contracts?
- Does every directory have an owner and a reason to change, or did a `shared/` appear because two things looked alike?
- Is root `AGENTS.md` longer than one screen?
