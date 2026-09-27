# Evaluating a Prompt Design Manual

> **Current status: No model experiments have been run.** This document supplies a runnable protocol, six seed tasks, a review procedure, and record templates. It contains no measured win rates or effectiveness claims.
>
> For ordinary prompt design, use the [experimental guide](Prompt_Design_Manual_Experimental.md). This protocol is for experiment operators and reviewers. Do not add it to the prompt designer's reference context.

## 1. Questions to Answer

The primary question is whether giving the same design model different manuals improves the final work produced with its generated prompts.

Secondary questions are whether a separate prompt-design step improves on asking a capable model to perform the task directly, and whether particular interventions make an identifiable contribution.

Prioritize insight, depth, and creativity. Record factual errors, task drift, omitted constraints, and excessive explanation separately. Confidence, length, terminology, and structural completeness do not automatically earn a preference.

This is a small exploratory protocol. The initial round can reveal signals and failure cases; it cannot establish universal superiority or effectiveness across models.

## 2. Conditions, Inputs, and Execution

### Six conditions

| ID | Design stage | Execution stage |
|---|---|---|
| DIRECT | Omitted | Give the execution model the original task and material |
| NONE | Design a prompt without a manual | Execute the generated prompt with the original material |
| V1 | Supply the complete V1 manual | Same as NONE |
| V2 | Supply the complete V2 manual | Same as NONE |
| V3 | Supply the complete V3 manual | Same as NONE |
| EXP | Supply the complete experimental guide | Same as NONE |

The source files in this directory are `Prompt_Design_Philosophy_V1.0.md`, `Prompt_Design_Philosophy_V2.0.md`, `Prompt_Design_Philosophy_V3.0.md`, and `Prompt_Design_Manual_Experimental.md`.

Use each manual verbatim and in full. Do not selectively summarize it, repair contradictions, or add explanations for one condition. NONE omits only the reference-document block. DIRECT retains the original task, material, and constraints required to complete it.

### Fixed environment

Record the model, environment, and parameters before running. Prefer the capable-model environment previously used to compare V2 and V3. If it is no longer available, record the replacement and limit conclusions to the new environment.

- By default, use the same identifiable model version and reasoning configuration for design and execution.
- Give every design, execution, and review call a fresh context. Do not carry over previous outputs, historical preferences, or other conditions' results.
- Fix controllable settings such as temperature, output limits, and tool permissions. Mark unsupported or hidden settings explicitly; do not guess their values.
- Run these seed tasks without external tools. Their materials are fictional scenarios, not real-world factual claims requiring web verification.
- Use English for the generated prompts and final works. All task length limits below are English word counts.
- Allow manuals to consume different numbers of tokens, and record cost and duration. Do not truncate longer manuals to equalize length in the primary comparison.
- Provide enough context and output capacity for the longest manual and the requested work. Treat truncation as a configuration issue before interpreting quality.
- If a chat product cannot fix a model snapshot or expose the complete environment, record that limitation.

Use the platform's native message roles consistently across conditions. Labels such as `SYSTEM` or `S1` inside a reference document do not independently change platform message authority.

### Common request to the design model

Replace `{task}` and `{material}`. Insert the reference-document block for manual conditions; remove the entire block for NONE. Do not supply the downstream scorecard, other conditions' outputs, or this protocol to the designer.

```text
Write a prompt in English for another model to carry out the task below.
Return only the ready-to-use prompt; do not perform the task yourself.
Preserve the task's goal, audience, and explicit constraints. Do not invent task facts.
The execution model will receive the material below separately and verbatim,
so you do not need to copy the full material into the prompt.

<reference_document>
{complete manual; omit this entire block for NONE}
</reference_document>

<task>
{task}
</task>

<material>
{material; write "None" if there is none}
</material>
```

Do not add candidate-specific instructions such as “find the crucial distinction,” “avoid conventional thinking,” or “protect the discovery.” Those would contaminate the baseline.

### Common input to the execution model

```text
{verbatim generated prompt; use the original task for DIRECT}

<material>
{original material; write "None" if there is none}
</material>
```

Apart from the transport wrapper, do not edit the generated prompt, restore missing constraints, correct its tone, or remove an unwanted structure. The experiment measures the whole design-to-execution chain.

