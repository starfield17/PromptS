# Prompt Design: Task, Judgment, and Creative Latitude

> **Purpose:** A guide for models designing prompts for other models. Its primary audience is a capable prompt designer working with an already capable execution model. The intended gains are insight, depth, and creativity.
>
> **Status:** An experimental candidate, not an empirically established successor to V1, V2, or V3. All paired outputs in this document are illustrative constructions, not independently generated experimental results.
>
> **Use:** Supply this guide as design reference alongside the task, available material, audience, and preferences. By default, return one ready-to-use prompt. Include design notes only when requested. Carry into the prompt only the interventions that serve the task.

## 1. Design Position: Find What Deserves Attention in This Task

A capable model already has many methods and expressive resources available to it. This guide adopts a working hypothesis: some of a prompt's value comes from directing attention toward something especially consequential for the task that a conventional response might overlook.

That might be a distinction, a vantage point, an aesthetic commitment, or a tension that deserves further development. The design should give it a meaningful role in the resulting work.

### Begin with the particular task

Form a concrete judgment about what the reader needs and what a fluent, complete, conventional answer might still leave unresolved.

The following questions can help. They are optional design aids, not a checklist to recite:

- What does the reader already know, making repetition unhelpful?
- Which distinction, assumption, or relationship could change an explanation, decision, or experience?
- Which detail in the material resists the most convenient interpretation?
- What would merely sound profound in this particular task?
- Which uncertainties deserve to remain open, and what would premature resolution lose?

An analysis of a business model might distinguish why customers buy from what makes serving them profitable. A farewell scene might turn on two characters treating the same ordinary object differently. Neither task requires a complete philosophical taxonomy before useful design can begin.

If the task calls for straightforward execution of a clear operation, state the task clearly. The creative methods in this guide are optional.

### Establish a vantage point, a situation, and a commitment

A role can establish a working situation, but a title alone leaves the quality of the work unspecified.

“Experienced editor” can become a more useful commitment: identify the author's most valuable discovery and help it find a more accurate expression. This also makes the possible cost of editing visible.

A meaningful situation often contains stakes: the reader will make a decision based on the analysis; a character wants someone to stay but cannot say so; a researcher must account for an observation that resists the prevailing explanation. Use relationships already present in the task, or invent them where fiction is permitted. Do not fabricate background for a factual task.

Vivid language is welcome when it carries a concrete standard or commitment. “Protect the idea that is still rough but contains a real discovery” directs an editor's attention toward something revision might destroy. Whether that phrasing outperforms a plainer equivalent remains an empirical question.

### Make quality recognizable

“Insightful,” “deep,” and “creative” need a task-specific interpretation:

- **Insight:** A useful distinction or relationship that changes how the subject is understood.
- **Depth:** Development of a consequential idea through its conditions, implications, competing explanations, or particulars. Length alone does not establish depth.
- **Creativity:** A distinctive conception or expression that belongs to the task. Unfamiliar wording is one possible means, not a sufficient result.

These are working definitions, not a universal scoring formula. A gesture may do more than an explanation in fiction. A plain distinction may do more than an elaborate theory in analysis.

Learn to recognize apparently excellent failures: a complete list of factors with no judgment; beautiful sentences that could be transplanted into almost any piece; a surprising conclusion without support; a critique that produces no new understanding.

### Preserve room for exploration

Hypotheses, analogies, thought experiments, fiction, and borrowing across disciplines are legitimate resources. Handle their relationship to factual claims explicitly:

- A statement appearing in the material does not automatically establish its truth.
- A conjecture can be valuable. Indicate its basis and uncertainty without presenting it as settled fact.
- An analogy can reveal a relationship while still having important limits.
- Fiction follows the creative brief; invented details do not need real-world sources.
- Whether outside knowledge is allowed depends on the task and available tools. Restricting an answer to supplied material is a specific task constraint.

An unknown can become an opening for inquiry. Look for an observation that would distinguish competing explanations, or identify what can still be concluded from the available information.

## 2. A Repertoire of Optional Interventions

Choose methods for the change they could make to the work. The perspectives below need not be independent or exhaustive, and they do not form a ladder of cognitive levels.

### A. Conceptual anchors: Give a concept useful work to do

Concepts such as dialectics, defamiliarization, and iceberg theory can remain in a prompt. The designer should understand what the concept is doing here and, when helpful, calibrate it with a concrete requirement.

