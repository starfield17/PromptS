# Prompt Design Philosophy V1.0
(A "Cognitive Activation" Guide from 0 to 1)

> **Positioning**: This is a "Prompt Design Philosophy" document—focusing on how to use Prompts to activate model capabilities, shape the generation distribution, and establish an alignable field of thought.
> **What it doesn't do**: It does not include "controllability engineering" like engineering specifications, format validation, tool calls, or recovery loops (these are left for **PromptEngineeringV3**).
> **You can think of it as**: Learning "Directing and Aesthetics" first, then looking at "Construction Blueprints and Acceptance Standards."

---

## 0. The One-Sentence Principle: A Prompt is Not an Instruction, It's a "Field"
When you treat a Prompt as "giving commands to a machine," you will naturally write increasingly detailed rules.
When you treat a Prompt as "setting the stage and lighting," you will start to care about:
- **Where attention will be drawn** (information weight and focus)
- **What the thinking posture is** (role, method, style)
- **How it self-converges** (judgment system and iteration)

Therefore, a more useful definition is:

> **Prompt = Context Field Design**
> You are not writing constraints; you are writing "gravity."
> You are not programming the model; you are creating semantic resonance.

---

## 1. The Three Essential Tasks of a Prompt
A Prompt from 0 to 1 usually only needs to answer three types of questions:

1. **What exactly are you trying to optimize?** (Intention / Objective Function)
2. **Where does the model "believe" it is?** (World / Scene / Audience)
3. **How does it think and self-align?** (Method / Judge)

Get these three things right, and many "rules" won't need to be written; the model will automatically fill in reasonable behaviors.
Conversely, if these three things are missing, no amount of rules will help, like "writing construction specifications in a vacuum."

---

## 2. The Quartet Framework: Intention / World / Method / Judge
This is the minimal framework best suited for creating a Prompt from scratch.
Every time you write a Prompt, fill in these four slots first, then decide whether to engineer it further.

### 2.1 Intention: What Are You Actually Optimizing?
A common reason for failure from 0 to 1 is not that the model is incapable, but that you haven't made it clear "what is most important."

Lock down the intention with three questions:

- **Task Form**: Exploration (divergent) or decision-making (convergent)?
- **Priority of Success Criteria**: Novelty / Correctness / Executability / Persuasiveness / Stylistic Consistency—which comes first?
- **Boundary Conditions**: Is fiction allowed? Is inference allowed? What to do with insufficient evidence?

> Philosophical Tip: The intention is not "what the output looks like," but "what change you want to happen in the reader's mind."

---

### 2.2 World: Let the Model "Enter a Certain Work Mode"
The world is not background decoration; it is a switch for the model's behavioral strategy. A well-constructed world makes the model automatically choose more fitting expressions and structures.

When building the world, prioritize these four types of information:

- **Identity and Ethics**: Who is it? What is it responsible for? What is it not responsible for?
- **Scene and Audience**: Who is it writing for? What occasion is it for? (Internal memo / client proposal / classroom lecture / late-night radio)
- **Resources and Materials**: Where are the available materials? Which can only be referenced and not executed?
- **Risks and Stakes**: What happens if it's wrong? Should it be conservative, offer multiple solutions, or flag uncertainties?

#### 2.2.1 The Stanislavski Method: Don't Just Give a "Job Title," Give a "Life Experience"
- "You are a senior programmer" is just a label.
- "You write code like a craftsman polishes furniture, valuing simplicity and readability" activates values and aesthetics, making the output more consistent.

> You are giving the model a set of "personality vectors," not just a role name.

#### 2.2.2 Cognitive Anchors: Instantly Align Thinking Frameworks with High-Density Concepts
Naming a specific thinking model/school of thought in a Prompt is often more effective than writing a page of explanation, for example:
- First Principles (forces it to trace back to the source)
- Socratic Questioning (forces it to guide with questions)
- The Feynman Technique (forces it to explain in simple terms)
- Systems Theory, Game Theory, Narratology, Product Thinking, Editorial Thinking...

> These words are "semantic zip files" that trigger a whole set of implicit frameworks.

---

### 2.3 Method: In What "Cognitive Posture" Do You Want It to Think?
The method is not a list of steps, but a command to "make the model switch its posture": diverge, compare, critique, simulate, rewrite, abstract, implement...

Three common method postures (most stable for going from 0 to 1):

1. **Diverge first, then converge**: Seek diversity first, then make choices.
2. **Define the judge first, then generate**: Write the rubric/evaluation dimensions first, then produce the output.
3. **Fit the style first, then fill the content**: Determine the tone and structure first, then write the content.