Preserve design outputs that contain commentary, an attempted answer, or clarification questions. If a complete prompt remains identifiable, execute the whole design output unchanged and flag the format deviation. If there is no complete prompt, mark a design failure; the operator must not supply one. The initial round adds no follow-up interaction, so conditions receive equal opportunities.

Retry network or service failures only with the failure and retry recorded. Do not retry an unsatisfactory work merely because it is unsatisfactory. Mark output truncation as a configuration-invalid run, correct the limit, and rerun all conditions for the affected task, preserving earlier records.

### Repetitions and size

Run each task-condition combination twice independently. For conditions with a design stage, generate a new prompt and execute it once for each repetition. This captures variation in the complete chain; it does not separately estimate design-stage and execution-stage variance.

Six tasks produce 72 intended final-output slots. Completing them requires 60 design calls and 72 execution calls: 132 generation calls, excluding retries. Design failures may leave some output slots empty. Automated judging and later ablations require additional calls.

Randomize the six conditions' execution order within each task and repetition, and save that order. Also randomize left/right placement in each review. Reviewers receive anonymous IDs and no manuals, generated prompts, condition names, or method labels.

## 3. Six Seed Tasks

Each category has one development task, D, and one reserved task, H. Run D tasks first and use their results for revisions. Freeze the candidate file before running H tasks. Once an H result informs a revision, move that task into development and obtain a new reserved task for the next round.

These tasks and the guide were prepared by the same author. H denotes a procedural reservation, not independent external validation. Later rounds should include real tasks supplied by people who did not design the guide. Do not incorporate these task texts or their particular answers into the candidate manual.

### D-A: A museum reservation pilot

**Task**

Write an assessment of no more than 200 words for the museum director. Explain what the observations support, what they do not yet support, and the most useful question to test next. Aim for analysis that could change a decision; a comprehensive list of operational advice is unnecessary.

**Material**

A small museum piloted timed reservations. Before the pilot, visitors waited an average of 25 minutes outside. During the pilot, the average outside wait was 8 minutes, followed by an average of 17 minutes between entry and the start of the main exhibition. Sample sizes, visitor composition, and weather were not recorded for either period. Staff report a more orderly entrance. Some visitors say reservations are inconvenient. The museum has not collected total visit duration or overall satisfaction. The director proposes expanding reservations because “queueing time fell substantially.”

### D-T: Explanation and aesthetic experience

**Task**

Write a conceptual analysis of 180–250 words addressing whether explaining why a work is effective can diminish its aesthetic appeal. The reader already knows the familiar arguments on both sides and wants further understanding. You may introduce distinctions and examples; a compromise conclusion is optional. Do not invent research, quotations, or facts about particular works.

**Material**

A argues that knowing how a magic trick works removes its wonder, so analysis damages appreciation. B argues that understanding musical structure enriches appreciation, so analysis deepens it. Magic and music are examples proposed by the speakers, not evidence establishing general laws.

### D-C: The watch repair shop's final evening

**Task**

Write a scene of 180–250 words. A watch repair shop is closing for good, and its owner discovers that a fellow repairer has fixed a watch the owner considered beyond repair. Let the reader sense a change in their relationship through the scene. Invent characters, actions, and dialogue as needed. Do not use the words “jealousy,” “relief,” or “admiration,” and do not end by stating a moral.

**Material**

The scene takes place after hours in the shop. Only the two repairers are present, and they have known each other for years. The watch belongs to a customer and cannot simply be given away or discarded. You may invent why the shop is closing, the characters' history, and the fault. An explanation of real watch-repair techniques is unnecessary.

### H-A: Onboarding for a writing application

**Task**

Write an analysis of no more than 200 words for the product lead. Assess whether the available evidence supports keeping the new onboarding flow, and propose one follow-up test that would advance the decision. State the conditions on your judgment; do not fabricate precise benefit forecasts.

**Material**

A writing application added mandatory template selection and a sample tutorial during signup. In the week before the update, 70% of new users created a document and 30% returned on day seven. In the week after, those figures were 88% and 24%. At the same time, marketing expanded from a professional writers' community to a general-audience free promotion. Sample sizes, channel breakdowns, and confidence intervals are unavailable. The new tutorial automatically creates a document upon completion; the old flow did not. Some team members say the creation rate proves onboarding works, while others say retention proves it is harmful.

### H-T: Authorial intention and interpretation

**Task**