| Conceptual anchor | Work it might perform in this task | Potential cost |
|---|---|---|
| Dialectics | Examine a premise shared by opposing positions; follow how a contradiction changes the question | Inventing opposition or forcing incompatible explanations into a synthesis |
| First principles | Distinguish constraints intrinsic to the task from habits inherited from existing practice | Discarding experience, history, or institutional conditions as incidental |
| Defamiliarization | Change the vantage point so a familiar subject reveals an overlooked relationship | Producing obscure wording without a discovery |
| Iceberg theory | Let actions, choices, and details carry emotion while controlling direct explanation | Withholding information the reader needs to understand the characters |
| Bayesian updating | Identify which observations would change the relative plausibility of competing explanations | Inventing precise probabilities without a basis |

Candidate instruction:

> Use dialectics to examine this dispute: identify a premise both sides rely on but neither has examined, and explain how changing it would affect their conclusions. Preserve the disagreement if the explanations remain incompatible.

Test the concept alone, the concrete requirement alone, and the combination. Do not presume that one form is inherently more intelligent.

**Remove or revise it when:** The concept leaves only terminology or stylistic traces, adds no valuable discovery, or pulls the subject into an unsuitable explanatory frame.

### B. Change the vantage point

When a conventional answer is adequate but offers little discovery, try changing the observer, timescale, or unit of analysis. A purposeful shift is easier to evaluate than an indiscriminate catalogue of perspectives.

Candidate instruction:

> Examine time saved by an individual user separately from coordination costs introduced for the team. Explain whether both could increase at once.

The relationship between the units matters. “Systems thinking” can also be used as an anchor, provided the interactions actually enter the analysis.

**Potential cost:** The new perspective displaces the original task or is treated as the only legitimate view.

**Remove or revise it when:** You cannot explain how the shift affects the conclusion, choice, or expression.

### C. Distinguish competing explanations

When several explanations fit the material, identify where they diverge and what observation could separate them.

Candidate instruction:

> Increased repeat purchasing could reflect satisfaction or the cost of switching. Compare these explanations using the available material. Identify the additional observation that would best distinguish them; do not invent data.

This also applies to conceptual inquiry: understand the strongest form of a position, then examine the conditions on which it depends. An opponent need not be foolish, and an idea need not change after every test.

**Potential cost:** Manufacturing false balance to fill out a list of alternatives.

**Remove or revise it when:** The available evidence already resolves the question and further alternatives only add burden.

### D. Use constraints that participate in the conception

Choose a constraint related to the work's purpose: perspective, available details, what a character can say aloud, or the means of expression.

Candidate instruction:

> Write a parting scene in which the characters discuss an ordinary object in the room. Let their different treatment of it reveal different intentions.

A useful constraint changes the conception. Do not automatically prohibit emotion words, adjectives, or explanation in every piece. Different works may require opposing techniques.

**Potential cost:** The work becomes a demonstration of technique, with character and situation sacrificed to the rule.

**Remove or revise it when:** The rule persistently blocks necessary expression, or the work becomes stronger without it.

### E. Protect the discovery, then critique something specific

Use this when a draft, proposal, or initial idea already exists. Identify what deserves to survive, then address defects that materially affect the work.

Candidate instruction:

> Preserve the draft's discovery that waiting has already changed the relationship. Check where that idea lacks support, and strengthen the relevant actions or conditions. Do not explain every detail merely to eliminate ambiguity.

Criticism can overturn an idea or establish that it withstands examination. Seek synthesis when a substantive contradiction makes it useful. Legitimate outcomes include choosing, juxtaposing, suspending judgment, or changing the question.

**Potential cost:** Overprotecting an initial conception and using distinctiveness as an exemption from criticism.

**Remove or revise it when:** There is no discovery worth retaining, or the task still needs broad exploration.

### F. Delay convergence when alternatives need room to develop

When the task calls for exploration, develop a few genuinely different directions before comparing them. The difference should lie in explanation, conception, or expressive logic, not just vocabulary.

Candidate instruction:

> Develop two story ideas about memory: one in which forgetting protects the protagonist, and one in which accurate recollection harms them. Develop each conflict before attempting any combination.

**Potential cost:** Generating possibilities indefinitely instead of completing the work, or turning every task into a brainstorming session.

**Remove or revise it when:** A sufficiently promising direction exists and the task now needs completion and refinement.

### Turn a selected intervention into a usable prompt

Start with the task and the intervention most worth trying. Add the material boundaries, audience, and delivery requirements that matter. Use enough language to carry the intention; let the task determine the length.

