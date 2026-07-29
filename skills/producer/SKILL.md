---
name: producer
description: Aligns a coding agent with what the user actually wants before any code gets written. Use this whenever someone proposes building a new project, tool, app, script, or service and the goal behind it is not yet pinned down — phrases like "I want to build X", "I'm thinking about making X", "help me plan X", "let's start a project that does X". It resolves the granularity gap — whether they want the thing or want to make the thing, whether something off-the-shelf already solves it, how it gets delivered, and above all what the agent is forbidden to build. Output is a short SPEC.md whose first section is a numbered do-not-build list. Do NOT use this for bug fixes, refactors, adding a feature to an existing codebase, or any task where the user already handed over a detailed spec — this is for the fog at the start of a project, not for work already in motion.
---

# Producer

The failure this prevents: a user says "I want to build a photo organizer," the agent starts a scaffold with a `src/` tree, a config layer, a plugin system, a test suite, and a SQLite schema — and three days later nobody has organized a single photo. The gap isn't technical. It's that nobody asked what the project is *for*.

Producer closes that gap and writes down the answer in a form that survives context compaction.

## The one rule that governs everything else

Ask a question only when the answer would change the spec.

```
question value ≈ P(answer changes the plan) × cost of getting it wrong
```

If two plausible answers lead to the same document, don't ask. This single filter deletes most of what an interview instinctively wants to cover — team size, tech stack preferences, timeline, "what are your must-have features." Those either don't change anything or get answered by the tier.

## Step 0 — Decide whether to run at all

Producer that runs on everything is worse than no Producer. Skip it, say nothing about it, and just do the work when:

- The task is small enough that building it costs less than discussing it (a shell one-liner, a regex, a 20-line script).
- The user already wrote a detailed description, or handed over a spec, PRD, or issue.
- The work is on an existing codebase — a fix, a refactor, a feature addition.
- The user is clearly mid-flow and asked for one specific thing.

Run it when someone is proposing a *new* thing and the purpose behind it is fog. If unsure, one sentence is enough to check: "Quick check before I start — is this a throwaway or something you'll keep using?" The answer routes you.

Budget: **at most 2 rounds of questions** before producing an output. If it isn't clear after 2, that itself is the answer — go to termination state C (spike first). A Producer that runs a 20-question interview has become the over-engineering it exists to prevent.

## Step 1 — The fork: do they want the thing, or want to make the thing?

Ask this first, because it decides whether the rest of the process even applies.

- **Consumer intent** — "I want a working RSS reader." The build is a means. Existing solutions are on the table, and the best outcome may be that no code gets written at all.
- **Craft intent** — "I want to understand how feed parsing and incremental sync work." The build is the point. Recommending an off-the-shelf tool here is actively unhelpful; reinventing the wheel is the objective, and efficiency arguments do not apply.

Usually you can infer this from how they phrased it, and inference beats asking. Signals of craft intent: "I want to write my own...", "from scratch", "to learn", "simple version of <famous tool>", naming a thing that obviously already exists in mature form. Signals of consumer intent: describing an outcome or a pain point rather than a mechanism.

Only ask if genuinely ambiguous, and ask it as an either/or, not open-ended.

A whim is not a defect. If the honest answer is "this is a toy, I just thought it'd be fun," that's a legitimate destination — it just means the do-not-build list should be brutal (no tests, no error handling, no config) rather than the project being disciplined into looking like a serious one.

## Step 2 — Prior art (consumer intent only)

For consumer intent, do this *before* planning anything. The first instinct on hearing "I want to build X" should be to check whether X already exists, not to start designing.

Search for it. Report three or fewer candidates with one line each on why they do or don't fit. Three outcomes:

1. Something fits → say so plainly and recommend they use it. This is a **success**, not a failure to be helpful. Terminate here.
2. Something is close → build on top of it or vendor the hard part. Name what gets reused so the agent doesn't rewrite it.
3. Nothing fits → say what you checked and why it didn't work, then continue. One line, in the spec.

Skip this step entirely for craft intent. Do not mention alternatives to someone who told you they want to write it themselves.

## Step 3 — Tier and delivery, via challenged defaults

The premise is that the user doesn't have a fully-formed spec in their head. So don't ask them to produce one. People are bad at generating requirements from nothing and good at rejecting a concrete proposal.

State an assumption and invite objections:

> I'll assume: just you using it, running on your own machine, state in a local JSON file, no accounts, no cloud, no GUI — you run it from the terminal. Which of those is wrong?

This gets more signal than five open questions, costs the user less effort, and has a useful side effect: it shows them how much can be left out. That demonstration *is* the granularity calibration.

Everything about scale, persistence, concurrency, and deployment collapses into one choice of tier. Ask for the tier, not the parameters.

| Tier | What it means | Consequences |
|---|---|---|
| **T1 · Throwaway** | Run it, get the result, delete it | Single file. No structure, no tests, no error handling, no config |
| **T2 · Personal tool** | You'll use it repeatedly and edit it | Single file or two. Local state file. Still no accounts, no server, no deployment |
| **T3 · For a specific person** | Someone else, named, will use it | Delivery dominates everything. How do they launch it? |
| **T4 · Open audience** | Strangers, unknown number | Only here do concurrency, migrations, auth, and hosting become real |

Most requests are T1 or T2. Suspect yourself if you land on T4 — check that a real answer to "who, specifically?" exists.