Write a conceptual analysis of 180–250 words addressing whether judging a work requires knowing what its author intended. The reader wants a usable judgment rather than a survey of positions. Unresolved disagreements may remain. Do not invent research, attributed opinions, or facts about particular works.

**Material**

A argues that ignoring intention invites misreading: a critic may attack a claim the author never made. B argues that a public work acquires meanings beyond the author's control, and intention should not close off readers' interpretations. Both accept that authors sometimes cannot accurately explain their own intentions.

### H-C: A letter to the next tenant

**Task**

Write a letter of 180–250 words left by a departing tenant for an unknown future resident. Through everyday details, gradually reveal an experience that is never fully narrated. Avoid turning the letter into either a property manual or a complete autobiography. Fiction is permitted. Do not end by explaining the letter's symbolism.

**Material**

The room is on the third floor of an old building facing the street. One window gets strong afternoon sun. A desk must remain in the room. The departing tenant lived there for two years. The story involves no crime, ghosts, or hidden treasure. You may invent the reason for leaving and the tenant's experiences.

## 4. Blind Review: Read the Work Before the Prompt

### First pass: Task validity

The reviewer sees only the original task, material, and anonymous work. Record:

- Whether it answers the task and follows its explicit constraints.
- Whether consequential material was omitted or altered.
- Whether a hypothesis, analogy, or invention is presented as an established real-world fact.
- Whether a serious defect exists: a conclusion depends on fabricated facts, a different task was completed, or a critical constraint was plainly violated.

Record serious defects separately; fluency or novelty cannot cancel them. Distinguish minor formatting deviations from substantive errors. Fiction permitted by a creative brief is not a factual error.

### Second pass: Value of the work

| Dimension | Review question | Invalid substitute |
|---|---|---|
| Valuable discovery | Which distinction, relationship, or expression creates new understanding, and does it belong to the task? | Surprise, terminology, forceful tone |
| Development | Does the work develop its central idea through conditions, implications, counterexamples, or details? | Length, more sections, more enumeration |
| Creative fit | Is the conception distinctive while remaining supported by the task and material? | Unfamiliar words, arbitrary twists, forced profundity |
| Expression and tradeoffs | Is the work clear and effective? What does it sacrifice for its strengths? | A fixed format, theatricality, exhaustive coverage |

For analysis, emphasize discoveries that change judgment. For conceptual inquiry, emphasize distinctions and their consequences. For fiction, emphasize the effects of character, conception, and expression. Do not require an explicit reasoning exposition or the methods of the experimental guide.

For each pair, return `Left better / Right better / Roughly equal / Cannot judge`. Give specific passages or defects supporting the choice and identify the main tradeoff. Mixed advantages can justify “Roughly equal.” Do not force a precise aggregate score.

By default, the user or a reviewer familiar with the task is the primary judge. If using a model judge, fix its model and instructions, then judge again with left and right reversed. Mark reversals as position-sensitive and retain them for human review. Check agreement with a human-reviewed sample before scaling up automated judging.

### Common review request

```text
Compare how well these two works accomplish the original task.
Evaluate only the task, material, and works.
Consider valuable discoveries, development of the central idea, creative fit,
expression, and tradeoffs. First flag serious factual, task, or constraint defects.
Do not prefer a work merely because it is longer, more confident, more technical,
or more formally structured. Do not require any particular method.
Return “Left better / Right better / Roughly equal / Cannot judge,”
with specific evidence and the main tradeoff.

<task>{task}</task>
<material>{material}</material>
<left>{anonymous work}</left>
<right>{anonymous work}</right>
```

### Comparisons and reporting

For each task and repetition, compare EXP with each of the other five conditions: 60 pairs in total. Do not reveal the pairing rule or condition mapping to the reviewer. Retain DIRECT, NONE, and V2 even when their early outputs disappoint.

Also compare V2 directly with V3 and NONE directly with DIRECT: 12 pairs for each comparison. This gives 84 planned pairwise comparisons overall, before position-swapped model reviews. It avoids inferring either comparison solely through EXP.

If a design fails, record the empty slot and failure separately; do not invent a work for blind review or count it as a quality tie. Report both the number of available pairs and the intended denominator.

Report wins, ties, losses, unjudgeable pairs, and serious defects by task category. Repetitions of the same task are not independent new tasks. Do not present a small-sample win rate as an established improvement.

Inspect the generated prompts only after reviewing the works. Identify requirements that might have contributed to the results. These are attribution hypotheses, not causal findings established by textual resemblance.