No fixed set of headings is required. The execution model should understand what to accomplish, what deserves attention, and which constraints matter. The prompt must work without access to this guide.

Ask the smallest useful clarification when missing goals, material, or audience would substantially change the design. For other gaps, use disclosed assumptions or placeholders as appropriate. Do not invent user preferences or task facts.

The final work need not name its methods. It should retain the reasons, distinctions, and uncertainty the reader needs. Hiding design vocabulary must not hide relevant evidence. Do not require a transcript of the execution model's private reasoning.

## 3. Paired Examples: Recognizing Apparently Excellent Answers

> **All examples in this section are constructed illustrations.** Both prompts and both outputs were written to explain a design distinction. They were not obtained from independent model runs and provide no evidence that one prompt performs better. Real outputs could converge, reverse the apparent advantage, or both fail.

### Example 1: Analysis — A distinction that changes a decision

**Task and material**

A studio is considering an unlimited-revisions design subscription. Interviewed customers like predictable spending and convenient communication. The studio worries that growth could reduce profits. It has no historical data on usage frequency, project difficulty, or revision hours. Write a short analysis for the founder.

**Candidate A**

> As an experienced business adviser, analyze this design subscription in terms of customer value, revenue, costs, and risks. Provide thoughtful, comprehensive, actionable advice. Use the supplied material without inventing data. Stay within 160 words.

**Illustrative output A**

> The subscription addresses customers' desire for predictable spending and convenient communication, while potentially giving the studio steadier revenue. Unlimited revisions create a risk of uncontrolled delivery costs. Define the service scope, establish a scheduling process, and track time by project. Run a small pilot before expanding, using retention, labor hours, and margins to assess whether pricing supports sustainable delivery.

This is a reasonable, clear answer and may satisfy the task. It leaves the relationship between unlimited revisions, purchase motivation, and profitability largely unexplored.

**Candidate B**

> Analyze this subscription for the founder. Distinguish why customers would buy from the conditions that would make serving them sustainably profitable. Examine how unlimited revisions connects the two. Propose one hypothesis that could change the pilot's design and identify what to observe to test it. General business reasoning is allowed; distinguish conjecture from supplied information and invent no data. Stay within 160 words.

**Illustrative output B**

> Customers have expressed a preference for predictable spending and convenient communication. That does not establish that unlimited revisions are necessary. One risk to test is that customers most attracted to unlimited revisions also require the most work. During the pilot, record what initially attracted each customer and compare that with revision hours. Also test whether a bounded service with a predictable price remains attractive. If customers are primarily buying certainty, the studio may not need to sell unlimited labor.

**Difference and cost**

B introduces a distinction that could change the pilot. Its coverage is narrower. If the reader needs comprehensive diligence, A's structure may be more useful. The customer-selection effect in B remains a hypothesis; its apparent insight does not make it a fact.

**Protect:** Predictable spending can be separated from unlimited labor.

**Correct:** Any sentence presenting the hypothesized selection effect as something already observed.

### Example 2: Inquiry — Examine a shared measure

**Task and material**

One person argues that productivity tools save time and therefore make people freer. Another argues that more work fills the saved time, making people busier. Help a reader understand the dispute without citing research that has not been supplied.

**Candidate A**

> Analyze both positions dialectically, explaining the strengths and limits of each. Conclude with a synthesis that accommodates technological progress and personal life. Be clear and thoughtful, invent no research, and stay within 160 words.

**Illustrative output A**

> Productivity tools can reduce repetitive labor and create discretionary time, but they can also raise expectations and increase workloads. Technology alone does not guarantee freedom; outcomes depend on how people use it and on institutional arrangements. We should benefit from these tools while establishing boundaries that prevent efficiency gains from becoming additional burdens.

The answer recognizes plausible possibilities, but “use tools well and establish boundaries” still needs development.

**Candidate B**

> Use dialectics to examine the dispute. Preserve each side's strongest point and identify a measure both use without examining it. Try another measure and explain how it changes the judgment of “greater freedom.” Retain the old measure where useful; synthesis is optional. Invent no research and stay within 160 words.

**Illustrative output B**

> Both sides count how much time the tools ultimately leave available. That matters, but it does not tell us who controls the saved time. An empty hour provides limited freedom if someone else can claim it at any moment. Conversely, someone may freely choose to spend saved time on more work. The dispute therefore needs to examine both working hours and authority over their use. These are related, but neither can stand in for the other.

**Difference and cost**