#### 2.3.1 Thought Process Simulation: Make "Good Answers" a Byproduct of "Good Reasoning"
Your focus is not on "whether it calculated correctly," but "what path it took to get here."

You can stimulate high-quality reasoning in two non-engineering ways:

- **Drafting Stage**: First list 3–6 directions + reasons for choices, then generate the final draft.
- **Counter-example Test**: Have it point out under what circumstances the solution would fail and provide remedies.

#### 2.3.2 Focal Length Control: Zoom Out / Zoom In
- When the output is generic: demand "down to the action, sentence, example, number."
- When the output is stuck in details: demand a "systems perspective / historical perspective / objective function perspective."

> A Prompt can be zoomed in and out like a camera lens; the change in focal length is itself a capability summons.

#### 2.3.3 Multi-Voice Thinking: Obtain More Stable Insights Through "Internal Deliberation"
If you want "stronger thinking" rather than a "faster answer," you can have it simulate:
- The Optimist / The Skeptic / The Pragmatist / The Aesthetic Editor
- User's perspective / Competitor's perspective / Investor's perspective / Compliance perspective

You are not aiming for dramatic effect, but for improving "perspective coverage."

---

### 2.4 Judge: Replace "Restraints" with a "Judgment System"
The quality leap from 0 to 1 often comes from a **judgment system**, not more rules.

A minimally viable judge comes in two forms:

- **Checklist** (5–10 items): Coverage, clarity, risk, style, executability.
- **Rubric** (4–6 dimensions): Accuracy, relevance, structure, persuasiveness, creativity, feasibility.

> Core Philosophy: **Write fewer prohibitions, more review criteria.**
> Letting the model align itself with standards is more effective than you manually "tightening the screws."

#### 2.4.1 "Honesty Pact": Use Creativity on Solutions, Not on Fabricating Facts
When working in high-risk factual domains (medical/legal/financial/real-time information), you must also give the model a philosophical bottom line:
- If uncertain, label it as uncertain.
- If evidence is insufficient, state what's missing.
- Do not fill in the blanks with a "sounds very certain" tone.

> This is "creative ethics," not an engineering specification; it protects your judgment and the credibility of the model's output.

---

## 3. Three-Stage Creation Process: Divergence → Convergence → Solidification
This is a path that reconciles "creativity" with "reusability."

### 3.1 Divergence: Activate Capabilities (Let the Latent Space Unfold)
Goal: Have the model expand possibilities as much as possible.
Method:
- Create strong world and intention tension (audience, conflict, constraints, desired effect).
- Use few rigid formats, allow for multiple solution outputs (3–8 directions).
- Require each direction to include "highlights / risks / applicable scenarios."

The key to the divergence stage is not to be "more like a specification," but "more like a brainstorming session."

---

### 3.2 Convergence: Turn Good Ideas into a Good Product
Goal: Choose the best among multiple solutions and complete the structure and details.
Method:
- Have it compare the trade-offs of A/B/C.
- Create an outline first, then expand (or generate section by section).
- Introduce the judge: score according to the rubric and explain any deductions.

> Philosophical Reminder: Convergence is not about deleting imagination, but about compressing imagination into a denser expression.

---

### 3.3 Solidification: "Encapsulate" a Success for Reusability
Goal: Distill the successful method into a template or workflow.
Method (writing only philosophical principles, not engineering details):
- Describe the "key good points" as reviewable standards (e.g., covering key points, structural hierarchy, reader action).
- Retain the "judge + iteration" mechanism instead of piling on more constraints.
- If it needs to enter production/team reuse, then hand it over to PromptEngineeringV3 for engineering.

---

## 4. Tension Management: Freedom vs. Controllability
Every Prompt manages a tension axis:

- The higher the **openness**: the more novel, but the more unstable.
- The higher the **constraint**: the more stable, but the more easily rigid.

The philosophical solution is "phased parameter tuning":
- Divergence stage: fewer constraints, more judging (let it self-evaluate first).
- Convergence stage: add structure and trade-offs (outline, comparison, counter-examples).
- Solidification stage: only then consider turning the structure into an engineer-controllable constraint.

> You are not choosing one over the other, but "switching modes by stage."

---

## 5. Attention Economics: Writing Prompts for a "Weighting System"
The model's attention is a scarce resource. Every sentence you write is competing for weight.

Philosophically, you just need to remember three things:

1. **Put the most important things in high-weight areas** (beginning/end).
2. **Avoid burying key content in the "middle dead zone"** (the middle of a long context is easily diluted).
3. **Semantically separate "instructions" from "materials"** (otherwise they will contaminate and dilute each other).

These three points are enough to explain most instances of "why it didn't do what I said."

---