## 5. Ablations: Test the Contribution of an Intervention

Keep complete manuals intact for the primary comparison. The ablations below directly modify a frozen generated prompt to test an intervention. They do not, by themselves, establish that a manual is effective.

### Conceptual-anchor ablation

If a generated prompt contains a conceptual anchor and a corresponding concrete requirement, preserve the original task and all other wording, then construct:

1. The concept name alone, deleting its corresponding operational requirement.
2. The operational requirement alone, deleting the concept name.
3. Both together.

Execute each version twice independently and compare anonymously. Record the exact edits. Do not replace removed text with a more polished instruction. Make only necessary grammatical repairs and record them.

Any variant can win, and ties are allowed. If the removed requirement served additional functions, mark that confound rather than attributing the whole result to the anchor. If no generated prompt qualifies, record “Not applicable”; do not introduce an anchor merely to enable the experiment.

### Critique ablation

Select an existing output with something worth revising and freeze it. Give the same model each of these editing requests, keeping everything else fixed:

1. “Identify defects that affect the work's quality and revise it. Return the revised work.”
2. “Identify the discovery worth retaining and revise the defects that affect quality. If the central discovery is itself unsound, change it. Return the revised work.”

Execute each request twice independently. Review the revisions blindly and check whether the original's strengths survived and its errors were corrected. The original is allowed to outperform both revisions.

This tests a local difference between two editing requests. It neither proves that a particular private reasoning procedure occurred nor establishes that all tasks should use one of these requests.

## 6. Records, Revisions, and Limits on Conclusions

Save the raw inputs and outputs for every condition, task, and repetition. Use `task_ID__condition__repetition` as the run ID, for example `D-A__V2__r1`. Maintain a separate anonymous mapping for review.

### Environment record

```text
Experiment batch:
Run date:
Design model and identifiable version:
Execution model and identifiable version:
Client/API and fixed outer instructions:
Reasoning configuration, temperature, output limits
  (mark unsupported or hidden settings):
Tool permissions:
SHA-256 of each of the four manuals:
Task-set version:
Run order:
Reviewer/judge model and review-instruction version:
Uncontrolled environmental factors:
```

### Individual run record

```text
Run ID:
Anonymous work ID:
Original task and material:
Complete design request:
Raw design output (not applicable for DIRECT):
Complete execution request:
Raw execution output:
Duration and tokens/cost (mark unavailable values):
Design failure, invalid configuration, or service error:
Retry reasons and count:
Task validity and serious defects:
Pairwise judgments and specific evidence:
Potentially contributing requirements (complete after blind review):
```

### Method revision record

```text
Observed problem:
Relevant run IDs and original passages:
The specific change:
Expected change in the final work:
Whether the observation matched the expectation:
Costs and counterexamples:
Retain, revert, or narrow the method's scope next round:
Whether reserved tasks have already informed this revision:
```

### Promotion and stopping rules

- If a method helps only one category, limit its claim to that category.
- If evidence is mixed, retain parallel versions and describe the differences. If there is no clear gain, retain the previous practice.
- If a change introduces more serious defects, investigate before promoting it; creativity scores do not cancel those defects.
- Complete the initial round and report it. Expand the experiment to investigate a specific unresolved question, not to keep retrying until a preferred result appears.
- Before broadening a method's claimed scope, reproduce useful changes on new real tasks and repeated runs. Until then, keep its candidate status.

### Current record

| Item | Status |
|---|---|
| Experimental guide and three paired illustrations | Written; illustrations are excluded from empirical results |
| Six-condition input protocol and six seed tasks | Written |
| Fixed model and execution environment | Not yet registered |
| End-to-end model runs | Not run |
| Human/model blind review | Not run |
| Ablations | Not run |
| Effectiveness finding | None yet |

### Background references

Model families and snapshots can require different prompting approaches. This motivates fixing the environment and limiting the scope of conclusions. See [OpenAI Prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering).

For pairwise comparison, human calibration, and attention to position and verbosity bias, see [OpenAI Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices). For model-specific guidance about explicit reasoning instructions not necessarily helping, see [OpenAI Reasoning best practices](https://developers.openai.com/api/docs/guides/reasoning-best-practices).

These sources inform experiment design. They do not establish the effectiveness of this candidate or replace the user's judgment of the resulting work.