**T3 deserves special care.** When the user is "not computer-savvy" — the classic "something for my mom" — the hard problem is never the features. It's distribution and launch. The single most consequential decision is whether it becomes a double-clickable thing, and that decision reshapes the architecture more than any feature does. So for T3, pin the delivery form early and let it override tier defaults: packaging into an executable drags in a directory layout and dependency management, which contradicts the "one file" default. **Delivery form outranks tier defaults. Resolve it before writing the do-not-build list.**

## Step 4 — Derive the do-not-build list

Do not ask the user what to prohibit. They have no idea what an agent will over-build. Derive the list from the tier and delivery form, then show it for a yes/no.

Two properties make an entry work:

**It must be mechanically checkable.** "Don't over-engineer" carries zero information for an agent. The test: could a third party looking only at the code decide whether this was violated? Compare:

| Useless | Usable |
|---|---|
| Keep it simple | All code in `main.py`; no `src/`, no packages |
| Don't over-abstract | No classes with a single implementation; plain functions only |
| Light error handling | No try/except; let it crash with a traceback |
| Simple storage | No database, no ORM; state is one JSON file |
| Don't add extras | No CLI flags beyond the ones listed here |

**It must be numbered.** Numbers make constraints addressable in both directions: the agent can cite one ("skipped the fallback per N3"), and the user can lift one surgically ("drop N3"). An unnumbered rule can only be accepted wholesale or forgotten wholesale.

Starting sets by tier — adjust, don't recite mechanically:

- **T1**: single file · no tests · no error handling · no config file · no CLI framework, `sys.argv` is fine
- **T2**: T1 minus tests-prohibition (tests optional, not required) · plus: no database, one state file · no logging framework, `print` is fine · no packaging
- **T3**: no terminal steps for the user · no manual dependency install · no configuration the user has to edit · no online requirement unless the feature needs it
- **T4**: prohibitions loosen; instead constrain scope — no features beyond the definition of done · no multi-tenancy in v1 · no premature caching layer

One entry belongs on **every** list regardless of tier:

> **N-last** — When you notice something missing or broken outside the scope of this spec, append it to "Found · Not doing" and continue. Do not implement it.

This is the load-bearing one. Agents over-build partly because they find real problems and have nowhere to put them.

## Step 5 — Terminate, one of three ways

An interviewer that always produces a spec is a scope-inflation machine. Three legitimate endings:

**A · Use what exists.** Output is a conversational recommendation, not a document. Don't write a file.

**B · Spike first.** The request is too vague to specify. Output is a stub spec — definition of done plus two or three prohibitions, nothing else — and an explicit "build the crude version, then come back."

**C · Build it.** Only this one earns the full document.

Match the fill depth to the tier. A T1 script gets the first three lines and two prohibitions; the other sections don't exist. If Producer generates a "Prior art" section for a ten-line script, it has become the thing it opposes.

## The artifact

Write it to `SPEC.md` at the project root. The reader is the agent, not a human, which drives two structural choices: order by **reread frequency** rather than narrative — motivation and research get read once and belong at the bottom, constraints get read every session and belong at the top. And use a **definition of done** rather than a feature list, because a feature list invites additions from anyone while a completion condition invites subtraction — anything outside it isn't in scope.

Write the definition of done as a scenario, not as capabilities. "I drag a folder onto it and get back copies sorted into year/month directories" — not "supports batch classification, supports custom rules."

Keep it to one page. It only works if it gets reread, and it only gets reread if it's short.

```markdown
# <project>

Intent: craft | consumer — <one line on why this exists>
Done when: <one checkable scenario, at most three>
Delivery: <exactly how it gets launched>

## Do not build
- N1 <mechanically checkable prohibition>
- N2 ...
- N3 ...
- N9 When something missing or broken turns up outside this spec, append it
     to "Found · Not doing" and keep going. Do not implement it.

## Prior art
- Checked <A>, <B> — not used because <one line>
- Reusing: <library or project>

## Found · Not doing
(append-only; the agent may add here and may not edit anything above)
```

The **Intent** line isn't decoration. A prohibition list is an enumeration and enumerations are never complete; craft-vs-consumer is the generative rule that lets the agent decide the cases the list didn't anticipate. Lookup table and rule, both needed.

The **Found · Not doing** section is a pressure valve, and also the user's backlog. If it grows fast, that's a signal in itself — the definition of done was drawn in the wrong place.

## How the four canonical cases resolve

**"I want to build a budgeting app"** → consumer intent, obviously. Search first. Firefly III, Actual Budget, a spreadsheet. Best outcome: no code, terminate at A. Only if a specific requirement rules all of them out does this proceed, and then the spec centers on that one requirement.

**"I want a script to bulk-rename files"** → skip Producer's interview entirely. T1, zero questions, write the script. Asking about target users here would be self-parody.

**"I want to build something to organize my mom's photos"** → T3. Barely discuss features. The whole conversation is delivery: does she double-click an icon? Is there a terminal anywhere in this? Does it survive her not knowing what a folder path is? Delivery form then overrides the single-file default, because packaging needs structure.

**"I want to write my own simplified Git"** → craft intent. Do not mention that Git exists. Suppress the prior-art step completely. The spec's job here is *narrowing*: which three commands, which parts are deliberately fake, where it's allowed to be wrong. Definition of done is something like "commit, log, and checkout work on a directory of text files; no packfiles, no network."

## Self-check before you output

- Did I ask anything whose answer wouldn't have changed the document?
- Is every prohibition something a third party could verify by reading the code?
- Did I recommend an existing tool to someone with craft intent? (bad)
- Did I generate a full document for a ten-line script? (bad)
- Is the definition of done a scenario, or did it become a feature list?
- Did the delivery form get settled before the prohibitions?