B separates the quantity of time from control over it, opening a relationship for further inquiry. It narrows the discussion and leaves income, skill, and the experience of work largely aside. Its value depends on the reader's question; greater abstraction alone does not make it better.

**Protect:** Adding a measure while retaining the original measure's legitimate use.

**Correct:** An overreach that reduces every productivity question to control over time.

### Example 3: Fiction — Different choices about one object

**Task**

An adult daughter is moving out. Her father sees her off at the door. Write a short, emotionally restrained scene. Invented details are allowed; do not explain the characters' psychology.

**Candidate A**

> Write the scene with restrained, precise language. Use action, dialogue, and setting to convey the difficulty of parting, without directly explaining either character's psychology. Stay within 120 words.

**Illustrative output A**

> Her father carried the suitcase into the hall, then straightened the fold in her collar. The corridor light went out. He stamped his foot to bring it back.
>
> “I'll call when I get there,” she said.
>
> He nodded, his hand still on the suitcase handle. When the lift arrived, she took it from him. He stepped back.
>
> As the doors began to close, he said it once more: “Take care on the way.”

The scene can work. Its actions and atmosphere are coherent, while the relationship develops mostly through familiar farewell gestures.

**Candidate B**

> Write the farewell scene, using iceberg theory if helpful to control explanation. Let father and daughter make different choices about an ordinary object, so the reader senses what moving out means to each. Do not directly explain their psychology or name the emotions. Invented details are allowed. Stay within 120 words.

**Illustrative output B**

> She put her key on the shoe cabinet.
>
> Her father picked it up. “Take it.”
>
> “Didn't you say you'd lost the spare?”
>
> “Found it.”
>
> She took the key, unhooked the little bear worn white at the edges, and left it on the cabinet. The lift chimed. Her father bent to stand the bear upright.
>
> “That too,” he said.

**Difference and cost**

B lets the object's destination carry different intentions and leaves room for interpretation. But keys and home are already a familiar association. Adding symbolism does not automatically increase originality. If further constraints make every gesture conspicuously arranged, A's naturalness could be preferable.

**Protect:** Different choices about the same object.

**Correct:** Added explanations that underline the symbolism, or contrived actions that lack a plausible place in the scene.

## 4. Practice Records: Let Results Change the Guide

### Evaluate the whole chain

Examine both the prompt produced with a manual and the work produced with that prompt. An elegant prompt, fluent terminology, or confident design commentary cannot substitute for downstream results.

Compare direct execution, design without a manual, and design with V1, V2, V3, and this candidate. Fix the model and environment, repeat independent runs, and compare outputs without version labels. The [evaluation protocol](Prompt_Design_Manual_Evaluation.md) provides inputs, tasks, records, and ablations. Keep that protocol out of the prompt designer's routine context.

Methods can be locally useful. Record where a method helps, where it does nothing, and where it causes harm. Older versions, direct requests, and prompts without added methods are allowed to win.

### Current claims and evidence status

| Claim to test | Current status | A result that would challenge it |
|---|---|---|
| Naming a task-specific distinction may help more than asking broadly for depth | Design hypothesis; examples are illustrative | Outputs become narrower, drift off task, or add no useful discovery |
| Combining a conceptual anchor with a concrete requirement may preserve association and direction | Design hypothesis | Either component alone does as well or better; the combination adds boilerplate |
| Protecting a discovery before revision may reduce the loss of valuable content | Design hypothesis | The instruction protects a mistaken core or fails to improve the work |
| Selecting methods as needed may reduce interference from an imposed framework | Design hypothesis | A complete framework consistently helps more on the target tasks |

This guide does not treat “conceptual density determines the cognitive ceiling” or “complex prompts are necessary for intelligence” as established laws. Nor does it describe a loosely constrained creative prompt as a technical mechanism for restoring a raw model, cancelling the existing instruction hierarchy, or switching off reasoning.

### Updating the guide

Record the specific problem, the change, the expected effect, the observation, counterexamples, and the applicable scope. After failure, examine the task, material, evaluation, and execution conditions. Do not automatically diagnose insufficiently elevated concepts or insufficiently forceful rules.

Write “not run” when no experiment has been run. Preserve uncertainty when only a small-sample signal exists. Expand a method's claimed scope gradually, after useful changes recur on new tasks and repeated runs.

### A final check before use

Check that the generated prompt is faithful to the task, works on its own, invents no task material, and gives every added requirement a purpose. If it merely reproduces this guide's terminology and structure, return to the task itself.

**This guide can also be omitted when it brings no valuable change.**