## 6. Language as Incantation: Semantic Resonance and Language Density
The higher the lexical density of a Prompt, the "sharper" the model's output.

### 6.1 Strong Verbs + Concrete Nouns
- "Change it a bit" is too weak.
- "Polish it into shorter sentences with more rhythm and impact" provides an aesthetic direction.
- "Analyze" is very general.
- "Dissect / attribute / synthesize / critique / rewrite" can better pinpoint the thinking action.

> Vague words give the model a wide distribution; precise words give it a sharp distribution.

### 6.2 Atmosphere Palette: Style is Not Decoration, It's an Information Carrier
You can directly write:
- Tone: Calm, restrained, sharp, warm, humorous, academic...
- Narrative: Iceberg theory, late-night radio, lawyer's closing argument, product launch, editorial revision...

Style is not a "filter added at the end," but the framework that "determines how content is organized."

### 6.3 Describe Style with Contrast: Positive + Negative Examples
If you care a lot about a certain stylistic consistency, the most philosophically effective way is:
- Give a "similar sample" that you like.
- Then give a "counter-example" that you dislike.
- Let the model actively summarize the differences and generate based on that.

> You are training it to recognize "aesthetic boundaries," not listing rules.

---

## 7. Symbiotic Iteration: Treat the Prompt as a Living Entity
The strongest form of a Prompt is not "getting it right once," but "growing it through conversation."

### 7.1 Give Feedback Like You're Guiding a Person
Don't just say "too long/wrong." You can say:
- "The structure is good, but it lacks empathy; keep the structure, but make the tone warmer."
- "This metaphor is forced, change it to a more everyday one."
- "Replace the abstract sentences with 2 concrete scenario examples."

The model responds strongly to "human-like feedback" because it is naturally good at imitation and alignment.

### 7.2 Meta-Prompting: Let the Model Help You Write Prompts
When you don't know how to describe your needs, just let the model ask you:
- "To better complete X, please ask me 8 clarifying questions."
- "Please rewrite my request into a stronger draft system prompt."

> This is a form of human-machine co-creation: temporarily handing over control to the party that is better at semantic organization.

---

## 8. From Philosophy to Engineering: How the Two Documents Should Be Divided
You can break your workflow into two steps:

1. **First, use the philosophy document to write the "field"**: Intention / World / Method / Judge.
2. **Then, use the engineering document for "solidification and acceptance"**: format, constraints, tools, recovery, evaluation, version control.

A practical criterion for judgment:

- When you are "looking for direction, expression, or soul" → use this philosophy document.
- When you need "stable reproduction, team collaboration, or online reliability" → hand it over to PromptEngineeringV3.

---

## Appendix A: Three General Prompt Skeletons (Field Embryos)
> The following are not engineering templates, but "field skeletons." Just fill in the quartet.

### A1. Exploratory (Divergent)
- **Intention**: I want 6 different directions, prioritizing novelty and inspiration.
- **World**: You are ___; the audience is ___; the scene is ___.
- **Method**: First list directions → for each, list highlights/risks/scenarios → give 1 recommended combination.
- **Judge**: Novelty × Executability × Fit (please self-evaluate and explain).

---

### A2. Convergent (Decision-Making/Final Draft)
- **Intention**: I want a deliverable version, prioritizing executability and persuasiveness.
- **World**: You are ___; I will present this to ___; the decision risk is ___.
- **Method**: First give an outline → generate paragraph by paragraph → self-evaluate → refine.
- **Judge**: Clear structure, key points covered, clear actions, consistent tone, risk warnings.

---

### A3. Critical (Editing/Review)
- **Input**: This is the v1 draft + success criteria.
- **Intention**: Turn it into v2 with minimal changes.
- **Method**: Point out deviations from the standard one by one → give suggestions for changes → output v2.
- **Judge**: Only change the 20% that most affects quality, avoid starting over from scratch.

---

## Appendix B: Philosophical Checklist (Ask Yourself Before Hitting Send)
1. Have I made the "most important success criterion" clear?
2. Have I built a sufficiently believable "world" (identity, audience, scene, risk)?
3. Have I specified the "cognitive posture" I want it to adopt (diverge/compare/critique/implement)?
4. Have I provided a "judge" (checklist or rubric) for it to self-align?
5. Are the words I used specific, powerful, and capable of causing semantic resonance?

---

## References and Division of Labor (Your provided drafts/specifications)
- PromptEngineeringV3 (Engineering specifications, reserved for solidification and controllability)
- "Prompt Design Philosophy: A Cognitive Activation Guide" (Semantic resonance / thought paths / iterative view)
- "A Guide to Prompt Design Philosophy from 0 to 1 v0.1" (Quartet/three stages/tension management)
